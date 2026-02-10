from ..domain.interfaces import ILanguageModel, INotionRepository, ISessionRepository
from ..config import SESSION_HISTORY_LIMIT_MINUTES
from ..logging_config import setup_logger
import asyncio
from typing import Dict, Any

logger = setup_logger(__name__)

class ProcessMessageUseCase:
    """
    ユーザーメッセージを処理するビジネスロジック（ユースケース）。
    2ステップの思考プロセス（ツール生成→応答生成）を実装します。
    統合データベース (master_db) を使用します。
    """

    def __init__(self, language_model: ILanguageModel, notion_repository: INotionRepository, session_repository: ISessionRepository, help_message: str = ""):
        self.language_model = language_model
        self.notion_repository = notion_repository
        self.session_repository = session_repository
        self.help_message = help_message
        # NotionAdapterが持つDBスキーマ情報を取得しておく
        self.db_schemas = getattr(notion_repository, 'notion_database_mapping', {})

    async def execute(self, user_utterance: str, current_date: str, session_id: str = "default") -> str:
        try:
            # ヘルプ機能: 特定のキーワードでヘルプメッセージを返す
            if user_utterance.strip().lower() in ["help", "ヘルプ", "へるぷ"]:
                logger.info("Help keyword detected. Returning help message.")
                return self.help_message

            # セッション履歴を取得
            history = self.session_repository.get_recent_history(session_id, limit_minutes=SESSION_HISTORY_LIMIT_MINUTES)

            # --- ステップ1: 調査 (Research) ---
            # Gemini 2.5の制限を回避するため、Notionツール生成の前にGoogle検索で情報を収集します。
            research_results = await self.language_model.perform_research(
                user_utterance, current_date, history
            )

            # --- ステップ2: ツールコール生成 & 実行 ---
            all_tool_results = []

            # 利用可能なツール関数を辞書としてマッピング
            available_tools = {
                "search_database": self.notion_repository.search_database,
                "create_page": self.notion_repository.create_page,
                "update_page": self.notion_repository.update_page,
                "append_block": self.notion_repository.append_block,
            }

            # 統合データベース (master_db) のスキーマを取得
            single_db_schema = self.db_schemas.get("master_db")
            if not single_db_schema:
                logger.error("Schema for 'master_db' not found in Firestore.")
                raise ValueError("master_db schema not found")

            tool_calls = await self.language_model.generate_tool_calls(
                user_utterance,
                current_date,
                list(available_tools.values()),
                single_db_schema,
                history,
                research_results=research_results
            )

            # 生成されたツールコールを非同期で実行
            tasks = []
            for call in tool_calls:
                tool_name = call.get("name")
                tool_args = call.get("args", {})
                if tool_name in available_tools:
                    task = asyncio.to_thread(available_tools[tool_name], **tool_args)
                    tasks.append((tool_name, task))

            # asyncio.gatherで並列実行し、結果を収集
            executed_results = await asyncio.gather(*(task for _, task in tasks))

            for (tool_name, _), result in zip(tasks, executed_results):
                all_tool_results.append({"name": tool_name, "result": result})

            # --- ステップ3: 最終応答生成 ---
            # 検索ツール(grounding)が使われた場合、その結果も含めて応答生成される
            logger.info("Step 3: Generating final response with Autogrounding support...")
            
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
