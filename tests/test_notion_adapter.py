import pytest
from unittest.mock import MagicMock, patch
import json
import os
from notion_client import APIResponseError
from cloud_functions.core.interfaces.gateways.notion_adapter import NotionAdapter

@pytest.fixture
def mock_notion_client(mocker):
    # notion_client.Client をモック化
    mock_client_cls = mocker.patch('cloud_functions.core.interfaces.gateways.notion_adapter.Client')
    mock_instance = mock_client_cls.return_value
    return mock_instance

@pytest.fixture
def notion_adapter(mock_notion_client, monkeypatch):
    # テスト用に環境変数を設定（dummyだと初期化されないため）
    monkeypatch.setenv("NOTION_API_KEY", "test_key")
    mapping = {"TestDB": {"id": "db-123", "description": "Test DB"}}
    return NotionAdapter(mapping)

def test_execute_tool_query_database(notion_adapter, mock_notion_client):
    # 正常系: query_database
    # 修正対応: client.request をモックする
    mock_notion_client.request.return_value = {"results": []}

    args = {"database_name": "TestDB", "filter_json": {"filter": {}}}
    # 同期メソッド
    result_json = notion_adapter.execute_tool("query_database", args)

    # ID変換が行われているか確認
    # NotionAdapter実装に合わせて修正: client.requestが呼ばれることを確認
    mock_notion_client.request.assert_called_with(
        path="databases/db-123/query",
        method="POST",
        body={}
    )
    assert "results" in json.loads(result_json)

def test_execute_tool_query_database_with_name_as_id(notion_adapter, mock_notion_client):
    # 修正確認: database_id に名前が入っていた場合の自動解決
    mock_notion_client.request.return_value = {"results": []}

    # "TestDB" is the key in mapping, ID is "db-123"
    args = {"database_id": "TestDB", "filter_json": {}}
    result_json = notion_adapter.execute_tool("query_database", args)

    mock_notion_client.request.assert_called_with(
        path="databases/db-123/query",
        method="POST",
        body={}
    )
    assert "results" in json.loads(result_json)

def test_execute_tool_create_page(notion_adapter, mock_notion_client):
    # 正常系: create_page
    mock_notion_client.pages.create.return_value = {"id": "page-123"}

    args = {"database_name": "TestDB", "properties_json": {"Name": "New Page"}}
    result_json = notion_adapter.execute_tool("create_page", args)

    # ID変換が行われているか確認
    # create_pageでは parent={"database_id": ...} と properties={...} が渡される
    mock_notion_client.pages.create.assert_called_with(parent={"database_id": "db-123"}, properties={"Name": "New Page"})
    assert "id" in json.loads(result_json)

def test_execute_tool_unknown_action(notion_adapter):
    # 異常系: 未知のアクション
    result_json = notion_adapter.execute_tool("unknown_action", {})
    result = json.loads(result_json)
    assert "error" in result
    assert "未知のアクション" in result["error"]

def test_execute_tool_api_error(notion_adapter, mock_notion_client):
    # 異常系: Notion APIエラー
    error = APIResponseError(response=MagicMock(), message="API Error", code=400)
    error.body = "Bad Request"
    # mock_notion_client.databases.query.side_effect = error
    mock_notion_client.request.side_effect = error

    args = {"database_id": "db-123", "filter_json": {}}

    # 変更後: 例外が送出されることを確認
    with pytest.raises(APIResponseError):
        notion_adapter.execute_tool("query_database", args)
