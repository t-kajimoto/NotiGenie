import os
import json
from typing import Dict, Any, Optional
from notion_client import Client, APIResponseError
from ...domain.interfaces import INotionRepository

class NotionAdapter(INotionRepository):
    """
    Notion APIを使用したINotionRepositoryの実装。
    Infrastructure層に位置し、Notionクライアントライブラリのラッパーとして機能します。
    """

    def __init__(self, notion_database_mapping: Dict[str, Any]):
        """
        初期化処理。

        Args:
            notion_database_mapping (dict): データベース名とIDのマッピング情報。
                                          config.yamlから読み込まれた構造を想定。
                                          Example: {"TaskDB": {"id": "xxx", ...}}
        """
        self.api_key = os.environ.get("NOTION_API_KEY")
        self.client = None
        if self.api_key:
            self.client = Client(auth=self.api_key)
        else:
            print("Warning: NOTION_API_KEY not set. Notion operations will fail.")

        self.notion_database_mapping = notion_database_mapping

    def execute_tool(self, action: str, args: Dict[str, Any]) -> str:
        """
        Notionに対する操作を実行します。

        Args:
            action (str): アクション名 (query_database, create_page, etc)
            args (Dict[str, Any]): アクションに必要なパラメータ

        Returns:
            str: 実行結果（JSON形式の文字列）
        """
        if not self.client:
            return json.dumps({"error": "Notion API key is not configured."})

        try:
            if action == "query_database":
                return self._query_database(args)
            elif action == "create_page":
                return self._create_page(args)
            elif action == "append_block":
                return self._append_block(args)
            else:
                return json.dumps({"error": f"未知のアクション: {action}"})
        except APIResponseError as e:
            return json.dumps({"error": f"Notion APIエラー: {str(e)}", "code": e.code})
        except Exception as e:
            return json.dumps({"error": f"予期せぬエラー: {str(e)}"})

    def _resolve_database_id(self, database_name: str) -> Optional[str]:
        """データベース名からIDを解決します。"""
        if database_name in self.notion_database_mapping:
            return self.notion_database_mapping[database_name]["id"]
        return None

    def _query_database(self, args: Dict[str, Any]) -> str:
        database_name = args.get("database_name")
        database_id = args.get("database_id")

        # IDが直接指定されていない場合、名前から解決
        if not database_id and database_name:
            database_id = self._resolve_database_id(database_name)

        if not database_id:
            return json.dumps({"error": "Database ID or valid Database Name is required."})

        filter_param = args.get("filter_json", {})
        # filter_jsonが文字列で渡された場合のケア（念のため）
        if isinstance(filter_param, str):
            try:
                filter_param = json.loads(filter_param)
            except:
                pass

        # filterキーが直下にあるか、そのままfilterとして使うか
        # notion-clientは filter={...} を受け取る
        # LLMが {"filter": {...}} という構造を返すか、中身だけ返すかによるが、
        # args["filter_json"] が filterオブジェクトそのものと仮定する

        response = self.client.databases.query(database_id=database_id, **filter_param)
        return json.dumps(response)

    def _create_page(self, args: Dict[str, Any]) -> str:
        database_name = args.get("database_name")
        database_id = args.get("database_id")

        if not database_id and database_name:
            database_id = self._resolve_database_id(database_name)

        if not database_id:
            return json.dumps({"error": "Database ID or valid Database Name is required."})

        properties = args.get("properties_json", {})
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except:
                pass

        response = self.client.pages.create(
            parent={"database_id": database_id},
            properties=properties
        )
        return json.dumps(response)

    def _append_block(self, args: Dict[str, Any]) -> str:
        block_id = args.get("block_id")
        if not block_id:
             return json.dumps({"error": "block_id is required."})

        children = args.get("children_json", [])
        if isinstance(children, str):
            try:
                children = json.loads(children)
            except:
                pass

        response = self.client.blocks.children.append(
            block_id=block_id,
            children=children
        )
        return json.dumps(response)
