import os
import json
from notion_client import Client
from typing import Dict, Any
from ...domain.interfaces import INotionRepository

class NotionAdapter(INotionRepository):
    """
    Notion APIを使用したINotionRepositoryの実装。
    Infrastructure層に位置し、外部APIとの通信詳細をカプセル化します。
    """

    def __init__(self, notion_database_mapping: dict):
        """
        初期化処理。

        Args:
            notion_database_mapping (dict): Notionデータベースの定義情報。
        """
        self.notion_database_mapping = notion_database_mapping
        self.api_key = os.environ.get("NOTION_API_KEY")

        if self.api_key and self.api_key != "dummy":
            self.client = Client(auth=self.api_key)
        else:
            # テスト時やAPIキー未設定時
            self.client = None
            print("Warning: NOTION_API_KEY not set or is dummy.")

    def execute_tool(self, action: str, args: Dict[str, Any]) -> Any:
        """
        指定されたアクションと引数でNotionツールを実行します。
        """
        if not self.client:
            return {"error": "Notion Client not initialized (No API Key)"}

        try:
            if action == "query_database":
                return self._query_database(args)
            elif action == "create_page":
                return self._create_page(args)
            elif action == "append_block_children":
                # 必要に応じて実装
                pass
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": str(e)}

    def _query_database(self, args: Dict[str, Any]) -> Any:
        database_name = args.get("database_name")
        query_filter = args.get("filter", {})

        # データベース名からIDを取得（簡易実装）
        # 実際にはマッピングからIDを引くロジックが必要
        database_id = None
        if database_name and database_name in self.notion_database_mapping:
            database_id = self.notion_database_mapping[database_name].get("id")

        if not database_id:
            # IDが直接渡された場合やマッピングにない場合のフォールバック
            database_id = args.get("database_id")

        if not database_id:
             return {"error": "Database ID not found"}

        return self.client.databases.query(database_id=database_id, filter=query_filter)

    def _create_page(self, args: Dict[str, Any]) -> Any:
        # 簡易実装
        parent = args.get("parent")
        properties = args.get("properties")

        if not parent or not properties:
            return {"error": "Missing parent or properties for create_page"}

        return self.client.pages.create(parent=parent, properties=properties)
