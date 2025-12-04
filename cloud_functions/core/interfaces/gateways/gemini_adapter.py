import os
import json
import asyncio
import logging
import sys
import google.generativeai as genai
from typing import Dict, Any
from ...domain.interfaces import ILanguageModel

# ロガーの設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


class GeminiAdapter(ILanguageModel):
    """
    Gemini APIを使用したILanguageModelの実装。
    Infrastructure層に位置し、外部APIとの通信詳細をカプセル化します。
    """

    def __init__(self, command_prompt_template: str, response_prompt_template: str, notion_database_mapping: dict):
        """
        初期化処理。

        Args:
            command_prompt_template (str): コマンド生成用のプロンプトテンプレート。
            response_prompt_template (str): 応答生成用のプロンプトテンプレート。
            notion_database_mapping (dict): Notionデータベースの定義情報（プロンプトに埋め込むため）。
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        # Geminiライブラリの設定
        # Note: genai.configure sets the API key globally.
        genai.configure(api_key=api_key)

        self.command_prompt_template = command_prompt_template
        self.response_prompt_template = response_prompt_template
        self.notion_database_mapping = notion_database_mapping

    def _get_model(self):
        """
        GenerativeModelのインスタンスを生成して返します。
        'Event loop is closed' エラーを防ぐため、リクエストごとに（メソッド呼び出し時に）
        インスタンス化することを推奨します。
        """
        return genai.GenerativeModel('gemini-2.0-flash-lite')

    def _build_command_prompt(self, user_utterance: str, current_date: str) -> str:
        """
        コマンド生成用のシステムプロンプトを構築します。
        """
        database_descriptions = ""
        for db_name, db_info in self.notion_database_mapping.items():
            title = db_info.get('title', db_name)
            # スキーマ情報も含める（Geminiがプロパティを理解しやすくするため）
            properties_info = ""
            if 'properties' in db_info:
                properties_info = "\n  Properties:\n"
                for prop_name, prop_details in db_info['properties'].items():
                    prop_type = prop_details.get('type', 'unknown')
                    options = ""
                    if 'options' in prop_details:
                        options = f" (Options: {', '.join(prop_details['options'])})"
                    properties_info += f"  - {prop_name} ({prop_type}){options}\n"

            database_descriptions += f"- {db_name} ({title}): {db_info['description']}{properties_info}\n"

        full_prompt = self.command_prompt_template.replace("{database_descriptions}", database_descriptions)
        full_prompt = full_prompt.replace("{user_utterance}", user_utterance)
        full_prompt = full_prompt.replace("{current_date}", current_date)
        return full_prompt

    async def _generate_content_async(self, prompt: str) -> Dict[str, Any]:
        """
        Geminiにプロンプトを投げ、JSONレスポンスをパースして返します。
        """
        logger.info(f"Sending prompt to Gemini:\n{prompt}")

        try:
            model = self._get_model()
            # 'Event loop is closed' エラー回避のため、同期メソッドをスレッドで実行する
            response = await asyncio.to_thread(model.generate_content, prompt)

            logger.info(f"Received response from Gemini:\n{response.text}")

            # JSONとしてパースするためのクリーニング処理
            # Geminiは時々Markdownのコードブロック(```json ... ```)を含めて返すため、それを除去します
            cleaned_json = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_json)

        except json.JSONDecodeError as e:
            # JSONパースエラーの場合
            raw_text = response.text if 'response' in locals() else "Unknown"
            error_message = f"JSON parse error: {e}. Raw response: {raw_text}"
            logger.error(error_message)
            return {"action": "error", "message": error_message}
        except Exception as e:
            # その他のAPIエラーなど
            error_message = f"Gemini API error: {e}"
            logger.error(error_message)
            return {"action": "error", "message": error_message}

    async def generate_notion_command(self, user_utterance: str, current_date: str) -> Dict[str, Any]:
        """
        ユーザーの発言からNotion操作コマンドを生成します。
        """
        full_prompt = self._build_command_prompt(user_utterance, current_date)
        return await self._generate_content_async(full_prompt)

    async def fix_notion_command(self, user_utterance: str, current_date: str, previous_json: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """
        エラーが発生したNotion操作コマンドを修正します。
        """
        base_prompt = self._build_command_prompt(user_utterance, current_date)

        # 修正指示を追加
        fix_instruction = f"""

### 修正指示:
前回のJSON生成で以下のエラーが発生しました。
エラーメッセージ: {error_message}
前回生成したJSON: {json.dumps(previous_json, ensure_ascii=False)}

上記のエラー原因を分析し、正しいJSONコマンドを再生成してください。
特に、プロパティ名や値の型、必須フィールドが正しいか確認してください。
"""
        full_prompt = base_prompt + fix_instruction
        return await self._generate_content_async(full_prompt)

    async def generate_final_response(self, user_utterance: str, tool_result: str) -> str:
        """
        ツールの実行結果に基づいて、最終的な応答を生成します。
        """
        prompt = self.response_prompt_template.replace("{user_utterance}", user_utterance)
        prompt = prompt.replace("{tool_result}", tool_result)

        logger.info(f"Sending final response prompt to Gemini:\n{prompt}")

        try:
            model = self._get_model()
            # 'Event loop is closed' エラー回避のため、同期メソッドをスレッドで実行する
            response = await asyncio.to_thread(model.generate_content, prompt)

            logger.info(f"Received final response from Gemini:\n{response.text}")

            return response.text
        except Exception as e:
            logger.error(f"Gemini API response generation error: {e}")
            return f"Gemini API response generation error: {e}"
