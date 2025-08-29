
from abc import ABC, abstractmethod

class IIntentAndResponseGateway(ABC):
    @abstractmethod
    def generate_notion_command(self, user_utterance: str) -> dict:
        pass

    @abstractmethod
    def generate_final_response(self, tool_result: str) -> str:
        pass

class INotionMCPGateway(ABC):
    @abstractmethod
    def execute_tool(self, action: str, args: dict) -> str:
        pass

class InterpretAndExecuteUseCase:
    def __init__(self, intent_and_response_gateway: IIntentAndResponseGateway, notion_mcp_gateway: INotionMCPGateway):
        self.intent_and_response_gateway = intent_and_response_gateway
        self.notion_mcp_gateway = notion_mcp_gateway

    def execute(self, user_utterance: str) -> str:
        # 1. コマンド生成
        command_data = self.intent_and_response_gateway.generate_notion_command(user_utterance)
        action = command_data.pop("action", None)
        args = command_data

        if not action or action == "error":
            return command_data.get("message", "申し訳ありませんが、理解できませんでした。")

        # 2. ツール実行
        tool_result = self.notion_mcp_gateway.execute_tool(action, args)

        # 3. 最終応答生成
        final_response = self.intent_and_response_gateway.generate_final_response(tool_result)

        return final_response
