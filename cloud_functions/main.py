import functions_framework
from flask import Request, abort
import os
import json
import yaml
import asyncio
import traceback
from typing import Tuple
from asgiref.sync import async_to_sync
from linebot.v3.exceptions import InvalidSignatureError

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
    schemas_path = os.path.join(base_path, "schemas.yaml")

    # Load schemas (previously config.yaml)
    if os.path.exists(schemas_path):
        with open(schemas_path, 'r', encoding='utf-8') as f:
            schemas = yaml.safe_load(f)
    else:
        print(f"Warning: {schemas_path} not found. Using empty config.")
        schemas = {}

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

    return schemas, prompts


# Dependency Injection / Composition Root
# アプリケーションの構成ルート。ここで依存関係を注入し、オブジェクトグラフを構築します。
try:
    schemas_data, prompts_data = load_config_and_prompts()
    # schemas.yaml is now the db_mapping itself
    db_mapping = schemas_data

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
    traceback.print_exc()
    # 初期化失敗時はNoneにしておき、リクエスト時にエラーを返す
    process_message_use_case = None
    line_controller = None

async def main_logic(request: Request):
    """
    Async logic for the Cloud Function.
    This function contains the core logic previously in 'main'.
    """
    if not process_message_use_case:
        return "Server Internal Configuration Error: Initialization failed. Please check the logs for details.", 500

    # 1. LINE Webhook Request Handling
    if "X-Line-Signature" in request.headers:
        if not line_controller:
            print("Request received but LineController is not configured.")
            return "LINE Handler not configured", 500

        signature = request.headers["X-Line-Signature"]
        body = request.get_data(as_text=True)
        try:
            await line_controller.handle_request(body, signature)
            return "OK"
        except InvalidSignatureError:
            abort(400)
        except Exception as e:
            print(f"LINE Webhook Error: {e}")
            traceback.print_exc()
            return f"Error: {e}", 500

    # 2. Raspberry Pi / API Request Handling
    request_json = request.get_json(silent=True)
    if request_json and "text" in request_json:
        user_utterance = request_json["text"]
        current_date = request_json.get("date", "")

        try:
            response_text = await process_message_use_case.execute(user_utterance, current_date)
            return json.dumps({"response": response_text}, ensure_ascii=False)
        except Exception as e:
            print(f"Process Error: {e}")
            traceback.print_exc()
            return json.dumps({"error": str(e)}), 500

    return "Invalid Request", 400

@functions_framework.http
def main(request: Request):
    """
    HTTP Cloud Function Entry Point.
    Wraps the async logic in a synchronous call to ensure compatibility with
    Functions Framework and Flask's request dispatching in the current environment.
    """
    return async_to_sync(main_logic)(request)
