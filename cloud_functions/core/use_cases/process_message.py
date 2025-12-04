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
            command = await self.language_model.generate_notion_command(user_utterance, current_date)

            # 2. ツール実行 (Execute Tool) とリトライ処理
            # 解析されたコマンドに基づいて、実際に外部システム(Notion)を操作します。
            # エラーが発生した場合は、Geminiに修正を依頼してリトライします（最大2回）。

            max_retries = 2
            tool_result = None

            for attempt in range(max_retries + 1):
                # エラー生成されていた場合は即座に結果とする（リトライしても意味がないため、あるいはGemini側の判断エラー）
                # ただし、JSONパースエラーなどの場合は fix_notion_command で直せる可能性もあるが、
                # 現状のGeminiAdapterは {"action": "error"} を返す実装なので、ここではループを抜ける。
                if command.get("action") == "error":
                    tool_result = command.get("message", "Unknown error")
                    break

                try:
                    action = command.get("action")
                    # アクション以外のすべてのキーを引数として渡します
                    args = {k: v for k, v in command.items() if k != "action"}

                    # 同期メソッドとして定義されている場合でも、必要に応じて非同期ラッパー内で実行することがあります。
                    # 現状のNotionHandlerは同期的なのでそのまま呼び出します。
                    tool_result = self.notion_repository.execute_tool(action, args)

                    # 成功したらループを抜ける
                    break

                except Exception as e:
                    # エラーが発生した場合
                    error_message = str(e)
                    print(f"Tool execution failed (Attempt {attempt + 1}/{max_retries + 1}): {error_message}")

                    if attempt < max_retries:
                        # リトライ可能な場合は、Geminiに修正を依頼
                        print("Requesting JSON fix from Gemini...")
                        command = await self.language_model.fix_notion_command(
                            user_utterance,
                            current_date,
                            command,
                            error_message
                        )
                    else:
                        # リトライ回数上限に達した場合は、エラーメッセージを結果とする
                        tool_result = f"Error: Failed to execute command after {max_retries + 1} attempts. Last error: {error_message}"

            # 3. 最終応答生成 (Generate Final Response)
            # ツールの実行結果をユーザーに分かりやすい言葉で伝えます。
            final_response = await self.language_model.generate_final_response(user_utterance, tool_result)

            return final_response

        except Exception as e:
            # 予期せぬエラーが発生した場合のフォールバック
            # ログを出力し、エラーを上位レイヤーに伝播させます。
            print(f"Error in ProcessMessageUseCase: {e}")
            raise
