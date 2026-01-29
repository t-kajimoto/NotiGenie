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
    
    Args:
        notion_adapter: NotionAdapterインスタンス
        api_key: リクエストAPIキー (予備認証用、今回はmain側で認証済みとして扱う)

    Returns:
        str: JSON文字列
    """
    try:
        # Notion DBのマッピングから "todo_list" を探す (存在しない場合はエラー)
        # ※ ユーザーのDB名に合わせて適宜変更が必要な場合があるが、まずは "todo_list" をデフォルトとする
        target_db_name = "todo_list"
        if target_db_name not in notion_adapter.notion_database_mapping:
            # マッピングが見つからない場合、最初のDBを使用するフォールバック
            if notion_adapter.notion_database_mapping:
                target_db_name = list(notion_adapter.notion_database_mapping.keys())[0]
            else:
                return json.dumps({"error": "No database schema found"}, ensure_ascii=False)

        # 現在日時 (JST)
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.datetime.now(jst)
        today_str = now.strftime('%Y-%m-%d')
        three_days_ago = (now - datetime.timedelta(days=3)).strftime('%Y-%m-%d')

        # ---------------------------------------------------------
        # 1. 未完了タスク (TODO) の取得
        # ---------------------------------------------------------
        # 条件: Status != "Done" (完了以外)
        # ソート: Deadline 昇順
        # ---------------------------------------------------------
        # Notion APIのフィルタ仕様上、"Does not equal" は Status型で使えない場合があるため、
        # "Not started" OR "In progress" のように実装するのが確実だが、
        # ここでは adapter.search_database に JSONフィルタを渡す形で実装する。
        
        # 簡易的に "Status" プロパティが存在すると仮定
        # FIXME: ユーザーのDB定義依存。Statusプロパティ名が "ステータス" の可能性などを考慮する必要あり
        
        # 全件取得してPython側でフィルタ・ソートする方が柔軟かもしれないが、件数が多いと遅い。
        # ここでは検索クエリで可能な限り絞り込む。
        
        # 未完了タスクの取得
        # search_database は単純なクエリか、高度なフィルタを受け取る
        # ここでは、未完了の定義がユーザーごとに違うため、単純に全件取得してPython側で処理する戦略をとる
        # (DBサイズが巨大でない前提)
        
        all_pages = notion_adapter.search_database(database_name=target_db_name)
        
        if isinstance(all_pages, dict) and "error" in all_pages:
            return json.dumps(all_pages, ensure_ascii=False)

        todos = []
        dones = []

        for page in all_pages:
            props = page.get("properties", {})
            
            # --- プロパティ抽出 ---
            # 汎用的に取得するが、仕様書定義のキーを探す
            name = page.get("title", "No Title")
            
            # ステータスの判定 (完了ボタン: checkbox)
            is_done = False
            if "完了ボタン" in props:
                is_done = bool(props["完了ボタン"])
            elif "Status" in props:
                # Fallback for compatibility or other DBs
                status_val = props["Status"]
                if isinstance(status_val, dict):
                    status_val = status_val.get("name", "")
                is_done = str(status_val) in ["Done", "完了", "Completed", "Archived"]
            elif "ステータス" in props:
                status_val = props["ステータス"]
                if isinstance(status_val, dict):
                    status_val = status_val.get("name", "")
                is_done = str(status_val) in ["Done", "完了", "Completed", "Archived"]

            # 各種カラムの取得
            deadline = None
            if "Deadline" in props and props["Deadline"]:
                if isinstance(props["Deadline"], dict):
                    deadline = props["Deadline"].get("start")
            elif "期限" in props and props["期限"]:
                 if isinstance(props["期限"], dict):
                    deadline = props["期限"].get("start")

            display_date = ""
            if "DisplayDate" in props and props["DisplayDate"]:
                display_date = str(props["DisplayDate"])
            elif "期限表示" in props and props["期限表示"]:
                 display_date = str(props["期限表示"])

            memo = ""
            if "Memo" in props and props["Memo"]:
                memo = str(props["Memo"])
            elif "メモ" in props and props["メモ"]:
                 memo = str(props["メモ"])

            done_date = None
            if "DoneDate" in props and props["DoneDate"]:
                if isinstance(props["DoneDate"], dict):
                    done_date = props["DoneDate"].get("start")
            elif "完了日" in props and props["完了日"]:
                 if isinstance(props["完了日"], dict):
                    done_date = props["完了日"].get("start")

            item = {
                "name": name,
                "deadline": deadline,
                "display_date": display_date,
                "memo": memo,
                "done_date": done_date
            }

            if is_done:
                # 完了タスク: 直近3日以内かチェック
                # DoneDateがあればそれを見る、なければLast Edited Timeを見る
                check_date = done_date
                if not check_date:
                    last_edited = page.get("last_edited_time", "")
                    if last_edited:
                        check_date = last_edited[:10] # YYYY-MM-DD
                
                if check_date and check_date >= three_days_ago:
                    dones.append(item)
            else:
                # 未完了タスク
                todos.append(item)

        # ---------------------------------------------------------
        # ソート処理
        # ---------------------------------------------------------
        # Todo: Deadline昇順 (Deadlineがないものは最後)
        todos.sort(key=lambda x: x["deadline"] if x["deadline"] else "9999-99-99")

        # Done: DoneDate降順
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
