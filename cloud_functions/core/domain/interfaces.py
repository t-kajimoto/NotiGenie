from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Union

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
    def search_database(self, query: str, database_name: Optional[str] = None) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        データベースからページを検索します。

        Args:
            query (str): 検索キーワード
            database_name (Optional[str]): データベース名（指定がない場合は全データベース、または適切なものを選択）

        Returns:
            Union[List[Dict[str, Any]], Dict[str, Any]]: 検索結果のリスト、またはエラー時の辞書。
            Clean Architectureの観点から、JSON文字列（Infrastructureの詳細）ではなく、
            Pythonのデータ構造（Domainに近い形式）を返します。
        """
        pass

    @abstractmethod
    def create_page(self, database_name: str, title: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        データベースに新しいページを作成します。

        Args:
            database_name (str): データベース名
            title (str): ページのタイトル
            properties (Optional[Dict[str, Any]]): その他のプロパティ

        Returns:
            Dict[str, Any]: 作成結果の辞書
        """
        pass

    @abstractmethod
    def update_page(self, page_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        ページを更新します。

        Args:
            page_id (str): ページID
            properties (Dict[str, Any]): 更新するプロパティ

        Returns:
            Dict[str, Any]: 更新結果の辞書
        """
        pass

    @abstractmethod
    def append_block(self, block_id: str, children: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        ブロックに子ブロックを追加します。

        Args:
            block_id (str): 親ブロックID
            children (List[Dict[str, Any]]): 追加する子ブロックのリスト

        Returns:
             Dict[str, Any]: 追加結果の辞書
        """
        pass
