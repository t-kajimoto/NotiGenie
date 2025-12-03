import functions_framework
from flask import Request
import os
import json
from .line_handler import LineHandler
from .gemini_agent import GeminiAgent
from .notion_handler import NotionHandler
import asyncio

# Initialize handlers (lazy loading or global)
line_handler = LineHandler()
gemini_agent = GeminiAgent()
notion_handler = NotionHandler()

@functions_framework.http
def main(request: Request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`.
    """

    # 1. Check if it is a LINE Webhook
    if "X-Line-Signature" in request.headers:
        signature = request.headers["X-Line-Signature"]
        body = request.get_data(as_text=True)
        try:
            line_handler.handle_request(body, signature)
            return "OK"
        except Exception as e:
            print(f"LINE Webhook Error: {e}")
            return f"Error: {e}", 500

    # 2. Handle Raspberry Pi / Client App Request
    # Expected JSON: {"text": "user utterance", "date": "2023-10-27"}
    request_json = request.get_json(silent=True)
    if request_json and "text" in request_json:
        user_utterance = request_json["text"]
        current_date = request_json.get("date", "")

        # Run async logic
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 1. Intent Analysis
            command = loop.run_until_complete(gemini_agent.generate_notion_command(user_utterance, current_date))

            # 2. Execute Notion Tool
            if command.get("action") == "error":
                tool_result = command.get("message")
            else:
                # Assuming command has 'action' and remaining keys are args
                action = command.get("action")
                args = {k: v for k, v in command.items() if k != "action"}
                tool_result = notion_handler.execute_tool(action, args)

            # 3. Generate Final Response
            final_response = loop.run_until_complete(gemini_agent.generate_final_response(user_utterance, tool_result))

            return json.dumps({"response": final_response})

        except Exception as e:
             return json.dumps({"error": str(e)}), 500
        finally:
            loop.close()

    return "Invalid Request", 400
