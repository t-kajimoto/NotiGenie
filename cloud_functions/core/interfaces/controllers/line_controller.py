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
    Webフレームワーク（Flaskなど）やLINE SDKからの入力を受け取り、
    内部のビジネスロジックであるユースケース（ProcessMessageUseCase）に適した形に変換して渡します。
    """

    def __init__(self, use_case: ProcessMessageUseCase):
        """
        コンストラクタ。依存関係を注入します。

        Args:
            use_case (ProcessMessageUseCase): メッセージ処理のビジネスロジックを実行するオブジェクト。
        """
        self.channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
        self.channel_secret = os.environ.get("LINE_CHANNEL_SECRET")
        self.use_case = use_case

        if self.channel_access_token and self.channel_secret:
            # LINE APIクライアントの設定
            configuration = Configuration(access_token=self.channel_access_token)
            self.api_client = ApiClient(configuration)
            self.messaging_api = MessagingApi(self.api_client)

            # Webhookイベントのパーサー設定
            # なぜ WebhookHandler ではなく WebhookParser を使うのか:
            # WebhookHandler はコールバック関数を登録する方式で設計されていますが、
            # デフォルトの実装では同期的に処理が行われます。
            # 今回のアーキテクチャでは async/await を使用した非同期処理を行いたいため、
            # イベントの解析だけを行う Parser を使用し、処理ループは自分で制御します。
            self.parser = WebhookParser(self.channel_secret)
        else:
            # 設定が不足している場合は機能を無効化（ローカルテスト時などにエラーにならないようにする）
            self.parser = None
            self.api_client = None
            self.messaging_api = None
            print("Warning: LINE credentials not found. LINE bot features will be disabled.")

    async def handle_request(self, body: str, signature: str):
        """
        HTTPリクエストから受け取ったボディと署名を処理します。
        Cloud Functionのエントリーポイントから呼び出されます。

        何をやっているか:
        1. `WebhookParser` を使ってリクエストの署名検証とイベント解析を行います。
        2. 解析されたイベントのリストをループ処理します。
        3. テキストメッセージイベントの場合のみ、詳細な処理メソッドを呼び出します。

        Args:
            body (str): リクエストボディ（JSON文字列）。
            signature (str): X-Line-Signatureヘッダーの値。改ざん防止用。
        """
        if not self.parser:
            raise ValueError("LINE credentials not set")

        # リクエストの解析 (署名検証も含む)
        # parseメソッド自体は同期的ですが、取得したイベントリストを非同期に処理します
        events = self.parser.parse(body, signature)

        for event in events:
            # テキストメッセージが送られてきた場合のみ処理対象とします
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
                await self._handle_text_message(event)

    async def _handle_text_message(self, event):
        """
        テキストメッセージイベントの具体的な処理ロジック。

        何をやっているか:
        1. ユーザーの発言内容と返信用のトークンを取得します。
        2. 現在の日付を日本時間（JST）で取得します（AIが「今日」を理解するために必要）。
        3. ユースケースを実行してAIからの応答を取得します。
        4. LINE Messaging API を使ってユーザーに応答メッセージを送信します。

        Args:
            event: LINE SDKのMessageEventオブジェクト。
        """
        user_utterance = event.message.text
        reply_token = event.reply_token

        # JSTで現在日付を取得
        # なぜ必要か: Notionのタスク管理などで「今日のタスク」などを検索する際、
        # サーバー（UTC）の時間ではなくユーザーの現地時間（JST）が必要だからです。
        current_date = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")

        try:
            # ユースケースの実行
            # ここでドメインロジック（AIによる判断とNotion操作）に委譲します
            final_response_text = await self.use_case.execute(user_utterance, current_date)

            # LINEへの応答送信
            # MessagingApiを使用して、リプライを返します
            self.messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=final_response_text)]
                )
            )

        except Exception as e:
            print(f"Error processing LINE message: {e}")
            # エラー時もユーザーに応答を返す（UX向上のため）
            # 既読スルー状態にせず、システムエラーであることを伝えます
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
