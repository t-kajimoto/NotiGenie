import os
import json
import logging
import sys
import traceback
import uuid
from typing import Dict, Any, Optional, List, Union
from notion_client import Client, APIResponseError
from ...domain.interfaces import INotionRepository

# ---------------------------------------------------------------------------
# ロギング設定
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

class NotionAdapter(INotionRepository):
    """
    Notion APIを使用したリポジトリ実装クラス。

    Infrastructure層に位置し、外部API（Notion）との通信詳細をカプセル化します。
    ここでは、AIが扱いやすい「データベース名（英語）」を実際の「Database ID（UUID）」に変換したり、
    複雑なNotion APIのフィルタ条件（JSON構造）を組み立てる責務を持ちます。
    """

    def __init__(self, notion_database_mapping: Dict[str, Any]):
        """
        初期化処理。

        Args:
            notion_database_mapping (dict): Notionデータベースの定義情報（schemas.yamlの中身）。
                                          論理名とID、プロパティ定義のマッピングを持ちます。
        """
        self.notion_database_mapping = notion_database_mapping
        self.api_key = os.environ.get("NOTION_API_KEY")

        if self.api_key and self.api_key != "dummy":
            # notion-client の初期化
            # log_level=logging.DEBUG を設定して、リクエストの詳細をログに残せるようにします。
            # notion_version="2022-06-28" を明示的に指定してAPIの互換性を保ちます。
            self.client = Client(
                auth=self.api_key,
                logger=logger,
                log_level=logging.DEBUG,
                notion_version="2022-06-28"
            )
            logger.info("Notion Client initialized successfully.")
        else:
            self.client = None
            if self.api_key != "dummy":
                logger.warning("Warning: NOTION_API_KEY not set.")

    def validate_connection(self) -> bool:
        """
        Notion APIへの接続テストを行います。
        アプリ起動時にAPIキーが正しいか確認するために使用します。
        """
        if not self.client:
            logger.error("Validate Connection Failed: Client not initialized (No API Key)")
            return False

        try:
            logger.info("Validating Notion API connection...")
            user = self.client.users.me()
            logger.info(f"Notion API Connection Successful. Bot User: {user.get('name')} (ID: {user.get('id')})")
            return True
        except APIResponseError as e:
            logger.error(f"Notion API Connection Failed: {e.code} - {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Notion API Connection Failed (Unexpected): {str(e)}")
            return False

    def _resolve_database_id(self, database_name: str) -> Optional[str]:
        """
        論理データベース名（例: 'todo_list'）から、実際のNotion Database ID（UUID）を取得します。
        """
        if not database_name:
            return None

        # マッピングに名前があればそのIDを返す
        if database_name in self.notion_database_mapping:
            val = self.notion_database_mapping[database_name].get("id")
            if val:
                return str(val).strip()

        return None

    def _resolve_property_type(self, database_name: str, property_name: str) -> Optional[str]:
        """
        指定されたデータベースのプロパティの型（'checkbox', 'select' 等）を取得します。
        フィルタ条件のJSONを構築する際に、型に応じた正しいクエリを作成するために必要です。
        """
        if not database_name or database_name not in self.notion_database_mapping:
            return None

        props = self.notion_database_mapping[database_name].get("properties", {})
        prop_config = props.get(property_name)
        if prop_config:
            return prop_config.get("type")
        return None

    def search_database(self, query: Optional[str] = None, database_name: Optional[str] = None, filter_conditions: Optional[str] = None) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        データベースからページを検索します。AIが使用する主要なツールです。

        Args:
            query (str, optional): タイトル検索キーワード。
            database_name (str, optional): 検索対象のデータベース名（英語のキー名）。
            filter_conditions (str, optional): JSON形式の絞り込み条件。
                例: '{"Status": "Done", "Category": "Work"}'
                AIはこの引数にJSON文字列を渡すことで、プロパティに基づいたフィルタリングを行います。

        Returns:
            List[Dict] | Dict: 検索結果の簡略化されたリスト、またはエラー情報。
        """
        logger.info(f"Searching database. Query: {query}, DB Name: {database_name}, Filter: {filter_conditions}")

        if not self.client:
            return {"error": "Notion Client not initialized"}

        try:
            database_id = None
            if database_name:
                database_id = self._resolve_database_id(database_name)
                if not database_id:
                     msg = f"Database '{database_name}' not found in configuration. Available keys: {list(self.notion_database_mapping.keys())}"
                     logger.warning(msg)
                     return {"error": msg}

            # Database IDの形式チェック（UUID形式）
            if database_id:
                try:
                    database_id = str(uuid.UUID(database_id))
                except ValueError:
                    msg = f"Invalid Database ID format: {database_id}"
                    logger.error(msg)
                    return {"error": msg}

                # ---------------------------------------------------------
                # 検索クエリ（Payload）の構築
                # ---------------------------------------------------------
                payload = {}
                filters = []

                # 1. タイトル部分一致検索 (query引数がある場合)
                if query:
                    # 'Name' や 'Title' など、実際のタイトルプロパティ名を特定
                    title_prop = "Name" # default
                    if database_name in self.notion_database_mapping:
                         props = self.notion_database_mapping[database_name].get("properties", {})
                         for k, v in props.items():
                             if v.get("type") == "title":
                                 title_prop = k
                                 break
                    filters.append({
                        "property": title_prop,
                        "title": {
                            "contains": query
                        }
                    })

                # 2. プロパティによる絞り込み (filter_conditions引数がある場合)
                if filter_conditions:
                    try:
                        conditions = json.loads(filter_conditions)
                        for prop, value in conditions.items():
                            # プロパティの型を解決して、適切なNotion APIフィルタ構文を使用する
                            prop_type = self._resolve_property_type(database_name, prop)

                            if prop_type == "checkbox":
                                filters.append({
                                    "property": prop,
                                    "checkbox": {
                                        "equals": value
                                    }
                                })
                            elif prop_type == "select":
                                filters.append({
                                    "property": prop,
                                    "select": {
                                        "equals": value
                                    }
                                })
                            elif prop_type == "status":
                                filters.append({
                                    "property": prop,
                                    "status": {
                                        "equals": value
                                    }
                                })
                            elif prop_type == "date":
                                # 日付は dict で詳細条件が来る場合と、値のみの場合を考慮
                                if isinstance(value, dict):
                                     filters.append({
                                        "property": prop,
                                        "date": value
                                    })
                                else:
                                     filters.append({
                                        "property": prop,
                                        "date": {
                                            "equals": value
                                        }
                                    })
                            else:
                                # デフォルトは rich_text contains (文字列検索)
                                if isinstance(value, str):
                                    filters.append({
                                        "property": prop,
                                        "rich_text": {
                                            "contains": value
                                        }
                                    })
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse filter_conditions: {filter_conditions}")
                    except Exception as e:
                        logger.error(f"Error building filter: {str(e)}")

                # フィルタを合成（AND条件）
                if len(filters) > 1:
                    payload["filter"] = {"and": filters}
                elif len(filters) == 1:
                    payload["filter"] = filters[0]

                # ---------------------------------------------------------
                # APIリクエストの実行
                # ---------------------------------------------------------
                # ライブラリのバージョン差異による互換性対応
                if hasattr(self.client.databases, "query"):
                    logger.info("Using client.databases.query method.")
                    response = self.client.databases.query(
                        database_id=database_id,
                        **payload
                    )
                else:
                    # client.databases.query が存在しない古いバージョンや環境でのフォールバック
                    path = f"databases/{database_id}/query"
                    logger.info(f"Using client.request fallback. Path: {path}")

                    response = self.client.request(
                        path=path,
                        method="POST",
                        body=payload
                    )
            else:
                # データベース指定なしの全体検索（search endpoint）
                # 精度が低いため、基本的には database_name を指定することを推奨
                search_params = {"query": query} if query else {}
                search_params["filter"] = {"value": "page", "property": "object"}
                response = self.client.search(**search_params)

            # ---------------------------------------------------------
            # 結果の整形
            # ---------------------------------------------------------
            # APIの生レスポンスは巨大でネストが深いため、AIが理解しやすい形に簡略化します
            simplified_results = []
            for page in response.get("results", []):
                simplified = {
                    "id": page.get("id"),
                    "url": page.get("url"),
                    "last_edited_time": page.get("last_edited_time"),
                }
                # タイトルの取得
                props = page.get("properties", {})
                title_text = "No Title"
                for prop_name, prop_val in props.items():
                    if prop_val.get("id") == "title" or prop_val.get("type") == "title":
                        title_list = prop_val.get("title", [])
                        if title_list:
                            title_text = "".join([t.get("plain_text", "") for t in title_list])
                        break
                simplified["title"] = title_text

                # 主要プロパティの抽出
                simple_props = {}
                for k, v in props.items():
                    type_ = v.get("type")
                    if type_ == "select":
                        simple_props[k] = v.get("select", {}).get("name") if v.get("select") else None
                    elif type_ == "checkbox":
                        simple_props[k] = v.get("checkbox")
                    elif type_ == "date":
                         simple_props[k] = v.get("date")

                simplified["properties"] = simple_props
                simplified_results.append(simplified)

            return simplified_results

        except APIResponseError as e:
            msg = f"Notion API Error in search: {e.code} - {str(e)}"
            logger.error(msg)
            return {"error": msg}
        except Exception as e:
            msg = f"Unexpected Error in search: {str(e)}"
            logger.error(msg)
            logger.error(traceback.format_exc())
            return {"error": msg}

    def create_page(self, database_name: str, title: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        データベースに新しいページを作成します。

        Args:
            database_name (str): 作成先のデータベース名。
            title (str): ページのタイトル。
            properties (dict): その他のプロパティ設定値。

        Returns:
            Dict: 作成結果。
        """
        logger.info(f"Creating page. DB: {database_name}, Title: {title}")

        if not self.client:
            return {"error": "Notion Client not initialized"}

        database_id = self._resolve_database_id(database_name)
        if not database_id:
            return {"error": f"Database '{database_name}' not found."}

        try:
             database_id = str(uuid.UUID(database_id))
        except ValueError:
            return {"error": f"Invalid Database ID for {database_name}"}

        if properties is None:
            properties = {}

        # タイトルプロパティ名の解決と設定
        title_prop_name = "名前" # Default fallback
        if database_name in self.notion_database_mapping:
             props = self.notion_database_mapping[database_name].get("properties", {})
             for k, v in props.items():
                 if v.get("type") == "title":
                     title_prop_name = k
                     break

        # タイトル構造の構築
        properties[title_prop_name] = {
            "title": [
                {
                    "text": {
                        "content": title
                    }
                }
            ]
        }

        try:
            response = self.client.pages.create(
                parent={"database_id": database_id},
                properties=properties
            )
            return {"status": "success", "id": response.get("id"), "url": response.get("url")}
        except APIResponseError as e:
            msg = f"Notion API Error in create_page: {e.code} - {str(e)}"
            logger.error(msg)
            return {"error": msg}
        except Exception as e:
            msg = f"Unexpected Error in create_page: {str(e)}"
            logger.error(msg)
            return {"error": msg}

    def update_page(self, page_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        既存のページを更新します。ステータス変更などで使用されます。
        """
        logger.info(f"Updating page. ID: {page_id}")

        if not self.client:
            return {"error": "Notion Client not initialized"}

        try:
            response = self.client.pages.update(
                page_id=page_id,
                properties=properties
            )
            return {"status": "success", "id": response.get("id")}
        except APIResponseError as e:
            msg = f"Notion API Error in update_page: {e.code} - {str(e)}"
            logger.error(msg)
            return {"error": msg}
        except Exception as e:
            msg = f"Unexpected Error in update_page: {str(e)}"
            logger.error(msg)
            return {"error": msg}

    def append_block(self, block_id: str, children: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        ページやブロックの下に、新しいブロック（子要素）を追加します。
        買い物リストの詳細などを追記する際に使用されます。
        """
        logger.info(f"Appending block. ID: {block_id}")

        if not self.client:
            return {"error": "Notion Client not initialized"}

        try:
            response = self.client.blocks.children.append(
                block_id=block_id,
                children=children
            )
            return {"status": "success", "results_count": len(response.get("results", []))}
        except APIResponseError as e:
            msg = f"Notion API Error in append_block: {e.code} - {str(e)}"
            logger.error(msg)
            return {"error": msg}
        except Exception as e:
            msg = f"Unexpected Error in append_block: {str(e)}"
            logger.error(msg)
            return {"error": msg}
