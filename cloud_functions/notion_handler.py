from notion_client import Client, APIResponseError
import json
import os

class NotionHandler:
    def __init__(self, notion_database_mapping: dict):
        self.notion_api_key = os.environ.get("NOTION_API_KEY")
        if not self.notion_api_key:
            raise ValueError("NOTION_API_KEY environment variable is not set")
        self.notion = Client(auth=self.notion_api_key)
        self.notion_database_mapping = notion_database_mapping

    def execute_tool(self, action: str, args: dict) -> str:
        # 論理名から実際のデータベースIDへのマッピング
        if "database_name" in args and args["database_name"] in self.notion_database_mapping:
            args["database_id"] = self.notion_database_mapping[args["database_name"]]['id']
            del args["database_name"]
        if "parent_name" in args and args["parent_name"] in self.notion_database_mapping:
            args["parent_id"] = self.notion_database_mapping[args["parent_name"]]['id']
            del args["parent_name"]

        print(f"Notion API呼び出し: action={action}, args={args}")
        try:
            response = None
            if action == "create_page":
                parent_arg = {"database_id": args.pop("database_id")} if "database_id" in args else {}
                properties_arg = args.get("properties_json", {})
                response = self.notion.pages.create(parent=parent_arg, properties=properties_arg)

            elif action == "query_database":
                database_id = args.get("database_id")
                if not database_id:
                    return json.dumps({"error": "データベースクエリにはdatabase_idが必要です。"})

                filter_condition = args.get("filter_json")
                response = self.notion.databases.query(
                    database_id=database_id,
                    filter=filter_condition.get("filter") if filter_condition else None,
                )
            else:
                return json.dumps({"error": f"未知のアクション '{action}' です。"})

            # 成功した場合、Notion APIのレスポンスをJSON文字列として返す
            return json.dumps(response, indent=2, ensure_ascii=False)

        except APIResponseError as e:
            print(f"Notion APIからエラー応答がありました: {e}")
            return json.dumps({"error": f"Notion APIエラー: {e.code}", "message": e.body})
        except Exception as e:
            print(f"Notion API実行中に予期せぬエラーが発生しました: {e}")
            return json.dumps({"error": f"Notion API実行中に予期せぬエラーが発生しました: {e}"})
