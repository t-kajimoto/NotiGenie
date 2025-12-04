import os
import json
import asyncio
import logging
import sys
import google.generativeai as genai
from typing import Dict, Any, List, Callable
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

    def __init__(self, system_instruction_template: str, notion_database_mapping: dict):
        """
        初期化処理。

        Args:
            system_instruction_template (str): システムプロンプト（インストラクション）。
            notion_database_mapping (dict): Notionデータベースの定義情報（プロンプトに埋め込むため）。
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        genai.configure(api_key=api_key)

        self.system_instruction_template = system_instruction_template
        self.notion_database_mapping = notion_database_mapping

    def _build_system_instruction(self, current_date: str) -> str:
        """
        システムプロンプトを構築します。
        """
        database_descriptions = ""
        for db_name, db_info in self.notion_database_mapping.items():
            title = db_info.get('title', db_name)
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

        instruction = self.system_instruction_template.replace("{database_descriptions}", database_descriptions)
        instruction = instruction.replace("{current_date}", current_date)
        return instruction

    def _get_model(self, tools: List[Callable], system_instruction: str):
        """
        GenerativeModelのインスタンスを生成して返します。
        """
        return genai.GenerativeModel(
            model_name='gemini-2.0-flash-lite',
            tools=tools,
            system_instruction=system_instruction
        )

    async def chat_with_tools(self, user_utterance: str, current_date: str, tools: List[Callable]) -> str:
        """
        ツールを使用してユーザーと会話を行い、最終的な応答を生成します。
        """
        system_instruction = self._build_system_instruction(current_date)
        model = self._get_model(tools, system_instruction)

        logger.info(f"Starting chat with tools. User Utterance: {user_utterance}")

        # 'Event loop is closed' エラー回避のため、同期メソッドをスレッドで実行
        # Automatic Function Callingは start_chat(enable_automatic_function_calling=True) で有効化し、
        # send_message を呼び出すと自動でループする。

        def _run_chat():
            chat = model.start_chat(enable_automatic_function_calling=True)
            response = chat.send_message(user_utterance)
            return response.text

        try:
            response_text = await asyncio.to_thread(_run_chat)
            logger.info(f"Received response from Gemini:\n{response_text}")
            return response_text
        except Exception as e:
            msg = f"Gemini API error in chat_with_tools: {e}"
            logger.error(msg)
            return f"申し訳ありません、エラーが発生しました: {e}"
