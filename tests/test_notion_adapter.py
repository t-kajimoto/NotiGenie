import pytest
from unittest.mock import MagicMock
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
    mapping = {"TestDB": {"id": "db-123", "description": "Test DB", "properties": {"名前": {"type": "title"}}}}
    return NotionAdapter(mapping)

def test_search_database_with_query(notion_adapter, mock_notion_client):
    # 正常系: search_database with specific DB
    mock_notion_client.request.return_value = {"results": []}

    result_json = notion_adapter.search_database(query="milk", database_name="TestDB")

    mock_notion_client.request.assert_called_with(
        path="databases/db-123/query",
        method="POST",
        body={"filter": {"property": "名前", "title": {"contains": "milk"}}}
    )
    assert isinstance(result_json, str)

def test_search_database_all(notion_adapter, mock_notion_client):
    # 正常系: search_database global
    mock_notion_client.search.return_value = {"results": []}

    notion_adapter.search_database(query="milk")

    mock_notion_client.search.assert_called_with(
        query="milk",
        filter={"value": "page", "property": "object"}
    )

def test_create_page(notion_adapter, mock_notion_client):
    # 正常系: create_page
    mock_notion_client.pages.create.return_value = {"id": "page-123", "url": "http://notion.so/page-123"}

    result_json = notion_adapter.create_page(database_name="TestDB", title="New Page")

    mock_notion_client.pages.create.assert_called()
    call_kwargs = mock_notion_client.pages.create.call_args[1]
    assert call_kwargs["parent"]["database_id"] == "db-123"
    assert call_kwargs["properties"]["名前"]["title"][0]["text"]["content"] == "New Page"

    res = json.loads(result_json)
    assert res["status"] == "success"

def test_update_page(notion_adapter, mock_notion_client):
    # 正常系: update_page
    mock_notion_client.pages.update.return_value = {"id": "page-123"}

    result_json = notion_adapter.update_page(page_id="page-123", properties={"Status": "Done"})

    mock_notion_client.pages.update.assert_called_with(
        page_id="page-123",
        properties={"Status": "Done"}
    )
    res = json.loads(result_json)
    assert res["status"] == "success"
