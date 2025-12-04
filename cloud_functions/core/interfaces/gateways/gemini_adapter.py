import os
import json
import google.generativeai as genai
from typing import Dict, Any
from ...domain.interfaces import ILanguageModel


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
        genai.configure(api_key=api_key)
        # モデルの指定（軽量で高速なflashモデルを使用）
        self.model = genai.GenerativeModel('gemini-2.0-flash-lite')

        self.command_prompt_template = command_prompt_template
        self.response_prompt_template = response_prompt_template
        self.notion_database_mapping = notion_database_mapping

    async def generate_notion_command(self, user_utterance: str, current_date: str) -> Dict[str, Any]:
        """
        ユーザーの発言からNotion操作コマンドを生成します。
        """
        # プロンプトの構築: データベース情報を動的に埋め込みます
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

        try:
            # 非同期でGemini APIを呼び出し
            response = await self.model.generate_content_async(full_prompt)

            # JSONとしてパースするためのクリーニング処理
            # Geminiは時々Markdownのコードブロック(```json ... ```)を含めて返すため、それを除去します
            cleaned_json = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_json)

        except json.JSONDecodeError as e:
            # JSONパースエラーの場合
            error_message = f"JSON parse error: {e}. Raw response: {response.text}"
            return {"action": "error", "message": error_message}
        except Exception as e:
            # その他のAPIエラーなど
            error_message = f"Gemini API error: {e}"
            return {"action": "error", "message": error_message}

    async def generate_final_response(self, user_utterance: str, tool_result: str) -> str:
        """
        ツールの実行結果に基づいて、最終的な応答を生成します。
        """
        prompt = self.response_prompt_template.replace("{user_utterance}", user_utterance)
        prompt = prompt.replace("{tool_result}", tool_result)

        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            return f"Gemini API response generation error: {e}"
