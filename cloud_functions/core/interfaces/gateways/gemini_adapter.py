import os
import json
import asyncio
import logging
import sys
import functools
import google.generativeai as genai
from typing import Dict, Any, List, Callable
from ...domain.interfaces import ILanguageModel

# ---------------------------------------------------------------------------
# ロギング設定
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# ハンドラが設定されていない場合のみ追加（重複出力防止）
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

class GeminiAdapter(ILanguageModel):
    """
    Gemini APIを使用したILanguageModelの実装クラス。

    Infrastructure層に位置し、外部API（Google Gemini）との通信詳細をカプセル化します。
    Domain層やUse Case層からは、このクラスがGeminiを使っていることは隠蔽されます。
    """

    def __init__(self, system_instruction_template: str, notion_database_mapping: dict):
        """
        初期化処理。

        Args:
            system_instruction_template (str): システムプロンプトのテンプレート。ここにDB定義などが埋め込まれます。
            notion_database_mapping (dict): Notionデータベースの定義情報。プロンプト生成に使用します。
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        genai.configure(api_key=api_key)

        self.system_instruction_template = system_instruction_template
        self.notion_database_mapping = notion_database_mapping

    def _build_system_instruction(self, current_date: str) -> str:
        """
        AIに与えるシステムプロンプトを動的に構築します。

        何をやっているか:
        1. `notion_database_mapping` からデータベース名、説明、プロパティ情報を抽出します。
        2. それらをテキスト形式に整形し、テンプレート内の `{database_descriptions}` に埋め込みます。
        3. `{current_date}` を現在の日付に置換します。

        なぜやっているか:
        AIが正確にツールを使用するためには、どのようなデータベースがあり、どのようなプロパティ（列）を持っているかを
        理解している必要があるためです（RAGのようなコンテキスト注入）。
        """
        database_descriptions = ""
        for db_name, db_info in self.notion_database_mapping.items():
            title = db_info.get('title', db_name)
            properties_info = ""
            # プロパティ情報の詳細を展開
            if 'properties' in db_info:
                properties_info = "\n  Properties:\n"
                for prop_name, prop_details in db_info['properties'].items():
                    prop_type = prop_details.get('type', 'unknown')
                    options = ""
                    # 選択肢（Select/Status）がある場合は、有効な値を列挙してAIに教える
                    if 'options' in prop_details:
                        options = f" (Options: {', '.join(prop_details['options'])})"
                    properties_info += f"  - {prop_name} ({prop_type}){options}\n"

            database_descriptions += f"- {db_name} ({title}): {db_info['description']}{properties_info}\n"

        # テンプレートのプレースホルダーを置換
        instruction = self.system_instruction_template.replace("{database_descriptions}", database_descriptions)
        instruction = instruction.replace("{current_date}", current_date)
        return instruction

    def _sanitize_arg(self, arg: Any) -> Any:
        """
        Gemini APIから渡される特殊な型（Protobuf）を、Pythonの標準型に変換します。

        何をやっているか:
        Google GenAI SDKのFunction Calling機能は、引数を `MapComposite` や `RepeatedComposite` という
        Protobuf由来の特殊なクラスで渡してくることがあります。
        これらはそのままでは `json.dumps` したり、通常の辞書として扱ったりする際に不具合が起きる場合があるため、
        再帰的に `dict` や `list` に変換します。

        Args:
            arg (Any): 変換対象のオブジェクト。

        Returns:
            Any: 変換後のPython標準オブジェクト（dict, list, str, int, etc.）。
        """
        # 型名での判定（protobufライブラリを直接importせずに済むように）
        type_name = type(arg).__name__

        # MapCompositeはdictに変換
        if type_name == 'MapComposite':
            return {k: self._sanitize_arg(v) for k, v in arg.items()}
        # RepeatedCompositeはlistに変換
        elif type_name == 'RepeatedComposite':
            return [self._sanitize_arg(v) for v in arg]
        # 辞書の場合は再帰的に処理
        elif isinstance(arg, dict):
            return {k: self._sanitize_arg(v) for k, v in arg.items()}
        # リストの場合も再帰的に処理
        elif isinstance(arg, list):
            return [self._sanitize_arg(v) for v in arg]

        return arg

    def _wrap_tool(self, tool: Callable) -> Callable:
        """
        ツール関数をラップし、引数のサニタイズ処理を挟み込みます。

        何をやっているか:
        デコレータパターンを使用して、元のツール関数が呼ばれる直前に `_sanitize_arg` を
        全ての引数に対して実行するようにします。

        なぜやっているか:
        個々のツール（NotionAdapterのメソッド）側でGemini特有の型変換を意識させないためです。
        """
        @functools.wraps(tool)
        def wrapper(*args, **kwargs):
            sanitized_args = [self._sanitize_arg(arg) for arg in args]
            sanitized_kwargs = {k: self._sanitize_arg(v) for k, v in kwargs.items()}
            logger.debug(f"Calling tool {tool.__name__} with sanitized args: {sanitized_args}, kwargs: {sanitized_kwargs}")
            return tool(*sanitized_args, **sanitized_kwargs)

        return wrapper

    def _get_model(self, tools: List[Callable], system_instruction: str):
        """
        設定済みの GenerativeModel インスタンスを生成して返します。
        """
        # ツール関数をラップして引数をサニタイズするようにする
        wrapped_tools = [self._wrap_tool(t) for t in tools]

        return genai.GenerativeModel(
            model_name='gemini-2.0-flash-lite',
            tools=wrapped_tools,
            system_instruction=system_instruction
        )

    async def chat_with_tools(self, user_utterance: str, current_date: str, tools: List[Callable]) -> str:
        """
        ツール（Function Calling）を使用してユーザーと会話を行い、最終的な応答を生成します。

        何をやっているか:
        1. システムプロンプトを構築します。
        2. Geminiモデルを初期化し、ツールを登録します。
        3. `model.start_chat` でチャットセッションを開始します。
        4. `send_message` を呼び出してユーザーの発言を送信します。
           `enable_automatic_function_calling=True` を指定することで、
           モデルが必要と判断したツール呼び出しをSDK内部で自動的に実行・結果取得・再生成のループを行います。
        5. 最終的なテキスト応答を返します。

        Args:
            user_utterance (str): ユーザーの入力テキスト。
            current_date (str): 現在日付。
            tools (List[Callable]): 使用可能なツール関数のリスト。

        Returns:
            str: モデルからの最終応答テキスト。
        """
        system_instruction = self._build_system_instruction(current_date)
        model = self._get_model(tools, system_instruction)

        logger.info(f"Starting chat with tools. User Utterance: {user_utterance}")

        # 同期メソッドを非同期実行するためのラッパー関数
        def _run_chat():
            # enable_automatic_function_calling=True により、ツール実行の往復（Turn）は
            # SDKが内部で処理してくれます。開発者は1回の呼び出しで最終結果を得られます。
            chat = model.start_chat(enable_automatic_function_calling=True)
            response = chat.send_message(user_utterance)
            return response.text

        try:
            # Google GenAI SDKのメソッドは同期（ブロッキング）処理を行うため、
            # イベントループをブロックしないように別スレッドで実行します。
            # これにより 'Event loop is closed' エラーやタイムアウトを回避します。
            response_text = await asyncio.to_thread(_run_chat)
            logger.info(f"Received response from Gemini:\n{response_text}")
            return response_text
        except Exception as e:
            msg = f"Gemini API error in chat_with_tools: {e}"
            logger.error(msg)
            # エラー発生時は、そのままエラー内容をユーザーに伝える（デバッグ容易性のため）
            # 本番運用では「申し訳ありません...」などに丸めることも検討してください。
            return f"申し訳ありません、エラーが発生しました: {e}"
