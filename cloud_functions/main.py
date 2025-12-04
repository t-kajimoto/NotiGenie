import functions_framework
from flask import Request
import os
import json
import yaml
import asyncio
from typing import Tuple

# Clean Architecture Components
# coreパッケージから必要なコンポーネントをインポートします
from core.interfaces.gateways.gemini_adapter import GeminiAdapter
from core.interfaces.gateways.notion_adapter import NotionAdapter
from core.interfaces.controllers.line_controller import LineController
from core.use_cases.process_message import ProcessMessageUseCase


# Configuration Loading
def load_config_and_prompts() -> Tuple[dict, dict]:
    """
    設定ファイルとプロンプトファイルを読み込みます。
    Infrastructure層の責務として、外部ファイルシステムからの読み込みを行います。

    Returns:
        Tuple[dict, dict]: (config辞書, prompts辞書)
    """
    base_path = os.path.dirname(os.path.abspath(__file__))
    # config.yaml is replaced by schemas.yaml
    config_path = os.path.join(base_path, "schemas.yaml")

    # Load config
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    else:
        print(f"Warning: {config_path} not found. Using empty config.")
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


# Dependency Injection / Composition Root
# アプリケーションの構成ルート。ここで依存関係を注入し、オブジェクトグラフを構築します。
try:
    config_data, prompts_data = load_config_and_prompts()
    db_mapping = config_data.get("notion_databases", {})

    # 1. Initialize Gateways (Adapters)
    gemini_adapter = GeminiAdapter(
        command_prompt_template=prompts_data.get("command", ""),
        response_prompt_template=prompts_data.get("response", ""),
        notion_database_mapping=db_mapping
    )
    notion_adapter = NotionAdapter(notion_database_mapping=db_mapping)

    # 2. Initialize Use Case (Inject Gateways)
    process_message_use_case = ProcessMessageUseCase(
        language_model=gemini_adapter,
        notion_repository=notion_adapter
    )

    # 3. Initialize Controllers (Inject Use Case)
    line_controller = LineController(use_case=process_message_use_case)

except Exception as e:
    print(f"Initialization Error: {e}")
    # 初期化失敗時はNoneにしておき、リクエスト時にエラーを返す
    process_message_use_case = None
    line_controller = None


@functions_framework.http
def main(request: Request):
    """
    HTTP Cloud Function Entry Point.
    Frameworks & Drivers層に位置します。
    ここから適切なコントローラーにリクエストを振り分けます。

    Args:
        request (flask.Request): The request object.
    Returns:
        The response text or tuple.
    """
    if not process_message_use_case:
        return "Server Internal Configuration Error: Initialization failed", 500

    # 1. LINE Webhook Request Handling
    # ヘッダーにLINE特有の署名がある場合はLINEコントローラーに任せます
    if "X-Line-Signature" in request.headers:
        if not line_controller:
            return "LINE Handler not configured", 500

        signature = request.headers["X-Line-Signature"]
        body = request.get_data(as_text=True)
        try:
            line_controller.handle_request(body, signature)
            return "OK"
        except Exception as e:
            print(f"LINE Webhook Error: {e}")
            return f"Error: {e}", 500

    # 2. Raspberry Pi / API Request Handling
    # 独自のJSON APIへのリクエストとして処理します
    request_json = request.get_json(silent=True)
    if request_json and "text" in request_json:
        user_utterance = request_json["text"]
        current_date = request_json.get("date", "")

        # 非同期ユースケースを実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response_text = loop.run_until_complete(
                process_message_use_case.execute(user_utterance, current_date)
            )
            return json.dumps({"response": response_text}, ensure_ascii=False)
        except Exception as e:
            print(f"Process Error: {e}")
            return json.dumps({"error": str(e)}), 500
        finally:
            loop.close()

    return "Invalid Request", 400
