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

    def _normalize_uuid(self, id_str: str) -> str:
        """
        ハイフンが含まれていたりいなかったりするUUID文字列を、
        ハイフン付きの正規化されたUUID文字列（8-4-4-4-12形式）に変換します。
        変換できない場合は元の文字列を返します（API側でエラーにさせるため）。
        """
        if not id_str:
            return id_str
        try:
            # ハイフンを除去してからUUIDオブジェクト化し、文字列に戻すことで正規化
            return str(uuid.UUID(id_str.replace("-", "")))
        except ValueError:
            logger.warning(f"Failed to normalize UUID: {id_str}")
            return id_str

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

    def _format_properties_for_api(self, database_name: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        モデルから渡されたシンプルなプロパティ辞書をNotion API形式に変換します。
        既にNotion形式になっている場合はそのまま維持します。
        """
        formatted_props = {}
        for prop_name, value in properties.items():
            prop_type = self._resolve_property_type(database_name, prop_name)

            # すでに辞書型で、Notion形式っぽい構造（'select', 'date' 等のキーがある）ならそのまま
            # ただし、単純な辞書（例: {"start": "..."}）の場合もあるので、キー名で簡易判定
            if isinstance(value, dict) and prop_type in value:
                formatted_props[prop_name] = value
                continue

            # 以下、型ごとの変換処理
            if prop_type == "title":
                # タイトルは別途処理されることが多いが、念のため
                 if isinstance(value, str):
                    formatted_props[prop_name] = {"title": [{"text": {"content": value}}]}
                 else:
                     formatted_props[prop_name] = value

            elif prop_type == "select":
                if isinstance(value, str):
                    formatted_props[prop_name] = {"select": {"name": value}}
                else:
                    formatted_props[prop_name] = value

            elif prop_type == "multi_select":
                if isinstance(value, list):
                    formatted_props[prop_name] = {"multi_select": [{"name": v} for v in value]}
                elif isinstance(value, str):
                     formatted_props[prop_name] = {"multi_select": [{"name": value}]}
                else:
                    formatted_props[prop_name] = value

            elif prop_type == "date":
                if isinstance(value, str):
                    formatted_props[prop_name] = {"date": {"start": value}}
                else:
                    formatted_props[prop_name] = value

            elif prop_type == "checkbox":
                formatted_props[prop_name] = {"checkbox": bool(value)}

            elif prop_type == "rich_text":
                if isinstance(value, str):
                    formatted_props[prop_name] = {"rich_text": [{"text": {"content": value}}]}
                else:
                    formatted_props[prop_name] = value

            elif prop_type == "number":
                 try:
                     formatted_props[prop_name] = {"number": float(value)}
                 except (ValueError, TypeError) as e:
                     logger.warning(f"Failed to convert '{value}' to number for property '{prop_name}': {e}")
                     formatted_props[prop_name] = value

            elif prop_type == "url":
                formatted_props[prop_name] = {"url": value}

            elif prop_type == "status":
                if isinstance(value, str):
                    formatted_props[prop_name] = {"status": {"name": value}}
                else:
                     formatted_props[prop_name] = value

            else:
                # 不明な型はそのまま渡す（API側でエラーになるかもしれないが、勝手な変換は避ける）
                formatted_props[prop_name] = value

        return formatted_props


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

                # rich_text型のプロパティ（例: メモ）の内容も抽出する
                # これがないとAIが既存のメモを読み取って追記することができない
                for k, v in props.items():
                    if v.get("type") == "rich_text":
                        text_list = v.get("rich_text", [])
                        content = "".join([t.get("plain_text", "") for t in text_list])
                        simplified["properties"][k] = content

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

        # フォーマット変換 (Simple values -> Notion API Objects)
        formatted_properties = self._format_properties_for_api(database_name, properties)

        # タイトルが properties に含まれていても、引数の title を優先して上書きする
        formatted_properties[title_prop_name] = {
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
                properties=formatted_properties
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
        # IDの正規化（ハイフン補完など）
        page_id = self._normalize_uuid(page_id)
        logger.info(f"Updating page. ID: {page_id}")

        if not self.client:
            return {"error": "Notion Client not initialized"}

        # 更新対象のデータベースを知る術がない (page_idからは分からない) ため、
        # propertiesのキーからデータベースを推測するか、あるいは全DBを走査する...のはコストが高い。
        # ここでは、propertiesに含まれるキー名と全DBのスキーマを比較して、マッチするプロパティ型の解決を試みる。
        # ただし、同じプロパティ名が複数のDBにある場合（例: "完了フラグ"）は最初に見つかった型を使う。
        # これは完全ではないが、多くのケースで動作する。
        # より良い方法は、update_pageにもdatabase_name引数を追加することだが、
        # 既存インターフェースを変えるリスクがあるため、まずは簡易的な解決策をとる。

        # 1. propertiesのフォーマット変換
        # page_idからdatabase_idを取得するのはAPIコールが必要だが、retrieveしてからupdateするのは2度手間。
        # しかし、型解決にはスキーマが必要。
        # ここでは「全ての既知のDB定義からプロパティ名を探す」戦略をとる。

        formatted_properties = {}
        for prop_name, value in properties.items():
            prop_type = None
            found_db = None

            # プロパティ名から型を検索
            for db_name, db_info in self.notion_database_mapping.items():
                p_conf = db_info.get("properties", {}).get(prop_name)
                if p_conf:
                    prop_type = p_conf.get("type")
                    found_db = db_name
                    break

            if found_db:
                # 1つだけの辞書を作って変換メソッドを通す
                temp_dict = self._format_properties_for_api(found_db, {prop_name: value})
                formatted_properties.update(temp_dict)
            else:
                # 見つからない場合はそのまま
                formatted_properties[prop_name] = value

        try:
            response = self.client.pages.update(
                page_id=page_id,
                properties=formatted_properties
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
        # IDの正規化
        block_id = self._normalize_uuid(block_id)
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
