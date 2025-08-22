import asyncio
import json
import os
import sys
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# .envファイルから環境変数を読み込む
load_dotenv()

# NotionデータベースID (ユーザーから提供されたもの)
# 本来は.envファイルで管理する
NOTION_DATABASE_ID = "1ff1ac9c8c708098bf4ac641178c9b8d"

async def query_notion_database():
    """
    mcp-notionサーバーを介して、指定したNotionデータベースをクエリするスクリプト。
    """
    print("mcp-notionサーバーへの接続とデータベースクエリテストを開始します...")

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

                print(f"\nテストとして'query_database'ツールを呼び出します (Database ID: {NOTION_DATABASE_ID})")
                
                # query_databaseツールを呼び出す
                result = await session.call_tool(
                    "query_database", 
                    arguments={"database_id": NOTION_DATABASE_ID}
                )

                print("\n--- テスト結果 ---")
                if result.isError:
                    print("\n[FAILED] ツールの呼び出しに失敗しました。")
                    if result.content:
                        for content_block in result.content:
                            if hasattr(content_block, 'text'):
                                print(f"エラー詳細: {content_block.text}")
                else:
                    if result.structuredContent:
                        print(json.dumps(result.structuredContent, indent=2, ensure_ascii=False))
                        print("\n[SUCCESS] データベースのクエリに成功しました！")
                    else:
                        print("\n[INFO] ツールは成功しましたが、構造化されたコンテンツはありませんでした。")
                        print(result.content)

    except Exception as e:
        print(f"\n[ERROR] テストスクリプトの実行中に予期せぬエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n接続テストが終了しました。")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(query_notion_database())