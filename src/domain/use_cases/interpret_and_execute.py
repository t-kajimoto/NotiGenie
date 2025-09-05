
from abc import ABC, abstractmethod
import datetime

class IIntentAndResponseGateway(ABC):
    @abstractmethod
    async def generate_notion_command(self, user_utterance: str, current_date: str) -> dict:
        pass

    @abstractmethod
    async def generate_final_response(self, user_utterance: str, tool_result: str) -> str:
        pass

class INotionClientGateway(ABC):
    @abstractmethod
    async def execute_tool(self, action: str, args: dict) -> str:
        pass

class InterpretAndExecuteUseCase:
    def __init__(self, intent_and_response_gateway: IIntentAndResponseGateway, notion_client_gateway: INotionClientGateway):
        self.intent_and_response_gateway = intent_and_response_gateway
        self.notion_client_gateway = notion_client_gateway

    async def execute(self, user_utterance: str) -> str:
        # 1. コマンド生成
        # AIが「今日」などの相対的な日付表現を正確に解釈できるよう、プロンプトに今日の日付を渡す。
        today_str = datetime.date.today().isoformat()
        command_data = await self.intent_and_response_gateway.generate_notion_command(user_utterance, today_str)
        
        action = command_data.pop("action", None)
        # command_dataからactionキーを削除したものをargsとして渡す
        args = {k: v for k, v in command_data.items() if k != 'action'}

        if not action or action == "error":
            return command_data.get("message", "申し訳ありませんが、理解できませんでした。")

        # 2. ツール実行
        tool_result = await self.notion_client_gateway.execute_tool(action, args)

        # 3. 最終応答生成
        final_response = await self.intent_and_response_gateway.generate_final_response(user_utterance, tool_result)

        return final_response
