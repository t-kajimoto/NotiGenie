import os
import json
import logging
import sys
import traceback
import uuid
from typing import Dict, Any, Union, Optional, List
from notion_client import Client, APIResponseError
from ...domain.interfaces import INotionRepository

# ロガーの設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

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
            logger.info("Notion Client initialized successfully.")
        else:
            self.client = None
            if self.api_key != "dummy":
                logger.warning("Warning: NOTION_API_KEY not set.")

    def validate_connection(self) -> bool:
        """
        Notion APIへの接続を検証します。
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
        """データベース名からIDを解決します。"""
        if not database_name:
            return None

        # マッピングに名前があればそのIDを返す
        if database_name in self.notion_database_mapping:
            val = self.notion_database_mapping[database_name].get("id")
            if val:
                return str(val).strip()

        return None

    def search_database(self, query: str, database_name: Optional[str] = None) -> str:
        """
        データベースからページを検索します。
        """
        logger.info(f"Searching database. Query: {query}, DB Name: {database_name}")

        if not self.client:
            return json.dumps({"error": "Notion Client not initialized"})

        try:
            database_id = None
            if database_name:
                database_id = self._resolve_database_id(database_name)
                if not database_id:
                     return json.dumps({"error": f"Database '{database_name}' not found in configuration."})

            # Validate UUID format if database_id is present
            if database_id:
                try:
                    # Normalize UUID format (e.g. add hyphens if missing) to ensure valid URL
                    database_id = str(uuid.UUID(database_id))
                except ValueError:
                    msg = f"Invalid Database ID format: {database_id}"
                    logger.error(msg)
                    return json.dumps({"error": msg})

                # 特定のDB内を検索 (databases.query)
                payload = {}
                if query:
                    # タイトルプロパティ名を特定
                    title_prop = "Name" # default
                    if database_name in self.notion_database_mapping:
                         props = self.notion_database_mapping[database_name].get("properties", {})
                         for k, v in props.items():
                             if v.get("type") == "title":
                                 title_prop = k
                                 break

                    payload["filter"] = {
                        "property": title_prop,
                        "title": {
                            "contains": query
                        }
                    }

                # 2.7.0 workaround
                # Note: Notion API expects UUID for database_id. uuid.UUID() ensures it is formatted correctly.
                response = self.client.request(
                    path=f"databases/{database_id}/query",
                    method="POST",
                    body=payload
                )
            else:
                # 全体検索 (search endpoint)
                search_params = {"query": query} if query else {}
                search_params["filter"] = {"value": "page", "property": "object"}
                response = self.client.search(**search_params)

            # 結果を間引く
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

            return json.dumps(simplified_results, ensure_ascii=False)

        except APIResponseError as e:
            msg = f"Notion API Error in search: {e.code} - {str(e)}"
            logger.error(msg)
            return json.dumps({"error": msg})
        except Exception as e:
            msg = f"Unexpected Error in search: {str(e)}"
            logger.error(msg)
            logger.error(traceback.format_exc())
            return json.dumps({"error": msg})

    def create_page(self, database_name: str, title: str, properties: Optional[Dict[str, Any]] = None) -> str:
        """
        データベースに新しいページを作成します。
        """
        logger.info(f"Creating page. DB: {database_name}, Title: {title}")

        if not self.client:
            return json.dumps({"error": "Notion Client not initialized"})

        database_id = self._resolve_database_id(database_name)
        if not database_id:
            return json.dumps({"error": f"Database '{database_name}' not found."})

        # Validate UUID
        try:
             database_id = str(uuid.UUID(database_id))
        except ValueError:
            return json.dumps({"error": f"Invalid Database ID for {database_name}"})

        if properties is None:
            properties = {}

        # タイトルプロパティの設定
        title_prop_name = "名前" # Default fallback
        if database_name in self.notion_database_mapping:
             props = self.notion_database_mapping[database_name].get("properties", {})
             for k, v in props.items():
                 if v.get("type") == "title":
                     title_prop_name = k
                     break

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
            return json.dumps({"status": "success", "id": response.get("id"), "url": response.get("url")})
        except APIResponseError as e:
            msg = f"Notion API Error in create_page: {e.code} - {str(e)}"
            logger.error(msg)
            return json.dumps({"error": msg})
        except Exception as e:
            msg = f"Unexpected Error in create_page: {str(e)}"
            logger.error(msg)
            return json.dumps({"error": msg})

    def update_page(self, page_id: str, properties: Dict[str, Any]) -> str:
        """
        ページを更新します。
        """
        logger.info(f"Updating page. ID: {page_id}")

        if not self.client:
            return json.dumps({"error": "Notion Client not initialized"})

        try:
            response = self.client.pages.update(
                page_id=page_id,
                properties=properties
            )
            return json.dumps({"status": "success", "id": response.get("id")})
        except APIResponseError as e:
            msg = f"Notion API Error in update_page: {e.code} - {str(e)}"
            logger.error(msg)
            return json.dumps({"error": msg})
        except Exception as e:
            msg = f"Unexpected Error in update_page: {str(e)}"
            logger.error(msg)
            return json.dumps({"error": msg})

    def append_block(self, block_id: str, children: List[Dict[str, Any]]) -> str:
        """
        ブロックに子ブロックを追加します。
        """
        logger.info(f"Appending block. ID: {block_id}")

        if not self.client:
            return json.dumps({"error": "Notion Client not initialized"})

        try:
            response = self.client.blocks.children.append(
                block_id=block_id,
                children=children
            )
            return json.dumps({"status": "success", "results_count": len(response.get("results", []))})
        except APIResponseError as e:
            msg = f"Notion API Error in append_block: {e.code} - {str(e)}"
            logger.error(msg)
            return json.dumps({"error": msg})
        except Exception as e:
            msg = f"Unexpected Error in append_block: {str(e)}"
            logger.error(msg)
            return json.dumps({"error": msg})
