from core.domain.interfaces import ILanguageModel, INotionRepository


class ProcessMessageUseCase:
    """
    ユーザーメッセージを処理するユースケース。
    """

    def __init__(self, language_model: ILanguageModel, notion_repository: INotionRepository):
        self.language_model = language_model
        self.notion_repository = notion_repository

    async def execute(self, user_utterance: str, current_date: str) -> str:
        """
        ユースケースを実行します。
        Automatic Function Calling を使用して、LLMに自律的にツールを実行させます。
        """
        try:
            # 使用するツールを定義
            # NotionAdapterのメソッドを直接渡す
            tools = [
                self.notion_repository.search_database,
                self.notion_repository.create_page,
                self.notion_repository.update_page,
                self.notion_repository.append_block
            ]

            # LLMに処理を委譲
            final_response = await self.language_model.chat_with_tools(
                user_utterance,
                current_date,
                tools
            )

            return final_response

        except Exception as e:
            print(f"Error in ProcessMessageUseCase: {e}")
            raise
