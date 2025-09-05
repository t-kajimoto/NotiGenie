
import os
import google.generativeai as genai
import json
from domain.use_cases.interpret_and_execute import IIntentAndResponseGateway

class GeminiGateway(IIntentAndResponseGateway):
    def __init__(self, api_key: str, command_prompt_template: str, response_prompt_template: str, notion_database_mapping: dict):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.command_prompt_template = command_prompt_template
        self.response_prompt_template = response_prompt_template
        self.notion_database_mapping = notion_database_mapping

    async def generate_notion_command(self, user_utterance: str, current_date: str) -> dict:
        database_descriptions = ""
        for db_name, db_info in self.notion_database_mapping.items():
            database_descriptions += f"- {db_name}: {db_info['description']}\n"

        full_prompt = self.command_prompt_template.replace("{database_descriptions}", database_descriptions)
        full_prompt = full_prompt.replace("{user_utterance}", user_utterance)
        full_prompt = full_prompt.replace("{current_date}", current_date)

        try:
            response = await self.model.generate_content_async(full_prompt)
            cleaned_json = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            error_message = f"JSONの解析に失敗しました: {e}\n受信したテキスト: {response.text if 'response' in locals() else 'N/A'}"
            return {"action": "error", "message": error_message}
        except Exception as e:
            error_message = f"Gemini API呼び出し中に予期せぬエラーが発生しました: {e}"
            return {"action": "error", "message": error_message}

    async def generate_final_response(self, user_utterance: str, tool_result: str) -> str:
        prompt = self.response_prompt_template.replace("{user_utterance}", user_utterance)
        prompt = prompt.replace("{tool_result}", tool_result)
        
        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            error_message = f"Gemini APIでの最終応答生成中にエラーが発生しました: {e}"
            return error_message


