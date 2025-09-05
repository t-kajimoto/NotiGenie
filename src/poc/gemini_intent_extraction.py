import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import asyncio
from mcp import ClientSession, StdioServerParameters
import sys
import yaml

# .envファイルをロード
load_dotenv()

# 標準入出力のエンコーディングをUTF-8に設定
# Windows環境での文字化け対策
if sys.platform == "win32":
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')

# APIキーを設定
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("エラー: .envファイルにGEMINI_API_KEYが設定されていません。")
    exit()
else:
    genai.configure(api_key=api_key)

# config.yamlからデータベースマッピングを読み込む
CONFIG_FILE = "config.yaml"
if not os.path.exists(CONFIG_FILE):
    print(f"エラー: 設定ファイル'{CONFIG_FILE}'が見つかりません。")
    print("config.yaml.exampleを参考に、プロジェクトルートにconfig.yamlを作成してください。")
    exit()

with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

NOTION_DATABASE_MAPPING = config.get("notion_databases", {})

# --------------------------------------------------------------------------
# 1. プロンプトの読み込み
# --------------------------------------------------------------------------
PROMPT_FILE = "prompts/notion_command_generator.md"
if not os.path.exists(PROMPT_FILE):
    print(f"エラー: プロンプトファイル'{PROMPT_FILE}'が見つかりません。")
    exit()

with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
    SYSTEM_INSTRUCTIONS_TEMPLATE = f.read()

# --------------------------------------------------------------------------
# 2. Gemini API呼び出し関数
# --------------------------------------------------------------------------
async def generate_notion_command(user_utterance: str) -> str:
    """ユーザーの発話からNotion操作のJSONコマンドを生成する"""
    model = genai.GenerativeModel('gemini-pro') # モデルを更新
    
    database_descriptions = ""
    for db_name, db_info in NOTION_DATABASE_MAPPING.items():
        database_descriptions += f"- {db_name}: {db_info['description']}\n"

    full_prompt = SYSTEM_INSTRUCTIONS_TEMPLATE.replace("{database_descriptions}", database_descriptions)
    full_prompt = full_prompt.replace("{user_utterance}", user_utterance)

    print(f"Geminiにコマンド生成をリクエスト中...")
    response = await model.generate_content_async(full_prompt)
    
    # レスポンスからMarkdownのコードブロックを削除
    cleaned_json = response.text.strip().replace("```json", "").replace("```", "").strip()
    return cleaned_json

async def generate_final_response(tool_result: str) -> str:
    """ツールの実行結果から最終的な応答メッセージを生成する"""
    model = genai.GenerativeModel('gemini-pro') # モデルを更新
    prompt = f"Notionの操作結果は以下の通りです。この結果を元に、ユーザーへの応答メッセージを簡潔に生成してください。\n\n# 操作結果\n{tool_result}\n\n# 応答メッセージ"
    response = await model.generate_content_async(prompt)
    return response.text

# --------------------------------------------------------------------------
# 3. ツール実行関数
# --------------------------------------------------------------------------
async def execute_notion_tool(action: str, args: dict) -> str:
    """NotionMCPツールを実行する"""
    server_params = StdioServerParameters(
        command=[sys.executable, "-m", "mcp_notion.server"],
        env=os.environ,
    )
    async with ClientSession(server_params) as session:
        # 論理名から実際のデータベースIDへのマッピング
        if "database_name" in args and args["database_name"] in NOTION_DATABASE_MAPPING:
            args["database_id"] = NOTION_DATABASE_MAPPING[args["database_name"]]['id']
            del args["database_name"]
        if "parent_name" in args and args["parent_name"] in NOTION_DATABASE_MAPPING:
            args["parent_id"] = NOTION_DATABASE_MAPPING[args["parent_name"]]['id']
            del args["parent_name"]

        print(f"ツール実行: {action} with args: {args}")
        result = await session.call_tool(action, arguments=args)
        
        if result.isError:
            error_detail = "".join([block.text for block in result.content if hasattr(block, 'text')])
            return f"エラー: {error_detail}"
        else:
            if result.structuredContent:
                return json.dumps(result.structuredContent, indent=2, ensure_ascii=False)
            else:
                return "ツールは正常に実行されましたが、結果はありませんでした。"

# --------------------------------------------------------------------------
# 4. メイン処理
# --------------------------------------------------------------------------
async def main():
    print("Gemini意図抽出プロトタイプを開始します。'exit'で終了します。")
    while True:
        user_input = input("\nユーザー発話: ")
        if user_input.lower() == 'exit':
            break
        
        # 1. コマンド生成
        command_json_str = await generate_notion_command(user_input)
        print(f"\n--- Gemini生成コマンド ---\n{command_json_str}")

        try:
            command_data = json.loads(command_json_str)
            action = command_data.pop("action", None)
            args = command_data

            if action and action != "error":
                # 2. ツール実行
                tool_result = await execute_notion_tool(action, args)
                print(f"\n--- ツール実行結果 ---{tool_result}")

                # 3. 最終応答生成
                final_response = await generate_final_response(tool_result)
                print(f"\n--- Gemini最終応答 ---{final_response}")
            else:
                print(f"\n--- Gemini応答 ---{command_data.get('message', '不明なエラー')}")

        except json.JSONDecodeError:
            print("\n--- Gemini応答（JSONデコードエラー） ---")
            print(command_json_str)

    print("プロトタイプを終了します。")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())
