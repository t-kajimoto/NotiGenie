import os
import json
import asyncio
import logging
import sys
import functools
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, FunctionDeclaration, Tool
from typing import Dict, Any, List, Callable, Optional
from ...domain.interfaces import ILanguageModel

# ---------------------------------------------------------------------------
# ロギング設定
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

class GeminiAdapter(ILanguageModel):
    """
    Gemini APIを使用したILanguageModelの実装クラス。
    3ステップの思考プロセス（DB選択→ツール生成→応答生成）を実装します。
    """
    def __init__(self, system_instruction_template: str, notion_database_mapping: dict):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        genai.configure(api_key=api_key)
        self.system_instruction_template = system_instruction_template
        self.notion_database_mapping = notion_database_mapping
        self.model_name = 'gemini-2.5-flash-lite'

    # ---------------------------------------------------------------------------
    # プロンプト構築メソッド群
    # ---------------------------------------------------------------------------
    def _build_db_selection_instruction(self, current_date: str) -> str:
        """【ステップ1: DB選択】用のシステムプロンプトを構築します。"""
        db_summaries = ""
        for db_name, db_info in self.notion_database_mapping.items():
            title = db_info.get('title', db_name)
            db_summaries += f"- {db_name} ({title}): {db_info['description']}\n"

        prompt = f"""ユーザーの質問に回答するために、どのNotionデータベースを使用すべきか判断してください。
本日付: {current_date}
利用可能なデータベース:
{db_summaries}
ユーザーの意図に最も関連性の高いデータベース名を `select_databases` ツールを使って返してください。関連するDBがない場合は空リストを返してください。"""
        return prompt

    def _build_tool_generation_instruction(self, current_date: str, single_db_schema: Dict[str, Any]) -> str:
        """【ステップ2: ツールコール生成】用のシステムプロンプトを構築します。"""
        db_name = single_db_schema.get('id')
        title = single_db_schema.get('title', db_name)
        properties_info = "\n  Properties:\n"
        for prop_name, prop_details in single_db_schema.get('properties', {}).items():
            prop_type = prop_details.get('type', 'unknown')
            options = ""
            if 'options' in prop_details:
                options = f" (Options: {', '.join(prop_details['options'])})"
            properties_info += f"  - {prop_name} ({prop_type}){options}\n"

        database_descriptions = f"- {db_name} ({title}): {single_db_schema['description']}{properties_info}\n"

        # テンプレートのプレースホルダーを置換
        instruction = self.system_instruction_template.replace("{database_descriptions}", database_descriptions)
        instruction = instruction.replace("{current_date}", current_date)
        
        # Groundingと新カラム対応の指示を追加
        instruction += """
Note for ToDo List:
1. "Deadline" (Date): Set a concrete date for sorting (e.g., "2月中" -> 2026-02-28).
2. "DisplayDate" (Text): Keep the user's original vague expression (e.g., "2月中", "来週").
3. "Memo" (RichText): If the task needs research (e.g., "date ideas", "restaurant"), use the 'google_search_retrieval' tool to find info and summarize it here.
4. "DoneDate" (Date): Only set this when marking a task as Done (check "完了ボタン"). Use today's date.
"""
        return instruction

    def _build_response_generation_instruction(self) -> str:
        """【ステップ3: 応答生成】用のシステムプロンプトを構築します。"""
        return "あなたは親切なアシスタントです。ユーザーの質問とツールの実行結果を元に、自然で分かりやすい日本語の文章で回答を生成してください。"

    # ---------------------------------------------------------------------------
    # 内部ヘルパーメソッド
    # ---------------------------------------------------------------------------
    def _sanitize_arg(self, arg: Any) -> Any:
        type_name = type(arg).__name__
        if type_name == 'MapComposite':
            return {k: self._sanitize_arg(v) for k, v in arg.items()}
        elif type_name == 'RepeatedComposite':
            return [self._sanitize_arg(v) for v in arg]
        elif isinstance(arg, dict):
            return {k: self._sanitize_arg(v) for k, v in arg.items()}
        elif isinstance(arg, list):
            return [self._sanitize_arg(v) for v in arg]
        return arg

    def _wrap_tool(self, tool: Callable) -> Callable:
        @functools.wraps(tool)
        def wrapper(*args, **kwargs):
            sanitized_args = [self._sanitize_arg(arg) for arg in args]
            sanitized_kwargs = {k: self._sanitize_arg(v) for k, v in kwargs.items()}
            return tool(*sanitized_args, **sanitized_kwargs)
        return wrapper

    async def _run_gemini_async(self, model: genai.GenerativeModel, prompt: Any, history: Optional[List[Dict[str, Any]]] = None):
        """Geminiの同期SDKを非同期で安全に呼び出すラッパー。"""
        def _run_chat():
            chat = model.start_chat(history=history or [])
            response = chat.send_message(prompt)
            return response
        try:
            return await asyncio.to_thread(_run_chat)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    # ---------------------------------------------------------------------------
    # ILanguageModel インターフェース実装
    # ---------------------------------------------------------------------------
    async def select_databases(self, user_utterance: str, current_date: str, history: List[Dict[str, Any]] = None) -> List[str]:
        system_instruction = self._build_db_selection_instruction(current_date)

        select_databases_tool = FunctionDeclaration(
            name="select_databases",
            description="ユーザーの質問に関連するNotionデータベースを選択する",
            parameters={
                "type": "object",
                "properties": {
                    "db_names": {
                        "type": "array",
                        "description": "関連するデータベース名のリスト",
                        "items": {"type": "string"}
                    }
                },
                "required": ["db_names"]
            }
        )

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction,
            tools=[select_databases_tool]
        )

        logger.info("Step 1: Selecting databases...")
        response = await self._run_gemini_async(model, user_utterance, history)

        selected_dbs = []
        # レスポンスのpartsから関数呼び出しを抽出する
        if hasattr(response, 'parts'):
            for part in response.parts:
                if fn := part.function_call:
                    if fn.name == "select_databases":
                        sanitized_args = self._sanitize_arg(fn.args)
                        selected_dbs.extend(sanitized_args.get("db_names", []))

        logger.info(f"Selected databases: {selected_dbs}")
        return selected_dbs

    async def generate_tool_calls(
        self, user_utterance: str, current_date: str, tools: List[Callable],
        single_db_schema: Dict[str, Any], history: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        system_instruction = self._build_tool_generation_instruction(current_date, single_db_schema)
        wrapped_tools = [self._wrap_tool(t) for t in tools]

        # Google Search Groundingを有効化
        # Function Callingと併用するためにリストに追加
        all_tools = wrapped_tools + [{'google_search_retrieval': {}}]

        model = genai.GenerativeModel(
            model_name=self.model_name,
            tools=all_tools,
            system_instruction=system_instruction
        )

        logger.info(f"Step 2: Generating tool calls for DB '{single_db_schema.get('id')}' with Search Grounding...")
        response = await self._run_gemini_async(model, user_utterance, history)

        tool_calls = []
        # レスポンスのpartsから関数呼び出しを抽出する
        if hasattr(response, 'parts'):
            for part in response.parts:
                if fn := part.function_call:
                    tool_calls.append({
                        "name": fn.name,
                        "args": self._sanitize_arg(fn.args)
                    })

        logger.info(f"Generated tool calls: {tool_calls}")
        return tool_calls

    async def generate_response(
        self, user_utterance: str, tool_results: List[Dict[str, Any]], history: List[Dict[str, Any]] = None
    ) -> str:
        system_instruction = self._build_response_generation_instruction()
        model = genai.GenerativeModel(model_name=self.model_name, system_instruction=system_instruction)

        # ツール実行結果がある場合は、会話履歴にユーザー発言を追加し、ツール結果を送信する
        # ない場合（雑談など）は、ユーザー発言そのものを送信する
        prompt_history = history or []
        
        if not tool_results:
            # ツール実行なし：ユーザー発言をそのままプロンプトとして送信
            prompt = user_utterance
        else:
            # ツール実行あり：ユーザー発言を履歴に追加し、ツール結果をプロンプトとして送信
            prompt_history.append({"role": "user", "parts": [user_utterance]})

            # tool_resultsをモデルに理解できる形式に変換
            tool_feedback = []
            for result in tool_results:
                tool_feedback.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=result["name"],
                            response={"content": json.dumps(result["result"], ensure_ascii=False)}
                        )
                    )
                )
            prompt = tool_feedback

        logger.info("Step 3: Generating final response...")
        # ユーザー発言、ツールコール（履歴内）、ツール結果をすべて渡す
        response = await self._run_gemini_async(model, prompt, prompt_history)

        logger.info(f"Final response text: {response.text}")
        return response.text
