import functions_framework
from flask import Request
import os
import json
import yaml
import asyncio
from .line_handler import LineHandler
from .gemini_agent import GeminiAgent
from .notion_handler import NotionHandler

# Load Configuration and Prompts
def load_resources():
    base_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_path, "config.yaml")

    # Load config
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    else:
        print(f"Warning: {config_path} not found.")
        config = {}

    # Load prompts
    prompts = {}
    prompt_files = {
        "command": "prompts/notion_command_generator.md",
        "response": "prompts/final_response_generator.md"
    }

    for key, rel_path in prompt_files.items():
        path = os.path.join(base_path, rel_path)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                prompts[key] = f.read()
        else:
            print(f"Warning: {path} not found.")
            prompts[key] = ""

    return config, prompts

# Initialize handlers (Global scope to run on cold start)
try:
    config_data, prompts_data = load_resources()
    db_mapping = config_data.get("notion_databases", {})

    # Initialize handlers
    # Note: Environment variables must be set in the Cloud Functions environment
    line_handler = LineHandler()
    gemini_agent = GeminiAgent(
        command_prompt_template=prompts_data.get("command", ""),
        response_prompt_template=prompts_data.get("response", ""),
        notion_database_mapping=db_mapping
    )
    notion_handler = NotionHandler(notion_database_mapping=db_mapping)

except Exception as e:
    print(f"Initialization Error: {e}")
    # Function execution might fail if dependencies are not met, but we allow import to succeed
    # so we can see logs. In production, failing fast might be better.
    # raise e # Commented out to allow testing/linting without full env
    line_handler = None
    gemini_agent = None
    notion_handler = None


@functions_framework.http
def main(request: Request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`.
    """

    if not gemini_agent or not notion_handler:
        return "Server Configuration Error", 500

    # 1. Check if it is a LINE Webhook
    if "X-Line-Signature" in request.headers:
        if not line_handler:
             return "LINE Handler not configured", 500

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

            return json.dumps({"response": final_response}, ensure_ascii=False)

        except Exception as e:
             print(f"Process Error: {e}")
             return json.dumps({"error": str(e)}), 500
        finally:
            loop.close()

    return "Invalid Request", 400
