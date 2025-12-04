from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class ILanguageModel(ABC):
    """
    言語モデル(LLM)のインターフェース。
    外部AIサービスへのアダプターはこのインターフェースを実装する必要があります。
    """

    @abstractmethod
    async def generate_notion_command(self, user_utterance: str, current_date: str) -> Dict[str, Any]:
        """
        ユーザーの発言からNotion操作コマンドを生成します。

        Args:
            user_utterance (str): ユーザーの発言
            current_date (str): 現在の日付

        Returns:
            Dict[str, Any]: 解析されたコマンド情報（JSON）
        """
        pass

    @abstractmethod
    async def generate_final_response(self, user_utterance: str, tool_result: str) -> str:
        """
        ツールの実行結果に基づいて、最終的な応答を生成します。

        Args:
            user_utterance (str): ユーザーの発言
            tool_result (str): ツール実行結果

        Returns:
            str: 生成された応答テキスト
        """
        pass


class INotionRepository(ABC):
    """
    Notionリポジトリのインターフェース。
    Notion操作を行うアダプターはこのインターフェースを実装する必要があります。
    """

    @abstractmethod
    def execute_tool(self, action: str, args: Dict[str, Any]) -> str:
        """
        Notionに対する操作を実行します。

        Args:
            action (str): アクション名 (create_page, append_block, etc)
            args (Dict[str, Any]): アクションに必要なパラメータ

        Returns:
            str: 実行結果メッセージ
        """
        pass
