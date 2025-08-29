
import os
import google.generativeai as genai
import json
from domain.use_cases.interpret_and_execute import IIntentAndResponseGateway

class GeminiGateway(IIntentAndResponseGateway):
    def __init__(self, api_key: str, prompt_template: str, notion_database_mapping: dict):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.prompt_template = prompt_template
        self.notion_database_mapping = notion_database_mapping

    def generate_notion_command(self, user_utterance: str) -> dict:
        database_descriptions = ""
        for db_name, db_info in self.notion_database_mapping.items():
            database_descriptions += f"- {db_name}: {db_info['description']}\n"

        full_prompt = self.prompt_template.replace("{database_descriptions}", database_descriptions)
        full_prompt = full_prompt.replace("{user_utterance}", user_utterance)

        response = self.model.generate_content(full_prompt)
        cleaned_json = response.text.strip().replace("```json", "").replace("```", "").strip()
        
        try:
            return json.loads(cleaned_json)
        except json.JSONDecodeError:
            return {"action": "error", "message": "JSONの解析に失敗しました。"}

    def generate_final_response(self, tool_result: str) -> str:
        prompt = f"Notionの操作結果は以下の通りです。この結果を元に、ユーザーへの応答メッセージを生成してください。\n\n{tool_result}"
        response = self.model.generate_content(prompt)
        return response.text
