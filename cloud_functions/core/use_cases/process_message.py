from ..domain.interfaces import ILanguageModel, INotionRepository, ISessionRepository
from ..config import SESSION_HISTORY_LIMIT_MINUTES
from ..logging_config import setup_logger
import asyncio
from typing import Dict, Any

logger = setup_logger(__name__)

class ProcessMessageUseCase:
    """
    ユーザーメッセージを処理するビジネスロジック（ユースケース）。
    3ステップの思考プロセス（DB選択→ツール生成→応答生成）を実装します。
    """

    def __init__(self, language_model: ILanguageModel, notion_repository: INotionRepository, session_repository: ISessionRepository):
        self.language_model = language_model
        self.notion_repository = notion_repository
        self.session_repository = session_repository
        # NotionAdapterが持つDBスキーマ情報を取得しておく
        self.db_schemas = getattr(notion_repository, 'notion_database_mapping', {})

    async def execute(self, user_utterance: str, current_date: str, session_id: str = "default") -> str:
        try:
            # セッション履歴を取得
            history = self.session_repository.get_recent_history(session_id, limit_minutes=SESSION_HISTORY_LIMIT_MINUTES)

            # --- ステップ1: データベース選択 ---
            selected_db_names = await self.language_model.select_databases(
                user_utterance, current_date, history
            )

            if not selected_db_names:
                # 関連するDBがない場合、通常のチャット応答を試みる
                logger.info("No relevant databases selected. Generating a simple chat response.")
                # generate_responseにツール結果なしで渡して、雑談応答させる
                final_response = await self.language_model.generate_response(user_utterance, [], history)
                self.session_repository.add_interaction(session_id, user_utterance, final_response)
                return final_response

            # --- ステップ2: ツールコール生成 & 実行 ---
            all_tool_results = []

            # 利用可能なツール関数を辞書としてマッピング
            available_tools = {
                "search_database": self.notion_repository.search_database,
                "create_page": self.notion_repository.create_page,
                "update_page": self.notion_repository.update_page,
                "append_block": self.notion_repository.append_block,
            }

            # 選択された各DBに対してツールコールを生成・実行
            for db_name in selected_db_names:
                single_db_schema = self.db_schemas.get(db_name)
                if not single_db_schema:
                    logger.warning(f"Schema for database '{db_name}' not found. Skipping.")
                    continue

                tool_calls = await self.language_model.generate_tool_calls(
                    user_utterance,
                    current_date,
                    list(available_tools.values()),
                    single_db_schema,
                    history
                )

                # 生成されたツールコールを非同期で実行
                tasks = []
                for call in tool_calls:
                    tool_name = call.get("name")
                    tool_args = call.get("args", {})
                    if tool_name in available_tools:
                        # asyncio.to_threadを使って同期関数を非同期に実行
                        task = asyncio.to_thread(available_tools[tool_name], **tool_args)
                        tasks.append((tool_name, task))

                # asyncio.gatherで並列実行し、結果を収集
                executed_results = await asyncio.gather(*(task for _, task in tasks))

                for (tool_name, _), result in zip(tasks, executed_results):
                    all_tool_results.append({"name": tool_name, "result": result})

            # --- ステップ3: 最終応答生成 ---
            final_response = await self.language_model.generate_response(
                user_utterance,
                all_tool_results,
                history
            )

            # 会話を保存
            self.session_repository.add_interaction(session_id, user_utterance, final_response)

            return final_response

        except Exception as e:
            logger.error(f"Error in ProcessMessageUseCase: {e}", exc_info=True)
            raise
