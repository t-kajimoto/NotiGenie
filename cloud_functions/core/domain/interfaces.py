from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Union

class ILanguageModel(ABC):
    """
    言語モデルのインターフェース定義。
    Core層に位置し、具体的なLLMの実装（Geminiなど）に依存しない契約を定義します。
    """

    @abstractmethod
    async def perform_research(
        self,
        user_utterance: str,
        current_date: str,
        history: List[Dict[str, Any]] = None
    ) -> str:
        """
        ユーザーの発言に基づいて、Google検索などの外部情報を調査します。
        
        Args:
            user_utterance (str): ユーザーの発言
            current_date (str): 現在の日付
            history (List[Dict[str, Any]]): 過去の会話履歴
            
        Returns:
            str: 調査結果の要約テキスト。調査が不要な場合は空文字列を返します。
        """
        pass

    @abstractmethod
    async def generate_tool_calls(
        self,
        user_utterance: str,
        current_date: str,
        tools: List[Callable],
        single_db_schema: Dict[str, Any],
        history: List[Dict[str, Any]] = None,
        research_results: str = ""
    ) -> List[Dict[str, Any]]:
        """
        単一のDBスキーマをコンテキストとして、実行すべきツールコール（関数と引数）を生成します。

        Args:
            user_utterance (str): ユーザーの発言
            current_date (str): 現在の日付
            tools (List[Callable]): 使用可能なツールのリスト
            single_db_schema (Dict[str, Any]): 対象となる単一DBのスキーマ情報
            history (List[Dict[str, Any]]): 過去の会話履歴
            research_results (str): 事前に調査した外部情報の要約

        Returns:
            List[Dict[str, Any]]: ツールコールのリスト。例: [{'name': 'search_database', 'args': {'query': '...'} }]
        """
        pass

    @abstractmethod
    async def generate_response(
        self,
        user_utterance: str,
        tool_results: List[Dict[str, Any]],
        history: List[Dict[str, Any]] = None
    ) -> str:
        """
        ツール実行結果をコンテキストとして、ユーザーへの最終的な応答を生成します。

        Args:
            user_utterance (str): ユーザーの元の発言
            tool_results (List[Dict[str, Any]]): ツールの実行結果
            history (List[Dict[str, Any]]): 過去の会話履歴

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
    def search_database(self, query: Optional[str] = None, database_name: Optional[str] = None, filter_conditions: Optional[str] = None) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        データベースからページを検索します。

        Args:
            query (Optional[str]): 検索キーワード（タイトル部分一致）
            database_name (Optional[str]): データベース名（指定がない場合は全データベース検索）
            filter_conditions (Optional[str]): JSON形式の絞り込み条件（例: '{"Status": "Done"}'）

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

class ISessionRepository(ABC):
    """
    会話セッションの履歴を管理するリポジトリのインターフェース定義。
    Core層に位置します。
    """

    @abstractmethod
    def get_recent_history(self, session_id: str, limit_minutes: int) -> List[Dict[str, Any]]:
        """
        指定されたセッションIDの最近の会話履歴を取得します。
        指定された時間（limit_minutes）よりも古い履歴は無視または破棄されます。

        Args:
            session_id (str): セッションID（例: LINE User ID）
            limit_minutes (int): 履歴を有効とする時間（分）。これより古い会話は含めない。

        Returns:
            List[Dict[str, Any]]: 会話履歴のリスト。各要素はGemini API互換の形式。
                                  例: [{'role': 'user', 'parts': ['msg']}, {'role': 'model', 'parts': ['msg']}]
        """
        pass

    @abstractmethod
    def add_interaction(self, session_id: str, user_message: str, model_response: str):
        """
        新しいユーザー発言とAIの応答を履歴に追加します。

        Args:
            session_id (str): セッションID
            user_message (str): ユーザーの発言
            model_response (str): AIの応答
        """
        pass
