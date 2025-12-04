import os
import json
from typing import Dict, Any, Union, Optional
from notion_client import Client, APIResponseError
from ...domain.interfaces import INotionRepository

class NotionAdapter(INotionRepository):
    """
    Notion APIを使用したINotionRepositoryの実装。
    Infrastructure層に位置し、外部APIとの通信詳細をカプセル化します。
    """

    def __init__(self, notion_database_mapping: Dict[str, Any]):
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
            if self.api_key != "dummy":
                print("Warning: NOTION_API_KEY not set.")

    def execute_tool(self, action: str, args: Dict[str, Any]) -> Any:
        """
        指定されたアクションと引数でNotionツールを実行します。
        実行結果は、Use Case側で扱いやすいようにJSON文字列または辞書で返します。
        現在の実装では、互換性のためにJSON文字列を返すことを推奨しますが、
        将来的に辞書への移行を見越して実装します。
        """
        if not self.client:
            return json.dumps({"error": "Notion Client not initialized (No API Key)"})

        try:
            if action == "query_database":
                result = self._query_database(args)
            elif action == "create_page":
                result = self._create_page(args)
            elif action == "append_block":
                result = self._append_block(args)
            elif action == "append_block_children": # mainブランチの命名に対応
                result = self._append_block(args)
            else:
                return json.dumps({"error": f"未知のアクション: {action}"})

            # 結果がすでに文字列（JSON）ならそのまま、オブジェクトならJSON化
            if isinstance(result, str):
                return result
            return json.dumps(result)

        except APIResponseError as e:
            return json.dumps({"error": f"Notion APIエラー: {str(e)}", "code": e.code})
        except Exception as e:
            return json.dumps({"error": f"予期せぬエラー: {str(e)}"})

    def _resolve_database_id(self, database_name: str) -> Optional[str]:
        """データベース名からIDを解決します。"""
        if database_name in self.notion_database_mapping:
            return self.notion_database_mapping[database_name].get("id")
        return None

    def _query_database(self, args: Dict[str, Any]) -> Any:
        database_name = args.get("database_name")
        database_id = args.get("database_id")

        # IDが直接指定されていない場合、名前から解決
        if not database_id and database_name:
            database_id = self._resolve_database_id(database_name)

        if not database_id:
            return {"error": "Database ID or valid Database Name is required."}

        # Mainブランチは "filter", HEADは "filter_json" を使用していた可能性がある
        # 両対応する
        filter_param = args.get("filter_json")
        if not filter_param:
            filter_param = args.get("filter")

        # filter_jsonが文字列で渡された場合のケア
        if isinstance(filter_param, str):
            try:
                filter_param = json.loads(filter_param)
            except:
                pass

        # filter_paramが {"filter": {...}} 形式か、中身だけか
        # notion-client.databases.query は **kwargs で filter={...} を受け取る
        # もし filter_param が {"filter": ...} ならそれを展開して渡すのが安全
        query_kwargs = {}
        if filter_param:
            if isinstance(filter_param, dict) and "filter" in filter_param and len(filter_param) == 1:
                query_kwargs = filter_param
            else:
                query_kwargs = {"filter": filter_param}

        response = self.client.databases.query(database_id=database_id, **query_kwargs)
        return response

    def _create_page(self, args: Dict[str, Any]) -> Any:
        database_name = args.get("database_name")
        database_id = args.get("database_id")

        if not database_id and database_name:
            database_id = self._resolve_database_id(database_name)

        # Mainブランチの実装も考慮 (parent引数)
        parent = args.get("parent")
        if parent:
             # parentが明示されている場合はそれを使う
             pass
        elif database_id:
             parent = {"database_id": database_id}
        else:
             return {"error": "Database ID or valid Database Name or Parent is required."}

        properties = args.get("properties_json")
        if not properties:
            properties = args.get("properties", {})

        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except:
                pass

        response = self.client.pages.create(
            parent=parent,
            properties=properties
        )
        return response

    def _append_block(self, args: Dict[str, Any]) -> Any:
        block_id = args.get("block_id")
        if not block_id:
             return {"error": "block_id is required."}

        children = args.get("children_json")
        if not children:
            children = args.get("children", [])

        if isinstance(children, str):
            try:
                children = json.loads(children)
            except:
                pass

        response = self.client.blocks.children.append(
            block_id=block_id,
            children=children
        )
        return response
