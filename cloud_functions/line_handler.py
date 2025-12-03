from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
import os

class LineHandler:
    def __init__(self):
        self.channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
        self.channel_secret = os.environ.get("LINE_CHANNEL_SECRET")
        if self.channel_access_token and self.channel_secret:
            configuration = Configuration(access_token=self.channel_access_token)
            self.api_client = ApiClient(configuration)
            self.messaging_api = MessagingApi(self.api_client)
            self.handler = WebhookHandler(self.channel_secret)
        else:
            # For testing or if not enabled
            self.handler = None

    def handle_request(self, body, signature):
        if not self.handler:
            raise ValueError("LINE credentials not set")
        self.handler.handle(body, signature)

    # TODO: Add event handlers (e.g. MessageEvent)
