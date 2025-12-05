from ..domain.interfaces import ILanguageModel, INotionRepository, ISessionRepository
import logging

logger = logging.getLogger(__name__)

class ProcessMessageUseCase:
    """
    ユーザーメッセージを処理するビジネスロジック（ユースケース）。

    何をやっているか:
    ユーザーの発言を受け取り、Language Model（Gemini）とNotion Repository（Notion API）を
    連携させて、適切な応答やアクションを実行します。

    Clean Architectureにおける「Use Case (Interactor)」層に位置します。
    具体的なAPI（Gemini APIやNotion API）の実装詳細は知らず、
    抽象インターフェース（ILanguageModel, INotionRepository）のみに依存します。
    """

    def __init__(self, language_model: ILanguageModel, notion_repository: INotionRepository, session_repository: ISessionRepository):
        """
        コンストラクタ。依存関係を注入します。

        Args:
            language_model (ILanguageModel): 言語モデルへのインターフェース。
            notion_repository (INotionRepository): Notion操作へのインターフェース。
            session_repository (ISessionRepository): セッション履歴へのインターフェース。
        """
        self.language_model = language_model
        self.notion_repository = notion_repository
        self.session_repository = session_repository

    async def execute(self, user_utterance: str, current_date: str, session_id: str = "default") -> str:
        """
        ユースケースを実行します。

        何をやっているか:
        1. AIが使用可能なツール（Notion操作関数）のリストを定義します。
        2. セッション履歴を取得します。
        3. `language_model.chat_with_tools` を呼び出し、ユーザーの発言、ツール、履歴を渡します。
        4. AIが自律的にツールを選択・実行し、その結果を踏まえた最終的な回答を返します。
        5. 新しい会話のペアを履歴に保存します。

        Args:
            user_utterance (str): ユーザーの発言テキスト。
            current_date (str): 現在の日付文字列（YYYY-MM-DD）。
            session_id (str): セッションID（LINEユーザーIDなど）。

        Returns:
            str: ユーザーへの最終的な応答メッセージ。
        """
        try:
            # 使用するツール（関数）を定義
            # NotionAdapterのメソッドを直接渡すことで、AIがこれらを呼び出せるようになります。
            # Automatic Function Calling の仕組みにより、Geminiが必要に応じてこれらを実行します。
            tools = [
                self.notion_repository.search_database,
                self.notion_repository.create_page,
                self.notion_repository.update_page,
                self.notion_repository.append_block
            ]

            # セッション履歴を取得（過去5分以内）
            history = self.session_repository.get_recent_history(session_id, limit_minutes=5)

            # LLMに処理を委譲
            # ここが処理の中核です。ユーザーの意図理解 -> ツール実行判断 -> ツール実行 -> 結果解釈 -> 応答生成
            # という一連の流れが chat_with_tools 内部で行われます。
            final_response = await self.language_model.chat_with_tools(
                user_utterance,
                current_date,
                tools,
                history
            )

            # 会話を保存
            self.session_repository.add_interaction(session_id, user_utterance, final_response)

            return final_response

        except Exception as e:
            # ユースケースレベルでのエラーハンドリング
            print(f"Error in ProcessMessageUseCase: {e}")
            # エラーは呼び出し元（Controller）に伝播させ、そこで適切なエラーレスポンスを返させます
            raise
