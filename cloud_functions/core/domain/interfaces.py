from abc import ABC, abstractmethod
from typing import Dict, Any, Union

class ILanguageModel(ABC):
    """
    言語モデルのインターフェース定義。
    Core層に位置し、具体的なLLMの実装（Geminiなど）に依存しない契約を定義します。
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
    async def fix_notion_command(self, user_utterance: str, current_date: str, previous_json: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """
        エラーが発生したNotion操作コマンドを修正します。

        Args:
            user_utterance (str): ユーザーの発言
            current_date (str): 現在の日付
            previous_json (Dict[str, Any]): 前回生成したJSON
            error_message (str): 発生したエラーメッセージ

        Returns:
            Dict[str, Any]: 修正されたコマンド情報（JSON）
        """
        pass

    @abstractmethod
    async def generate_final_response(self, user_utterance: str, tool_result: Union[str, Dict[str, Any]]) -> str:
        """
        ツールの実行結果に基づいて、最終的な応答を生成します。

        Args:
            user_utterance (str): ユーザーの発言
            tool_result (Union[str, Dict[str, Any]]): ツール実行結果（文字列または辞書）

        Returns:
            str: 生成された応答テキスト
        """
        pass


class INotionRepository(ABC):
    """
    Notionリポジトリのインターフェース定義。
    Core層に位置し、具体的なNotion APIクライアントに依存しない契約を定義します。
    """

    @abstractmethod
    def execute_tool(self, action: str, args: Dict[str, Any]) -> Any:
        """
        指定されたアクションと引数でNotionツールを実行します。

        Args:
            action (str): アクション名
            args (Dict[str, Any]): パラメータ

        Returns:
            Any: 実行結果（JSON文字列または辞書など）
        """
        pass
