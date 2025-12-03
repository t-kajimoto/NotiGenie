import os
import google.generativeai as genai
import json

class GeminiAgent:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

        # TODO: Load prompts and mapping from config or env
        self.command_prompt_template = """
        You are a helpful assistant. Parse the user's intent and extract parameters for Notion.
        User said: {user_utterance}
        Current date: {current_date}

        Available Databases:
        {database_descriptions}

        Output JSON only.
        """
        self.response_prompt_template = """
        Generate a response for the user based on the tool execution result.
        User said: {user_utterance}
        Tool result: {tool_result}
        """
        self.notion_database_mapping = {}

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
            # response.text might not exist if generation failed completely, but here we assume it returned something unparseable
            error_message = f"JSON parse error: {e}"
            return {"action": "error", "message": error_message}
        except Exception as e:
            error_message = f"Gemini API error: {e}"
            return {"action": "error", "message": error_message}

    async def generate_final_response(self, user_utterance: str, tool_result: str) -> str:
        prompt = self.response_prompt_template.replace("{user_utterance}", user_utterance)
        prompt = prompt.replace("{tool_result}", tool_result)

        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            error_message = f"Gemini API response generation error: {e}"
            return error_message
