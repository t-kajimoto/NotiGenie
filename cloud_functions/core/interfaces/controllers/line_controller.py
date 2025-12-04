from linebot.v3 import WebhookHandler, WebhookParser
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import os
import asyncio
import datetime
from zoneinfo import ZoneInfo
from ...use_cases.process_message import ProcessMessageUseCase


class LineController:
    """
    LINE Messaging APIからのWebhookリクエストを処理するコントローラー。
    Clean Architectureにおける「Interface Adapter」層に位置します。
    外部フレームワーク（LINE Bot SDK）からのイベントを受け取り、
    内部のユースケース（ProcessMessageUseCase）に変換して渡します。
    """

    def __init__(self, use_case: ProcessMessageUseCase):
        """
        コンストラクタ。

        Args:
            use_case (ProcessMessageUseCase): メッセージ処理のビジネスロジック。
        """
        self.channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
        self.channel_secret = os.environ.get("LINE_CHANNEL_SECRET")
        self.use_case = use_case

        if self.channel_access_token and self.channel_secret:
            configuration = Configuration(access_token=self.channel_access_token)
            self.api_client = ApiClient(configuration)
            self.messaging_api = MessagingApi(self.api_client)
            # WebhookHandlerは同期処理用のため、非同期対応のためにWebhookParserを使用します
            self.parser = WebhookParser(self.channel_secret)
        else:
            # 設定が不足している場合は機能を無効化（ローカルテスト時などにエラーにならないようにする）
            self.parser = None
            self.api_client = None
            self.messaging_api = None
            print("Warning: LINE credentials not found. LINE bot features will be disabled.")

    async def handle_request(self, body: str, signature: str):
        """
        署名を検証し、Webhookイベントを処理します。
        Cloud Functionのエントリーポイントから呼び出されます。

        Args:
            body (str): リクエストボディ。
            signature (str): X-Line-Signatureヘッダーの値。
        """
        if not self.parser:
            raise ValueError("LINE credentials not set")

        # Parse events asynchronously (parsing itself is sync but we handle result async)
        events = self.parser.parse(body, signature)

        for event in events:
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
                await self._handle_text_message(event)

    async def _handle_text_message(self, event):
        """
        テキストメッセージイベントの実際の処理。
        """
        user_utterance = event.message.text
        reply_token = event.reply_token
        # JSTで現在日付を取得
        current_date = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")

        try:
            # ユースケースの実行
            # ここでドメインロジックに委譲します
            final_response_text = await self.use_case.execute(user_utterance, current_date)

            # LINEへの応答送信
            self.messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=final_response_text)]
                )
            )

        except Exception as e:
            print(f"Error processing LINE message: {e}")
            # エラー時もユーザーに応答を返す（UX向上のため）
            if self.messaging_api:
                try:
                    self.messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[TextMessage(text="申し訳ありません、システムエラーが発生しました。")]
                        )
                    )
                except Exception as inner_e:
                    print(f"Error sending error message: {inner_e}")
