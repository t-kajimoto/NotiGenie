import pytest
from unittest.mock import MagicMock
import json
from notion_client import APIResponseError
from cloud_functions.notion_handler import NotionHandler

@pytest.fixture
def mock_notion_client(mocker):
    # notion_client.Client をモック化
    mock_client_cls = mocker.patch('cloud_functions.notion_handler.Client')
    mock_instance = mock_client_cls.return_value
    return mock_instance

@pytest.fixture
def notion_handler(mock_notion_client):
    mapping = {"TestDB": {"id": "db-123", "description": "Test DB"}}
    return NotionHandler(mapping)

def test_execute_tool_query_database(notion_handler, mock_notion_client):
    # 正常系: query_database
    mock_notion_client.databases.query.return_value = {"results": []}

    args = {"database_name": "TestDB", "filter_json": {"filter": {}}}
    # 同期メソッド
    result_json = notion_handler.execute_tool("query_database", args)

    # ID変換が行われているか確認
    mock_notion_client.databases.query.assert_called_with(database_id="db-123", filter={})
    assert "results" in json.loads(result_json)

def test_execute_tool_create_page(notion_handler, mock_notion_client):
    # 正常系: create_page
    mock_notion_client.pages.create.return_value = {"id": "page-123"}

    args = {"database_name": "TestDB", "properties_json": {"Name": "New Page"}}
    result_json = notion_handler.execute_tool("create_page", args)

    # ID変換が行われているか確認
    mock_notion_client.pages.create.assert_called_with(parent={"database_id": "db-123"}, properties={"Name": "New Page"})
    assert "id" in json.loads(result_json)

def test_execute_tool_unknown_action(notion_handler):
    # 異常系: 未知のアクション
    result_json = notion_handler.execute_tool("unknown_action", {})
    result = json.loads(result_json)
    assert "error" in result
    assert "未知のアクション" in result["error"]

def test_execute_tool_api_error(notion_handler, mock_notion_client):
    # 異常系: Notion APIエラー
    error = APIResponseError(response=MagicMock(), message="API Error", code=400)
    error.body = "Bad Request"
    mock_notion_client.databases.query.side_effect = error

    args = {"database_id": "db-123", "filter_json": {}}
    result_json = notion_handler.execute_tool("query_database", args)

    result = json.loads(result_json)
    assert "Notion APIエラー" in result["error"]
