from ..domain.interfaces import ILanguageModel, INotionRepository


class ProcessMessageUseCase:
    """
    ユーザーメッセージを処理するユースケース。

    Clean Architectureにおける「Use Cases」層に位置します。
    具体的なフレームワークや外部APIに依存せず、純粋なビジネスロジック（アプリケーションの振る舞い）を記述します。

    処理フロー:
    1. 言語モデルを使用してユーザーの意図（Notionコマンド）を解析する。
    2. 解析されたコマンドに基づいてNotionリポジトリを操作する。
    3. 操作結果を言語モデルに渡し、最終的な応答を生成する。
    """

    def __init__(self, language_model: ILanguageModel, notion_repository: INotionRepository):
        """
        コンストラクタ。Dependency Injection（依存性の注入）パターンを使用しています。
        具体的なクラス（GeminiAgentなど）ではなく、インターフェース（ILanguageModel）に依存することで、
        コンポーネント間の結合度を下げ、テストや交換を容易にします。

        Args:
            language_model (ILanguageModel): 言語モデルのインターフェース実装。
            notion_repository (INotionRepository): Notionリポジトリのインターフェース実装。
        """
        self.language_model = language_model
        self.notion_repository = notion_repository

    async def execute(self, user_utterance: str, current_date: str) -> str:
        """
        ユースケースを実行します。

        Args:
            user_utterance (str): ユーザーの発言。
            current_date (str): 現在の日付（コンテキストとして使用）。

        Returns:
            str: 最終的なユーザーへの応答テキスト。
        """
        try:
            # 1. 意図解析 (Intent Analysis)
            # LLMを使用して、自然言語を構造化データ(JSON)に変換します。
            # awaitキーワードは、非同期処理（結果が返ってくるまで待機する処理）を表します。
            command = await self.language_model.generate_notion_command(user_utterance, current_date)

            # 2. ツール実行 (Execute Tool)
            # 解析されたコマンドに基づいて、実際に外部システム(Notion)を操作します。
            if command.get("action") == "error":
                # 生成段階でエラーがあった場合
                tool_result = command.get("message", "Unknown error")
            else:
                action = command.get("action")
                # アクション以外のすべてのキーを引数として渡します
                args = {k: v for k, v in command.items() if k != "action"}

                # 同期メソッドとして定義されている場合でも、必要に応じて非同期ラッパー内で実行することがあります。
                # 現状のNotionHandlerは同期的なのでそのまま呼び出します。
                tool_result = self.notion_repository.execute_tool(action, args)

            # 3. 最終応答生成 (Generate Final Response)
            # ツールの実行結果をユーザーに分かりやすい言葉で伝えます。
            final_response = await self.language_model.generate_final_response(user_utterance, tool_result)

            return final_response

        except Exception as e:
            # 予期せぬエラーが発生した場合のフォールバック
            # ログを出力し、ユーザーにはエラーであることを伝えます。
            print(f"Error in ProcessMessageUseCase: {e}")
            return f"申し訳ありません。処理中にエラーが発生しました: {str(e)}"
