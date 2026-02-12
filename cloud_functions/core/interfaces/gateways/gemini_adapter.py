import os
import json
import asyncio
import functools
from google import genai
from google.genai import types
from typing import Dict, Any, List, Callable, Optional
from ...domain.interfaces import ILanguageModel
from ...logging_config import setup_logger, log_oneline

# ---------------------------------------------------------------------------
# ロギング設定
# ---------------------------------------------------------------------------
logger = setup_logger(__name__)

class GeminiAdapter(ILanguageModel):
    """
    Gemini API (google-genai SDK) を使用したILanguageModelの実装クラス。
    2ステップの思考プロセス（ツール生成→応答生成）を実装します。
    統合データベース (master_db) を使用します。
    """
    def __init__(self, system_instruction_template: str, notion_database_mapping: dict, response_instruction: str = ""):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        self.client = genai.Client(api_key=api_key)
        self.system_instruction_template = system_instruction_template
        self.response_instruction = response_instruction
        self.notion_database_mapping = notion_database_mapping
        self.model_name = 'gemini-2.5-flash-lite' # Testing 2.5-flash-lite with function-only tools
        self.system_instruction_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts", "system_instruction.md")
        self.response_instruction_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts", "response_instruction.md")

    # ---------------------------------------------------------------------------
    # プロンプト構築メソッド群
    # ---------------------------------------------------------------------------

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
        
        # 調査結果がある場合はプレースホルダーに代入、なければ空文字に
        if research_results:
            research_section = f"\n### 調査結果 (Google Search)\n{research_results}\n"
        else:
            research_section = ""
        instruction = instruction.replace("{research_results}", research_section)

        return instruction

    def _build_response_generation_instruction(self) -> str:
        """【ステップ3: 応答生成】用のシステムプロンプトを構築します。"""
        return self.response_instruction

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

    def _get_system_instruction(self) -> str:
        try:
            with open(self.system_instruction_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"System instruction file not found at {self.system_instruction_path}")
            return "You are a helpful assistant."

    def _get_response_instruction(self) -> str:
        try:
            with open(self.response_instruction_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Response instruction file not found at {self.response_instruction_path}")
            return ""

    def _get_model_config(self, system_instruction: str, tool_mode: str = "AUTO") -> types.GenerateContentConfig:
        """Gemini API 呼び出し用の共通コンフィグを作成します。"""
        # tool_mode に応じた設定 (SDK v0.2 準拠)
        tool_config = None
        if tool_mode in ["NONE", "AUTO", "ANY"]:
            tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=tool_mode
                )
            )

        return types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
            tool_config=tool_config
        )

    def _convert_to_gemini_contents(self, user_utterance: str, history: List[Dict[str, Any]], tool_results: List[Dict[str, Any]], current_turn_history: List[Dict[str, Any]] = None) -> List[types.Content]:
        """User input, history, and tool results converted to Gemini API content list."""
        contents = []
        
        # 1. Add History (Older turns)
        if history:
            converted_history = self._convert_contents(history)
            contents.extend(converted_history)
            
        # 2. Add Current Session (User Utterance + Tool Interaction)
        # Reconstruct the sequence: User -> [Model -> Tool]* -> [System Reminder]
        
        session_contents = []
        session_contents.append(types.Content(role="user", parts=[types.Part(text=user_utterance)]))
        
        if current_turn_history:
             # Multi-turn processing
             for turn in current_turn_history:
                 if turn['role'] == 'model':
                     parts = []
                     for part in turn['parts']:
                         if 'function_call' in part:
                             parts.append(types.Part(
                                 function_call=types.FunctionCall(
                                     name=part['function_call']['name'],
                                     args=part['function_call']['args']
                                 )
                             ))
                     session_contents.append(types.Content(role="model", parts=parts))
                 elif turn['role'] == 'function':
                     parts = []
                     for part in turn['parts']:
                         if 'function_response' in part:
                             parts.append(types.Part(
                                 function_response=types.FunctionResponse(
                                     name=part['function_response']['name'],
                                     response=part['function_response']['response']
                                 )
                             ))
                     # SDK v0.2: function response is usually in 'tool' role
                     session_contents.append(types.Content(role="tool", parts=parts))
        
        elif tool_results:
             # Legacy or single-turn results (if any)
             parts = []
             for res in tool_results:
                  parts.append(types.Part(
                      function_response=types.FunctionResponse(
                          name=res["name"],
                          response={"content": res["result"]}
                      )
                  ))
             # We need a model call before a function response to satisfy SDK structure
             # But here we just want the model to see the results. 
             # For Step 3, we can append a reminder.
             session_contents.append(types.Content(role="tool", parts=parts))

        else:
             # No tools were called at all
             # We add a hidden "system" reminder as a user message to trigger response check
             # (Gemini 2.5 response_instruction usually works better if it sees the discrepancy)
             pass

        contents.extend(session_contents)
        return contents

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

        logger.info(f"[RESEARCH_INPUT] user_utterance={log_oneline(user_utterance)}")
        logger.info("Step 1.5: Performing research via Google Search...")
        response = await self._run_gemini_async(contents, config)

        research_summary = ""
        if response.text:
            research_summary = response.text.strip()
        
        if research_summary == "調査不要" or not research_summary:
            logger.info("Research either not required or empty.")
            return ""

        logger.info(f"[RESEARCH_OUTPUT] summary={log_oneline(research_summary)}")
        return research_summary

    async def generate_tool_calls(
        self, user_utterance: str, current_date: str, tools: List[Callable],
        single_db_schema: Dict[str, Any], history: List[Dict[str, Any]] = None,
        research_results: str = "",
        current_turn_history: List[Dict[str, Any]] = None
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

        if current_turn_history:
            contents.extend(current_turn_history)

        logger.info(f"[TOOL_GEN_INPUT] user_utterance={log_oneline(user_utterance)}, system_instruction={log_oneline(system_instruction, max_length=300)}")
        logger.info(f"Step 2: Generating tool calls for DB '{single_db_schema.get('id')}'...")
        response = await self._run_gemini_async(contents, config)

        tool_calls = []
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    tool_calls.append({
                        "name": part.function_call.name,
                        "args": part.function_call.args
                    })

        logger.info(f"[TOOL_GEN_OUTPUT] tool_calls={tool_calls}")
        return tool_calls

    async def generate_response(
        self, user_utterance: str, tool_results: List[Dict[str, Any]], 
        history: List[Dict[str, Any]] = None,
        current_turn_history: List[Dict[str, Any]] = None,
        research_results: str = ""
    ) -> str:
        # Step 3用のコンテンツを構築
        contents = self._convert_to_gemini_contents(user_utterance, history, tool_results, current_turn_history)

        # 最終回答生成用のプロンプトを取得
        # main.py 等での初期化時に response_instruction が渡されている想定だが、
        # 念のためファイルからも読み込めるようにしておく
        instruction = self.response_instruction
        if not instruction:
            instruction = self._get_response_instruction()
        
        # 幻覚防止のための最終念押し (Reflection Instruction)
        # 会話の最後に、状況に応じた指示をシステム指示として注入する
        if tool_results:
             status_text = f"**重要: ツール実行結果は {len(tool_results)} 件です。結果に基づき、正確に回答を生成してください。**"
        else:
             status_text = "**重要: ツールは1つも実行されませんでした。保存や作成が依頼されている場合、嘘をつかずに正直に『実行できませんでした』と回答してください。**"

        # 調査結果がある場合は、それもコンテキストとして注入する (Context Bridge)
        research_text = ""
        if research_results:
            research_text = f"### 今回リサーチで見つかった情報 (Google Search)\n{research_results}\n"

        # 回答生成用の指示に状況を埋め込む (Safe replace avoiding format errors)
        final_system_instruction = instruction.replace(
            "{tool_execution_status}", status_text
        )
        final_system_instruction = final_system_instruction.replace(
            "{research_results}", research_text
        )

        try:
            # Step 3用のプロンプトを読み込む
            config = self._get_model_config(
                system_instruction=final_system_instruction,
                tool_mode="NONE"
            )

            # SDKのAPIを非同期呼び出し
            response = await self._run_gemini_async(contents, config)

            if response.text:
                logger.info(f"Final response text: {log_oneline(response.text)}")
                return response.text
            else:
                return "申し訳ありません、応答を生成できませんでした。"

        except Exception as e:
            logger.error(f"Error in generate_response: {e}")
            return f"エラーが発生しました: {str(e)}"
