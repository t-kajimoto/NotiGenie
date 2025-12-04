from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable

class ILanguageModel(ABC):
    """
    言語モデルのインターフェース定義。
    Core層に位置し、具体的なLLMの実装（Geminiなど）に依存しない契約を定義します。
    """

    @abstractmethod
    async def chat_with_tools(self, user_utterance: str, current_date: str, tools: List[Callable]) -> str:
        """
        ツールを使用してユーザーと会話を行い、最終的な応答を生成します。
        Automatic Function Calling を使用することを想定しています。

        Args:
            user_utterance (str): ユーザーの発言
            current_date (str): 現在の日付（システムプロンプト等で使用）
            tools (List[Callable]): 使用可能なツールのリスト（関数）

        Returns:
            str: 最終的な応答テキスト
        """
        pass

class INotionRepository(ABC):
    """
    Notionリポジトリのインターフェース定義。
    Core層に位置し、具体的なNotion APIクライアントに依存しない契約を定義します。
    """

    @abstractmethod
    def search_database(self, query: str, database_name: Optional[str] = None) -> str:
        """
        データベースからページを検索します。

        Args:
            query (str): 検索キーワード
            database_name (Optional[str]): データベース名（指定がない場合は全データベース、または適切なものを選択）

        Returns:
            str: 検索結果のJSON文字列（LLMに渡すため）
        """
        pass

    @abstractmethod
    def create_page(self, database_name: str, title: str, properties: Optional[Dict[str, Any]] = None) -> str:
        """
        データベースに新しいページを作成します。

        Args:
            database_name (str): データベース名
            title (str): ページのタイトル
            properties (Optional[Dict[str, Any]]): その他のプロパティ

        Returns:
            str: 作成結果のJSON文字列
        """
        pass

    @abstractmethod
    def update_page(self, page_id: str, properties: Dict[str, Any]) -> str:
        """
        ページを更新します。

        Args:
            page_id (str): ページID
            properties (Dict[str, Any]): 更新するプロパティ

        Returns:
            str: 更新結果のJSON文字列
        """
        pass

    @abstractmethod
    def append_block(self, block_id: str, children: List[Dict[str, Any]]) -> str:
        """
        ブロックに子ブロックを追加します。

        Args:
            block_id (str): 親ブロックID
            children (List[Dict[str, Any]]): 追加する子ブロックのリスト

        Returns:
             str: 追加結果のJSON文字列
        """
        pass
