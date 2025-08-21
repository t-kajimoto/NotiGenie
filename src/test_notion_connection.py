import asyncio
import json
import os
import sys
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# .envファイルから環境変数を読み込む。このスクリプト自体はキーを使わないが、
# 起動するサブプロセス(mcp-notion)が環境変数を必要とする。
load_dotenv()

async def test_notion_connection():
    """
    mcp-notionサーバーとの通信をテストするスクリプト。

    このテストの目的は、Notion APIキーが正しいか以前に、
    mcp-notionライブラリが提供するサーバープロセスを起動し、
    そのサーバーとMCP(Model Context Protocol)で通信できるかを確認すること。
    """
    print("mcp-notionサーバーとの接続テストを開始します...")

    # --------------------------------------------------------------------------
    # 1. サーバープロセスの定義
    # --------------------------------------------------------------------------
    # StdioServerParametersを使って、バックグラウンドで起動するサーバープロセスを定義する。
    # command: 実行するPythonのパス (現在の環境と同じPythonを使うためにsys.executableを指定)
    # args: 実行する引数 ('-m mcp_notion.server' は 'python -m mcp_notion.server' と同義)
    # env: サブプロセスに渡す環境変数 (os.environを渡すことで、load_dotenvで読み込んだ内容を含む現在の環境変数を引き継ぐ)
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_notion.server"],
        env=os.environ,
    )

    try:
        # --------------------------------------------------------------------------
        # 2. サーバーの起動とクライアントの接続
        # --------------------------------------------------------------------------
        # stdio_clientは、定義したサーバープロセスを開始し、
        # そのプロセスの標準入力(write)と標準出力(read)に接続するためのストリームを提供する。
        async with stdio_client(server_params) as (read, write):
            print("MCPサーバープロセスが起動しました。")

            # ClientSessionは、提供されたストリームを使ってMCP通信を管理するクライアントセッションを開始する。
            async with ClientSession(read, write) as session:
                print("MCPクライアントセッションが確立されました。")

                # --------------------------------------------------------------------------
                # 3. MCP通信の初期化とツール呼び出し
                # --------------------------------------------------------------------------
                # MCPのセッションを初期化する。これにより、サーバーとクライアントが通信可能な状態になる。
                await session.initialize()
                print("MCPセッションが初期化されました。")

                # サーバーが提供するツール(機能)を呼び出す。
                # ここでは、接続確認の代用として、引数なしで'search_notion'を呼び出している。
                print("\nテストとして'search_notion'ツールを呼び出します...")
                result = await session.call_tool("search_notion", arguments={"query": ""})

                print("\n--- テスト結果 ---")
                if result.isError:
                    print("\n[FAILED] ツールの呼び出しに失敗しました。")
                    if result.content:
                        for content_block in result.content:
                            if hasattr(content_block, 'text'):
                                print(f"エラー詳細: {content_block.text}")
                else:
                    # ツール呼び出しが成功した場合、通常は構造化されたコンテンツ(JSON)が返される。
                    if result.structuredContent:
                        print(json.dumps(result.structuredContent, indent=2))
                        # ここではsearch_notionがエラーを返しても、通信自体は成功とみなす。
                        print("\n[SUCCESS] mcp-notionサーバーとの通信に成功しました！")
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
    # Windows環境で非同期処理を実行するためのおまじない
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(test_notion_connection())
