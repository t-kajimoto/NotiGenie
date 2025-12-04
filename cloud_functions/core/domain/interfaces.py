from abc import ABC, abstractmethod
from typing import Dict, Any, Union

class ILanguageModel(ABC):
    """
    言語モデルのインターフェース定義。
    Core層に位置し、具体的なLLMの実装（Geminiなど）に依存しない契約を定義します。
    """
    @abstractmethod
    async def generate_notion_command(self, user_utterance: str, current_date: str) -> Dict[str, Any]:
        """ユーザーの発言からNotion操作コマンドを生成します。"""
        pass

    @abstractmethod
    async def generate_final_response(self, user_utterance: str, tool_result: str) -> str:
        """ツールの実行結果に基づいて、最終的な応答を生成します。"""
        pass


class INotionRepository(ABC):
    """
    Notionリポジトリのインターフェース定義。
    Core層に位置し、具体的なNotion APIクライアントに依存しない契約を定義します。
    """
    @abstractmethod
    def execute_tool(self, action: str, args: Dict[str, Any]) -> Any:
        """指定されたアクションと引数でNotionツールを実行します。"""
        pass
