
import os
import json
import sys
from mcp import ClientSession, StdioServerParameters
from domain.use_cases.interpret_and_execute import INotionMCPGateway

class NotionMCPGateway(INotionMCPGateway):
    def __init__(self, notion_database_mapping: dict):
        self.notion_database_mapping = notion_database_mapping

    async def execute_tool(self, action: str, args: dict) -> str:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_notion.server"],
            env=os.environ,
        )
        async with ClientSession(server_params) as (read, write):
            session = ClientSession(read, write)
            await session.initialize()

            # 論理名から実際のデータベースIDへのマッピング
            if "database_name" in args and args["database_name"] in self.notion_database_mapping:
                args["database_id"] = self.notion_database_mapping[args["database_name"]]['id']
                del args["database_name"] # NotionMCPはdatabase_idを期待するため、論理名は削除
            if "parent_name" in args and args["parent_name"] in self.notion_database_mapping:
                args["parent_id"] = self.notion_database_mapping[args["parent_name"]]['id']
                del args["parent_name"] # NotionMCPはparent_idを期待するため、論理名は削除

            result = await session.call_tool(action, arguments=args)
            
            if result.isError:
                error_detail = "".join([block.text for block in result.content if hasattr(block, 'text')])
                return f"エラー: {error_detail}"
            else:
                if result.structuredContent:
                    return json.dumps(result.structuredContent, indent=2, ensure_ascii=False)
                else:
                    return "ツールは正常に実行されましたが、結果はありませんでした。"
