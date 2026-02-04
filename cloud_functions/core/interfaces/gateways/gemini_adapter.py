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
        self.model_name = 'gemini-2.5-flash-lite' # Testing 2.5-flash-lite with function-only tools

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

    def _build_tool_generation_instruction(self, current_date: str, single_db_schema: Dict[str, Any], research_results: str = "") -> str:
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
        
        # 調査結果がある場合はプロンプトに追加
        if research_results:
            instruction += f"\n### Research Results (Google Search results):\n{research_results}\n"

        # Groundingと新カラム対応の指示を追加
        instruction += """
Note for ToDo List:
1. "Deadline" (Date): Set a concrete date for sorting (e.g., "2月中" -> 2026-02-28).
2. "DisplayDate" (Text): Keep the user's original vague expression (e.g., "2月中", "来週").
3. "Memo" (RichText): If the task needs research (e.g., "date ideas", "restaurant"), use the information from 'Research Results' above to fill this field.
4. "DoneDate" (Date): Only set this when marking a task as Done (check "完了ボタン"). Use today's date.
"""
        return instruction

    def _build_response_generation_instruction(self) -> str:
        """【ステップ3: 応答生成】用のシステムプロンプトを構築します。"""
        return "あなたは親切なアシスタントです。ユーザーの質問とツールの実行結果を元に、装飾のない自然な日本語で回答してください。Markdown（太字の**や箇条書きの*など）は絶対に使用しないでください。"

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

    def _convert_contents(self, contents: List[Any]) -> List[types.Content]:
        """
        コンテンツリストを google.genai.types.Content のリストに変換・正規化します。
        特に Firestore から取得した 'parts': ['text'] 形式を 'parts': [{'text': 'text'}] に変換します。
        """
        formatted_contents = []
        for item in contents:
            if isinstance(item, types.Content):
                formatted_contents.append(item)
            elif isinstance(item, dict):
                # copy dict to avoid modifying original
                content_dict = item.copy()
                if 'parts' in content_dict:
                    new_parts = []
                    for part in content_dict['parts']:
                        if isinstance(part, str):
                            new_parts.append(types.Part(text=part))
                        elif isinstance(part, dict):
                            # Ensure dict part is compatible
                            # SDK's types.Part is a Pydantic model, so we can unpack dict
                            try:
                                new_parts.append(types.Part(**part))
                            except Exception:
                                # Fallback if validation fails, just wrap as text
                                new_parts.append(types.Part(text=str(part)))
                        elif isinstance(part, types.Part):
                            new_parts.append(part)
                        else:
                            # Fallback
                            new_parts.append(types.Part(text=str(part)))
                    content_dict['parts'] = new_parts
                # role is required
                if 'role' not in content_dict:
                    content_dict['role'] = 'user'
                formatted_contents.append(types.Content(**content_dict))
            elif isinstance(item, str):
                formatted_contents.append(types.Content(role="user", parts=[types.Part(text=item)]))
            else:
                # Try to use as is (e.g. specialized types)
                formatted_contents.append(item)
        return formatted_contents

    async def _run_gemini_async(self, contents: List[Any], config: Optional[types.GenerateContentConfig] = None):
        """Geminiの同期SDKを非同期で安全に呼び出すラッパー。"""
        # コンテンツの正規化
        sanitized_contents = self._convert_contents(contents)
        
        def _run_generate():
            return self.client.models.generate_content(
                model=self.model_name,
                contents=sanitized_contents,
                config=config
            )
        try:
            return await asyncio.to_thread(_run_generate)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    async def select_databases(self, user_utterance: str, current_date: str, history: List[Dict[str, Any]] = None) -> List[str]:
        """【ステップ1: DB選択】ユーザーの質問に関連するNotionデータベースを選択します。"""
        system_instruction = self._build_db_selection_instruction(current_date)
        
        # ツール定義
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

        contents = []
        if history:
            contents.extend(history)
        contents.append({"role": "user", "parts": [{"text": user_utterance}]})

        logger.info("Step 1: Selecting databases...")
        response = await self._run_gemini_async(contents, config)

        selected_dbs = []
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call and part.function_call.name == "select_databases":
                    args = part.function_call.args
                    selected_dbs.extend(args.get("db_names", []))

        logger.info(f"Selected databases: {selected_dbs}")
        return selected_dbs

    async def perform_research(self, user_utterance: str, current_date: str, history: List[Dict[str, Any]] = None) -> str:
        """【ステップ1.5: 調査】Google検索ツールを使用して外部情報を調査します。"""
        system_instruction = f"""ユーザーの質問に答えるため、またはNotionに登録する情報を補完するために必要な情報をGoogle検索で調査してください。
本日付: {current_date}
調査が必要な例: レストランの場所や営業時間、イベントの開催日、特定のトピックに関するアイデアなど。
調査結果を日本語で分かりやすく要約して回答してください。調査が不要な場合は「調査不要」と回答してください。"""
        
        # Google Search Tool (Grounding)
        grounding_tool = types.Tool(google_search=types.GoogleSearch())

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[grounding_tool]
        )

        contents = []
        if history:
            contents.extend(history)
        contents.append({"role": "user", "parts": [{"text": user_utterance}]})

        logger.info("Step 1.5: Performing research via Google Search...")
        response = await self._run_gemini_async(contents, config)

        research_summary = ""
        if response.text:
            research_summary = response.text.strip()
        
        if research_summary == "調査不要" or not research_summary:
            logger.info("Research either not required or empty.")
            return ""

        logger.info(f"Research summary obtained: {research_summary[:100]}...")
        return research_summary

    async def generate_tool_calls(
        self, user_utterance: str, current_date: str, tools: List[Callable],
        single_db_schema: Dict[str, Any], history: List[Dict[str, Any]] = None,
        research_results: str = ""
    ) -> List[Dict[str, Any]]:
        system_instruction = self._build_tool_generation_instruction(current_date, single_db_schema, research_results)
        
        # ツール定義を自動生成ではなく手動定義に変更 (Nullableエラー回避のため)
        # google-genai SDK v0.2 は Python の Optional型 を JSON Schema の "type": ["string", "null"] に変換するが
        # Gemini API はこれをサポートしていないため、明示的にスキーマを定義する。
        
        tool_declarations = []
        
        # 1. search_database
        tool_declarations.append(types.FunctionDeclaration(
            name="search_database",
            description="Notionデータベースからページを検索する。タイトル検索、またはプロパティによるフィルタリングが可能。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "タイトル検索キーワード"},
                    "database_name": {"type": "string", "description": "検索対象のデータベース名"},
                    "filter_conditions": {"type": "string", "description": "JSON形式の絞り込み条件 (例: '{\"Status\": \"Done\"}')"}
                },
                "required": [] # 全てOptionalだが、Nullableにはしない
            }
        ))
        
        # 2. create_page
        tool_declarations.append(types.FunctionDeclaration(
            name="create_page",
            description="データベースに新しいページを作成する。",
            parameters={
                "type": "object",
                "properties": {
                    "database_name": {"type": "string", "description": "作成先のデータベース名"},
                    "title": {"type": "string", "description": "ページのタイトル"},
                    "properties": {"type": "object", "description": "その他のプロパティ設定値 (辞書)"}
                },
                "required": ["database_name", "title"]
            }
        ))
        
        # 3. update_page
        tool_declarations.append(types.FunctionDeclaration(
            name="update_page",
            description="既存のページを更新する (ステータス変更など)。",
            parameters={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "更新対象のページID"},
                    "properties": {"type": "object", "description": "更新するプロパティ値 (辞書)"}
                },
                "required": ["page_id", "properties"]
            }
        ))
        
        # 4. append_block
        tool_declarations.append(types.FunctionDeclaration(
            name="append_block",
            description="ページの末尾にブロックを追加する。",
            parameters={
                "type": "object",
                "properties": {
                    "block_id": {"type": "string", "description": "親ブロックまたはページのID"},
                    "children": {
                        "type": "array", 
                        "items": {"type": "object"},
                        "description": "追加するブロックのリスト (Notion API Block object)"
                    }
                },
                "required": ["block_id", "children"]
            }
        ))

        notion_tools = types.Tool(function_declarations=tool_declarations)
        
        # NOTE: Gemini 2.5シリーズでは Function Calling と Google Search Grounding の同時利用に制限があるため
        # Notion操作ツールのみを定義し、調査結果はプロンプト（テキスト）経由で渡します。
        all_tools = [notion_tools]

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
