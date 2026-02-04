import os
import json
import asyncio
import logging
import sys
import functools
from google import genai
from google.genai import types
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
    Gemini API (google-genai SDK) を使用したILanguageModelの実装クラス。
    3ステップの思考プロセス（DB選択→ツール生成→応答生成）を実装します。
    """
    def __init__(self, system_instruction_template: str, notion_database_mapping: dict):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        self.client = genai.Client(api_key=api_key)
        self.system_instruction_template = system_instruction_template
        self.notion_database_mapping = notion_database_mapping
        self.model_name = 'gemini-2.0-flash-lite' # Stable version from available models list

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
3. "Memo" (RichText): If the task needs research (e.g., "date ideas", "restaurant"), use the 'google_search' tool to find info and summarize it here.
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
        # 新しいSDKでは型が異なる可能性があるため、汎用的に処理
        if isinstance(arg, dict):
            return {k: self._sanitize_arg(v) for k, v in arg.items()}
        elif isinstance(arg, list):
            return [self._sanitize_arg(v) for v in arg]
        return arg

    def _wrap_tool(self, tool: Callable) -> Callable:
        @functools.wraps(tool)
        def wrapper(*args, **kwargs):
            try:
                # 引数のサニタイズ（必要に応じて）
                sanitized_args = [self._sanitize_arg(arg) for arg in args]
                sanitized_kwargs = {k: self._sanitize_arg(v) for k, v in kwargs.items()}
                return tool(*sanitized_args, **sanitized_kwargs)
            except Exception as e:
                logger.error(f"Error executing tool {tool.__name__}: {e}")
                raise
        return wrapper

    async def _run_gemini_async(self, contents: List[Any], config: Optional[types.GenerateContentConfig] = None):
        """Geminiの同期SDKを非同期で安全に呼び出すラッパー。"""
        def _run_generate():
            return self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )
        try:
            return await asyncio.to_thread(_run_generate)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    # ---------------------------------------------------------------------------
    # ILanguageModel インターフェース実装
    # ---------------------------------------------------------------------------
    async def select_databases(self, user_utterance: str, current_date: str, history: List[Dict[str, Any]] = None) -> List[str]:
        system_instruction = self._build_db_selection_instruction(current_date)
        
        # ツール定義 (FunctionDeclarations は google.genai.types.Tool でラップする)
        select_databases_tool = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
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
            ]
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[select_databases_tool]
        )

        # 履歴と現在の発言を組み合わせる (History handling needs simplified)
        # 簡易的に、履歴の最後の数件 + 現在の発言のみを使用するか、あるいは履歴全体を渡す
        # ここではシンプルにユーザー発言のみで判定させる（ステップ1なので文脈依存が少ないと仮定、あるいは履歴が必要なら追加）
        # NOTE: historyの形式変換が必要かもしれないが、一旦 user_utterance のみで実装
        contents = [user_utterance]

        logger.info("Step 1: Selecting databases...")
        response = await self._run_gemini_async(contents, config)

        selected_dbs = []
        # レスポンス解析
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call and part.function_call.name == "select_databases":
                    args = part.function_call.args
                    # argsはdict形式でアクセス可能
                    selected_dbs.extend(args.get("db_names", []))

        logger.info(f"Selected databases: {selected_dbs}")
        return selected_dbs

    async def generate_tool_calls(
        self, user_utterance: str, current_date: str, tools: List[Callable],
        single_db_schema: Dict[str, Any], history: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        system_instruction = self._build_tool_generation_instruction(current_date, single_db_schema)
        
        # ユーザー定義ツールをSDKの形式に変換 (Client.models.generate_content は callable を直接受け取れる)
        wrapped_tools = [self._wrap_tool(t) for t in tools]
        
        # google_search ツールを追加
        # google-genai SDK では types.Tool(google_search=types.GoogleSearch()) で定義
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        
        # ユーザー定義ツールは function_declarations ではなく、直接 callable として渡すことも可能だが、
        # ここでは統一的に tools リストを作成する
        # NOTE: google-genai SDK allows passing python functions directly in `tools` list
        all_tools = wrapped_tools + [grounding_tool]

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=all_tools
        )

        # 履歴の変換は必要だが、ここでは user_utterance をメインに使用
        # 履歴がある場合は messages に変換して追加する必要がある
        contents = []
        if history:
             # Convert history dicts to types.Content if necessary, or just dicts
             # SDK accepts list of dicts: [{'role': 'user', 'parts': [...]}, ...]
             contents.extend(history)
        contents.append({"role": "user", "parts": [{"text": user_utterance}]})

        logger.info(f"Step 2: Generating tool calls for DB '{single_db_schema.get('id')}' with Search Grounding...")
        response = await self._run_gemini_async(contents, config)

        tool_calls = []
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    tool_calls.append({
                        "name": part.function_call.name,
                        "args": part.function_call.args
                    })

        logger.info(f"Generated tool calls: {tool_calls}")
        return tool_calls

    async def generate_response(
        self, user_utterance: str, tool_results: List[Dict[str, Any]], history: List[Dict[str, Any]] = None
    ) -> str:
        system_instruction = self._build_response_generation_instruction()
        config = types.GenerateContentConfig(system_instruction=system_instruction)

        contents = history or []
        
        if not tool_results:
            # ツール実行なし
            # 最後にユーザー発言を追加
            contents.append({"role": "user", "parts": [{"text": user_utterance}]})
        else:
            # ツール実行あり
            # 1. ユーザー発言
            contents.append({"role": "user", "parts": [{"text": user_utterance}]})
            
            # 2. モデルのツールコール (履歴として必要だが、ここでは前のターンで生成されたと仮定するか、
            #    あるいは tool_results に対応する tool_call が直前にある必要がある)
            #    簡略化のため、tool_results を function_response として追加する
            #    (Note: Geminiのマルチターンでは tool_call -> tool_response の順序が重要)
            
            # 実際の対話フローを再現するには、直前の generate_tool_calls の応答(model role)も履歴に含めるべきだが
            # ここでは tool_results から "ユーザーがツールを実行して結果を返した" 形式で構成する
            
            parts = []
            for result in tool_results:
                 parts.append(
                     types.Part(
                         function_response=types.FunctionResponse(
                             name=result["name"],
                             response={"content": result["result"]} # dict check
                         )
                     )
                 )
            
            # function_response は user ロールから返される (あるいは function ロール？ SDKによる)
            # Gemini API では function_response は user role の一部、または独立した function role
            # google-genai SDK 0.2.0 では通常 'function' role を使うことが多いが、'user' に含める場合もある
            # ここでは 'function' role を試行
            contents.append({"role": "function", "parts": parts})

        logger.info("Step 3: Generating final response...")
        response = await self._run_gemini_async(contents, config)

        if response.text:
            logger.info(f"Final response text: {response.text}")
            return response.text
        else:
            logger.warning("Empty response text")
            return "申し訳ありません、うまく回答を生成できませんでした。"
