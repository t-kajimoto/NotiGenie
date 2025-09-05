from domain.use_cases.interpret_and_execute import IIntentAndResponseGateway

class MockGeminiGateway(IIntentAndResponseGateway):
    def __init__(self):
        pass

    async def generate_notion_command(self, user_utterance: str) -> dict:
        # Hardcoded command data for testing "名前が親子丼" filter
        return {
            "action": "query_database",
            "database_name": "献立リスト", # Corrected database_name
            "filter_json": {
                "filter": {
                    "property": "名前",
                    "title": { # Changed from rich_text to title
                        "equals": "親子丼"
                    }
                }
            }
        }

    async def generate_final_response(self, tool_result: str) -> str:
        return f"Mock final response: {tool_result}"
