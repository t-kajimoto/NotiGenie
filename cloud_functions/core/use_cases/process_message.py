from ..domain.interfaces import ILanguageModel, INotionRepository, ISessionRepository
from ..config import SESSION_HISTORY_LIMIT_MINUTES
from ..logging_config import setup_logger, log_oneline
import asyncio
from typing import Dict, Any, List
from google.genai import types

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
            # [INPUT] ユーザーメッセージと処理コンテキストを記録
            logger.info(f"[INPUT] user_utterance={log_oneline(user_utterance)}, session_id={session_id}, date={current_date}")

            # ヘルプ機能: 特定のキーワードでヘルプメッセージを返す
            if user_utterance.strip().lower() in ["help", "ヘルプ", "へるぷ"]:
                logger.info("Help keyword detected. Returning help message.")
                return self.help_message

            # セッション履歴を取得
            history = self.session_repository.get_recent_history(session_id, limit_minutes=SESSION_HISTORY_LIMIT_MINUTES)
            
            # [ Round 4 ] ノイズ削減のため、履歴を直近10件に制限
            if len(history) > 10:
                history = history[-10:]
                
            logger.info(f"[HISTORY] count={len(history)}")

            # --- ステップ1: 調査 (Research) ---
            # Gemini 2.5の制限を回避するため、Notionツール生成の前にGoogle検索で情報を収集します。
            research_results = await self.language_model.perform_research(
                user_utterance, current_date, history
            )
            logger.info(f"[RESEARCH] result={log_oneline(research_results)}")

            # --- ステップ2: ツールコール生成 & 実行 (Multi-turn Loop) ---
            all_tool_results = []
            current_turn_history = []
            
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

            MAX_TURNS = 3
            for turn in range(MAX_TURNS):
                logger.info(f"[TURN {turn + 1}/{MAX_TURNS}] Generating tool calls...")
                
                tool_calls = await self.language_model.generate_tool_calls(
                    user_utterance,
                    current_date,
                    list(available_tools.values()),
                    single_db_schema,
                    history,
                    research_results=research_results,
                    current_turn_history=current_turn_history
                )
                logger.info(f"[TURN {turn + 1}] calls={tool_calls}")

                if not tool_calls:
                    logger.info(f"[TURN {turn + 1}] No tool calls generated. Breaking loop.")
                    break

                # 生成されたツールコールを非同期で実行
                tasks = []
                for call in tool_calls:
                    tool_name = call.get("name")
                    tool_args = call.get("args", {})
                    if tool_name in available_tools:
                        # [Round 9] update_page に database_name を付与
                        if tool_name == "update_page":
                            tool_args["database_name"] = "master_db"
                        task = asyncio.to_thread(available_tools[tool_name], **tool_args)
                        tasks.append((tool_name, task))

                # asyncio.gatherで並列実行し、結果を収集
                executed_results = await asyncio.gather(*(task for _, task in tasks))

                # 今回のターンの結果を収集
                turn_results = []
                for (tool_name, _), result in zip(tasks, executed_results):
                    turn_results.append({"name": tool_name, "result": result})
                    all_tool_results.append({"name": tool_name, "result": result}) # 全体履歴にも追加
                    
                    if isinstance(result, dict) and "error" in result:
                        logger.warning(f"[TOOL_ERROR] tool={tool_name}, error={result['error']}")

                logger.info(f"[TURN {turn + 1}] results={log_oneline(str(turn_results), max_length=500)}")

                # current_turn_history を更新
                # 1. Model's tool calls
                model_parts = []
                for tc in tool_calls:
                    model_parts.append({"function_call": {"name": tc["name"], "args": tc["args"]}})
                current_turn_history.append({"role": "model", "parts": model_parts})

                # 2. Function responses
                function_parts = []
                for tr in turn_results:
                    function_parts.append({
                        "function_response": {
                            "name": tr["name"],
                            "response": {"content": tr["result"]} 
                        }
                    })
                current_turn_history.append({"role": "function", "parts": function_parts})

            # --- ステップ3: 最終応答生成 ---
            logger.info("Step 3: Generating final response...")
            
            # [Round 9] Step 3 への転送時にツール定義も渡す (UNEXPECTED_TOOL_CALL 回避のため)
            # generate_tool_calls が内部で構築しているものと同じ定義を取得する必要がある
            # 現状は adapter 内で構築されているため、ダミーではなく実際の定義を渡せるように adapter を改善予定
            # 一旦、types.Tool(function_declarations=...) の形で渡せるようにする
            final_response = await self.language_model.generate_response(
                user_utterance,
                all_tool_results,
                history,
                current_turn_history=current_turn_history,
                research_results=research_results,
                tools=None # 後で GeminiAdapter 側で全ツールを自動適用するように更に改善可能
            )

            logger.info(f"[RESPONSE] text={log_oneline(final_response)}")

            # 会話を保存
            self.session_repository.add_interaction(session_id, user_utterance, final_response)

            return final_response

        except Exception as e:
            logger.error(f"Error in ProcessMessageUseCase: {e}", exc_info=True)
            raise
