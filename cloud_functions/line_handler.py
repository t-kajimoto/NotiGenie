from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import os
import asyncio
import datetime
from zoneinfo import ZoneInfo

class LineHandler:
    """
    LINE Messaging API Webhook Handler.
    """
    def __init__(self, gemini_agent, notion_handler):
        self.channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
        self.channel_secret = os.environ.get("LINE_CHANNEL_SECRET")
        self.gemini_agent = gemini_agent
        self.notion_handler = notion_handler

        if self.channel_access_token and self.channel_secret:
            configuration = Configuration(access_token=self.channel_access_token)
            self.api_client = ApiClient(configuration)
            self.messaging_api = MessagingApi(self.api_client)
            self.handler = WebhookHandler(self.channel_secret)

            # Register events
            @self.handler.add(MessageEvent, message=TextMessageContent)
            def handle_message(event):
                self._handle_text_message(event)
        else:
            # For testing or if not enabled
            self.handler = None
            self.api_client = None
            self.messaging_api = None

    def handle_request(self, body, signature):
        """
        Validates the signature and handles the webhook event.
        """
        if not self.handler:
            raise ValueError("LINE credentials not set")
        self.handler.handle(body, signature)

    def _handle_text_message(self, event):
        user_utterance = event.message.text
        reply_token = event.reply_token
        current_date = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")

        # Create a new loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 1. Intent Analysis
            command = loop.run_until_complete(
                self.gemini_agent.generate_notion_command(user_utterance, current_date)
            )

            # 2. Execute Notion Tool
            if command.get("action") == "error":
                tool_result = command.get("message")
            else:
                action = command.get("action")
                args = {k: v for k, v in command.items() if k != "action"}
                tool_result = self.notion_handler.execute_tool(action, args)

            # 3. Generate Final Response
            final_response_text = loop.run_until_complete(
                self.gemini_agent.generate_final_response(user_utterance, tool_result)
            )

            # 4. Reply
            self.messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=final_response_text)]
                )
            )

        except Exception as e:
            print(f"Error processing LINE message: {e}")
            try:
                self.messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="申し訳ありません、エラーが発生しました。")]
                    )
                )
            except Exception as inner_e:
                print(f"Error sending error message: {inner_e}")
        finally:
            loop.close()
