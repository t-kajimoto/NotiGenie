import functions_framework
from flask import Request, abort
import os
import json
import yaml
import traceback
import logging
import sys
from typing import Tuple
from asgiref.sync import async_to_sync
from linebot.v3.exceptions import InvalidSignatureError

# ---------------------------------------------------------------------------
# ロギング設定
# ---------------------------------------------------------------------------
# Cloud Functionsのログは標準エラー出力（stderr）に出力することで
# Google Cloud Loggingに正しく構造化されて取り込まれます。
# レベルをINFOに設定し、日時、モジュール名、ログレベル、メッセージを出力します。
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# クリーンアーキテクチャ コンポーネントのインポート
# ---------------------------------------------------------------------------
# 依存関係逆転の原則に基づき、インターフェースやユースケースをインポートします。
# 実際の実行フローでは、ここでインポートしたクラスを組み合わせて処理を行います。
from core.interfaces.gateways.gemini_adapter import GeminiAdapter
from core.interfaces.gateways.notion_adapter import NotionAdapter
from core.interfaces.gateways.firestore_adapter import FirestoreAdapter
from core.interfaces.controllers.line_controller import LineController
from core.use_cases.process_message import ProcessMessageUseCase


# ---------------------------------------------------------------------------
# 設定読み込み関数
# ---------------------------------------------------------------------------
def load_prompts() -> str:
    """
    AIへのシステム指示書（プロンプト）をファイルから読み込みます。

    Returns:
        str: システムプロンプトの文字列。
    """
    base_path = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(base_path, "prompts/system_instruction.md")

    if os.path.exists(prompt_path):
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        logger.warning(f"{prompt_path} not found.")
        return "You are a helpful assistant managing Notion databases. Today is {current_date}. Databases: {database_descriptions}"

def load_help_message() -> str:
    """
    ヘルプメッセージをファイルから読み込みます。
    """
    base_path = os.path.dirname(os.path.abspath(__file__))
    help_path = os.path.join(base_path, "prompts/help_message.md")
    
    if os.path.exists(help_path):
        with open(help_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        logger.warning(f"{help_path} not found.")
        return "ヘルプファイルが見つかりません。管理者に連絡してください。"


# ---------------------------------------------------------------------------
# 依存性の注入 (Dependency Injection) と初期化
# ---------------------------------------------------------------------------
# ここは「コンポジションルート (Composition Root)」と呼ばれ、アプリケーションの起動時に一度だけ実行されます。
# グローバルスコープに配置することで、Cloud Functionsのコールドスタート時にのみ実行され、
# 2回目以降のリクエストでは初期化済みのオブジェクトが再利用されます（ウォームスタート）。

try:
    # 1. スキーマ情報とプロンプトの読み込み
    #    - FirestoreAdapterを最初に初期化し、NotionスキーマをFirestoreから読み込みます。
    #    - これにより、schemas.yamlへの依存がなくなり、DB定義を動的に管理できます。
    firestore_adapter = FirestoreAdapter()
    schemas_data = firestore_adapter.load_notion_schemas()
    system_instruction = load_prompts()
    help_message = load_help_message()

    # 2. ゲートウェイ（外部サービスへのアダプター）の初期化
    #    - 取得したスキーマ情報を、GeminiとNotionのアダプターに渡します。
    gemini_adapter = GeminiAdapter(
        system_instruction_template=system_instruction,
        notion_database_mapping=schemas_data
    )
    notion_adapter = NotionAdapter(notion_database_mapping=schemas_data)

    # ---------------------------------------------------------
    # Notion API 接続確認 (Startup Verification)
    # ---------------------------------------------------------
    # 何をやっているか:
    # Notion APIへの接続テストを行います。
    # なぜやっているか:
    # デプロイ直後や起動時にAPIキーの設定ミスやネットワーク問題を検知するためです。
    # ここで失敗してもアプリケーション全体は停止させず、ログに残すだけに留めます。
    notion_adapter.validate_connection()
    # ---------------------------------------------------------

    # 2. ユースケースの初期化
    #    ビジネスロジックを担当するクラスに、具体的な外部アダプターを渡します（依存性の注入）。
    process_message_use_case = ProcessMessageUseCase(
        language_model=gemini_adapter,
        notion_repository=notion_adapter,
        session_repository=firestore_adapter,
        help_message=help_message
    )

    # 3. コントローラーの初期化
    #    Webリクエストをハンドリングするクラスに、ユースケースを渡します。
    line_controller = LineController(use_case=process_message_use_case)

except Exception as e:
    # 初期化中に致命的なエラーが発生した場合
    logger.error(f"Initialization Error: {e}")
    logger.error(traceback.format_exc())
    # リクエスト処理時にエラーを返せるよう、Noneを設定しておきます
    process_message_use_case = None
    line_controller = None


# ---------------------------------------------------------------------------
# 非同期メインロジック
# ---------------------------------------------------------------------------
async def main_logic(request: Request):
    """
    Cloud Functionのメインロジック（非同期版）。

    何をやっているか:
    1. 初期化が成功しているか確認します。
    2. リクエストヘッダーを見て、LINEからのWebhookか、それ以外（Raspberry Piなど）かを判定します。
    3. LINEの場合: `LineController` に処理を委譲します。
    4. その他の場合: JSONボディを読み取り、`ProcessMessageUseCase` を直接呼び出します。

    Args:
        request (flask.Request): HTTPリクエストオブジェクト。

    Returns:
        レスポンス本文とHTTPステータスコードのタプル、またはレスポンス文字列。
    """
    # 初期化失敗時のガード節
    if not process_message_use_case:
        return "Server Internal Configuration Error: Initialization failed. Please check the logs for details.", 500

    # 1. LINE Webhook リクエストの処理
    # LINEプラットフォームからのリクエストには必ず 'X-Line-Signature' ヘッダーが含まれます。
    if "X-Line-Signature" in request.headers:
        if not line_controller:
            logger.error("Request received but LineController is not configured.")
            return "LINE Handler not configured", 500

        signature = request.headers["X-Line-Signature"]
        body = request.get_data(as_text=True) # テキストとしてボディを取得
        try:
            # コントローラーに処理を委譲（非同期実行）
            await line_controller.handle_request(body, signature)
            return "OK"
        except InvalidSignatureError:
            # 署名検証失敗はセキュリティリスクまたは設定ミス
            logger.warning("Invalid Signature in LINE Webhook")
            abort(400)
        except Exception as e:
            # その他の予期せぬエラー
            logger.error(f"LINE Webhook Error: {e}")
            logger.error(traceback.format_exc())
            return f"Error: {e}", 500

    # 2. Raspberry Pi / 内部API リクエストの処理
    # LINE以外からのリクエスト（音声入力クライアントなど）を処理します。

    # APIキー認証
    expected_api_key = os.environ.get("NOTIGENIE_API_KEY")
    if expected_api_key:
        provided_api_key = request.headers.get("X-API-Key")
        if provided_api_key != expected_api_key:
            logger.warning("Unauthorized API request: Invalid or missing API key")
            return "Unauthorized", 401

    request_json = request.get_json(silent=True)
    if request_json and "text" in request_json:
        user_utterance = request_json["text"]
        current_date = request_json.get("date", "")
        # Raspberry PiなどはセッションIDを持たせるか、デフォルトにするか
        session_id = request_json.get("session_id", "default_api_session")
        logger.info(f"Received API request: {user_utterance}")

        try:
            # ユースケースを直接実行して結果を取得
            response_text = await process_message_use_case.execute(user_utterance, current_date, session_id=session_id)
            # JSON形式で応答を返す
            return json.dumps({"response": response_text}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Process Error: {e}")
            logger.error(traceback.format_exc())
            return json.dumps({"error": str(e)}), 500

    # どちらのパターンにもマッチしなかった場合
    return "Invalid Request", 400


# ---------------------------------------------------------------------------
# Cloud Function エントリーポイント (同期ラッパー)
# ---------------------------------------------------------------------------
@functions_framework.http
def main(request: Request):
    """
    Google Cloud FunctionsのHTTPエントリーポイント。

    何をやっているか:
    非同期関数 `main_logic` を `async_to_sync` でラップして同期的に呼び出します。

    なぜやっているか:
    現在の Google Cloud Functions (Python runtime) の `functions-framework` は
    WSGIベースであり、エントリーポイント関数は同期的である必要があります。
    一方、内部ロジック（LINE SDKやGemini API呼び出し）は効率のために非同期（async/await）で実装したいため、
    この変換層（ブリッジ）が必要になります。
    """
    return async_to_sync(main_logic)(request)
