import json
import logging
import datetime
import pytz
from typing import List, Dict, Any
from ..core.interfaces.gateways.notion_adapter import NotionAdapter

logger = logging.getLogger(__name__)

async def get_todo_list(notion_adapter: NotionAdapter, api_key: str) -> str:
    """
    E-paper表示用のToDoリストデータを取得・整形してJSONで返します。
    統合データベース (master_db) から全カテゴリのデータを取得します。
    
    Args:
        notion_adapter: NotionAdapterインスタンス
        api_key: リクエストAPIキー (予備認証用、今回はmain側で認証済みとして扱う)

    Returns:
        str: JSON文字列
    """
    try:
        target_db_name = "master_db"
        if target_db_name not in notion_adapter.notion_database_mapping:
            if notion_adapter.notion_database_mapping:
                target_db_name = list(notion_adapter.notion_database_mapping.keys())[0]
            else:
                return json.dumps({"error": "No database schema found"}, ensure_ascii=False)

        # 現在日時 (JST)
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.datetime.now(jst)
        today_str = now.strftime('%Y-%m-%d')
        three_days_ago = (now - datetime.timedelta(days=3)).strftime('%Y-%m-%d')

        # 全件取得してPython側でフィルタ・ソートする
        all_pages = notion_adapter.search_database(database_name=target_db_name)
        
        if isinstance(all_pages, dict) and "error" in all_pages:
            return json.dumps(all_pages, ensure_ascii=False)

        todos = []
        dones = []

        for page in all_pages:
            props = page.get("properties", {})
            
            # --- プロパティ抽出 (統合DB: 新プロパティ名) ---
            name = page.get("title", "No Title")
            
            # カテゴリ
            category = ""
            if "カテゴリ" in props:
                cat_val = props["カテゴリ"]
                if isinstance(cat_val, dict):
                    category = cat_val.get("name", "")
                else:
                    category = str(cat_val) if cat_val else ""

            # 完了判定: 完了日が入っていれば完了
            is_done = False
            done_date = None
            if "完了日" in props and props["完了日"]:
                if isinstance(props["完了日"], dict):
                    done_date = props["完了日"].get("start")
                elif isinstance(props["完了日"], str):
                    done_date = props["完了日"]
                if done_date:
                    is_done = True

            # 予定日
            scheduled_date = None
            if "予定日" in props and props["予定日"]:
                if isinstance(props["予定日"], dict):
                    scheduled_date = props["予定日"].get("start")
                elif isinstance(props["予定日"], str):
                    scheduled_date = props["予定日"]

            # 予定日表示
            display_date = ""
            if "予定日表示" in props and props["予定日表示"]:
                display_date = str(props["予定日表示"])

            # メモ
            memo = ""
            if "メモ" in props and props["メモ"]:
                memo = str(props["メモ"])

            item = {
                "name": name,
                "category": category,
                "deadline": scheduled_date,
                "display_date": display_date,
                "memo": memo,
                "done_date": done_date
            }

            if is_done:
                # 完了タスク: 直近3日以内かチェック
                check_date = done_date
                if not check_date:
                    last_edited = page.get("last_edited_time", "")
                    if last_edited:
                        check_date = last_edited[:10]
                
                if check_date and check_date >= three_days_ago:
                    dones.append(item)
            else:
                # 未完了タスク
                todos.append(item)

        # ---------------------------------------------------------
        # ソート処理
        # ---------------------------------------------------------
        # Todo: 予定日昇順 (予定日がないものは最後)
        todos.sort(key=lambda x: x["deadline"] if x["deadline"] else "9999-99-99")

        # Done: 完了日降順
        dones.sort(key=lambda x: x["done_date"] if x["done_date"] else "0000-00-00", reverse=True)

        result = {
            "query_date": today_str,
            "todos": todos,
            "dones": dones
        }
        
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Error in get_todo_list: {e}", exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)
