import asyncio
import json
import os
import sys
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# .envファイルから環境変数を読み込む
load_dotenv()

async def list_notion_tools():
    """
    mcp-notionサーバーが提供するツールの一覧を取得するスクリプト。
    """
    print("mcp-notionサーバーが提供するツールの一覧を取得します...")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_notion.server"],
        env=os.environ,
    )

    try:
        async with stdio_client(server_params) as (read, write):
            print("MCPサーバープロセスが起動しました。")

            async with ClientSession(read, write) as session:
                print("MCPクライアントセッションが確立されました。")

                await session.initialize()
                print("MCPセッションが初期化されました。")

                print("\n'list_tools'ツールを呼び出します...")
                
                # list_toolsツールを呼び出す
                result = await session.list_tools()

                print("\n--- テスト結果 ---")
                print(result)

    except Exception as e:
        print(f"\n[ERROR] テストスクリプトの実行中に予期せぬエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nテストが終了しました。")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(list_notion_tools())
