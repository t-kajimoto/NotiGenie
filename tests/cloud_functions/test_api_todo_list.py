import pytest
import json
import datetime
import sys
from unittest.mock import MagicMock

# ローカル環境で notion_client がない場合の対策
# テスト実行前にモジュールをモック化する
try:
    import notion_client
except ImportError:
    sys.modules["notion_client"] = MagicMock()

from cloud_functions.api.todo_list import get_todo_list

@pytest.fixture
def mock_notion_adapter():
    mock = MagicMock()
    # NotionAdapterクラスの型チェックを回避するためにモックオブジェクトを使用
    # get_todo_list内で型ヒントに使われているが、実行時はダックタイピングで動作する
    mock.notion_database_mapping = {
        "todo_list": {"id": "db_uuid", "properties": {}}
    }
    return mock

@pytest.mark.asyncio
async def test_get_todo_list_success(mock_notion_adapter):
    """正常系: TodoとDoneが正しく分類・ソートされること"""
    
    # -------------------------------------------------------------------------
    # Mock Data Setup
    # -------------------------------------------------------------------------
    # 現在日時 (固定)
    today = datetime.date.today().strftime('%Y-%m-%d')
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    four_days_ago = (datetime.date.today() - datetime.timedelta(days=4)).strftime('%Y-%m-%d')
    future = "2099-12-31"

    # Notion search results
    mock_notion_adapter.search_database.return_value = [
        # 1. 未完了: 期限近い (表示されるべき)
        {
            "title": "Task A (Urgent)",
            "properties": {
                "Status": {"name": "Not started"},
                "Deadline": {"start": yesterday}, # 昨日期限（期限切れ）
                "DisplayDate": "昨日まで",
                "Memo": "急ぎ"
            }
        },
        # 2. 未完了: 期限遠い (表示されるべき)
        {
            "title": "Task B (Future)",
            "properties": {
                "Status": {"name": "In progress"},
                "Deadline": {"start": future},
                "DisplayDate": "いつか",
            }
        },
        # 3. 完了: 昨日 (表示されるべき)
        {
            "title": "Task Done A",
            "properties": {
                "Status": {"name": "Done"},
                "DoneDate": {"start": yesterday},
                "Deadline": {"start": yesterday}
            }
        },
        # 4. 完了: 4日前 (表示されないべき)
        {
            "title": "Task Done Old",
            "properties": {
                "Status": {"name": "Done"},
                "DoneDate": {"start": four_days_ago}
            }
        },
        # 5. 未完了: 期限なし (最後に表示)
        {
            "title": "Task No Deadline",
            "properties": {
                "Status": {"name": "Not started"},
                # Deadline なし
            }
        }
    ]

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------
    response_json = await get_todo_list(mock_notion_adapter, "dummy_key")
    data = json.loads(response_json)

    # -------------------------------------------------------------------------
    # Assertion
    # -------------------------------------------------------------------------
    assert "query_date" in data
    todos = data["todos"]
    dones = data["dones"]

    # Todo件数: 3件 (A, B, No Deadline)
    assert len(todos) == 3
    # ソート順: A(昨日) -> B(未来) -> No Deadline(None)
    assert todos[0]["name"] == "Task A (Urgent)"
    assert todos[1]["name"] == "Task B (Future)"
    assert todos[2]["name"] == "Task No Deadline"

    # Done件数: 1件 (Done Aのみ。Oldは除外)
    assert len(dones) == 1
    assert dones[0]["name"] == "Task Done A"

@pytest.mark.asyncio
async def test_get_todo_list_no_db_mapping(mock_notion_adapter):
    """DBマッピングがない場合のエラー"""
    mock_notion_adapter.notion_database_mapping = {}
    
    response_json = await get_todo_list(mock_notion_adapter, "dummy_key")
    data = json.loads(response_json)
    
    assert "error" in data
    assert "No database schema" in data["error"]

@pytest.mark.asyncio
async def test_get_todo_list_text_properties(mock_notion_adapter):
    """プロパティがテキスト型（Status="完了"など）で返ってきた場合の互換性"""
    
    mock_notion_adapter.search_database.return_value = [
        {
            "title": "Text Prop Task",
            "properties": {
                "ステータス": "完了", # 辞書ではなく文字列
                "期限": {"start": "2024-01-01"},
                "メモ": "テキストメモ"
            }
        }
    ]
    
    # search_databaseの戻り値が想定外のエラーdictの場合
    # (ここでは正常系のデータのバリエーションとしてのテストではなく、ロジックが対応しているか)
    
    response_json = await get_todo_list(mock_notion_adapter, "dummy_key")
    data = json.loads(response_json)
    
    # 完了扱いになるか？ (ロジック実装依存)
    # 現在の実装では ["Done", "完了", "Completed"] をチェックしている
    dones = data["dones"]
    # 完了日はLast Editedから推測される（DoneDateがないため）
    # MockにLast Editedがないので、Noneになり除外される可能性がある
    # → ロジック修正が必要か？ テストデータに last_edited_time を追加する
    
    # テスト修正: last_edited_timeを追加
    mock_notion_adapter.search_database.return_value[0]["last_edited_time"] = datetime.datetime.now().isoformat()
    
    response_json = await get_todo_list(mock_notion_adapter, "dummy_key")
    data = json.loads(response_json)
    
    # エラーが返ってきていないか確認
    assert "error" not in data, f"API returned error: {data.get('error')}"

    dones = data["dones"]
    assert len(dones) == 1
    assert dones[0]["name"] == "Text Prop Task"
    assert dones[0]["memo"] == "テキストメモ"
