import pytest
import json
import uuid
from unittest.mock import MagicMock
from cloud_functions.core.interfaces.gateways.notion_adapter import NotionAdapter

@pytest.fixture
def mock_notion_client(mocker):
    # Set dummy API key to ensure client initialization
    mocker.patch.dict('os.environ', {'NOTION_API_KEY': 'dummy_key'})
    mock_client = mocker.patch('cloud_functions.core.interfaces.gateways.notion_adapter.Client')
    return mock_client.return_value

@pytest.fixture
def notion_adapter(mock_notion_client):
    # Use valid UUIDs for testing validation logic
    shopping_id = str(uuid.uuid4())
    todo_id = str(uuid.uuid4())

    mapping = {
        "shopping_list": {
            "id": shopping_id,
            "properties": {
                "名前": {"type": "title"},
                "完了フラグ": {"type": "checkbox"},
                "カテゴリ": {"type": "select"},
                "ステータス": {"type": "status"},
                "メモ": {"type": "rich_text"},
                "期限": {"type": "date"}
            }
        },
        "todo_list": {
            "id": todo_id,
            "properties": {
                "Title": {"type": "title"},
                "Done": {"type": "checkbox"}
            }
        }
    }
    return NotionAdapter(mapping)

def test_search_database_with_simple_checkbox_filter(notion_adapter, mock_notion_client):
    # Setup
    filter_conditions = json.dumps({"完了フラグ": False})
    mock_notion_client.databases.query.return_value = {"results": []}
    db_id = notion_adapter.notion_database_mapping["shopping_list"]["id"]

    # Execute
    notion_adapter.search_database(
        database_name="shopping_list",
        filter_conditions=filter_conditions
    )

    # Verify
    mock_notion_client.databases.query.assert_called_once()
    call_kwargs = mock_notion_client.databases.query.call_args[1]

    assert call_kwargs['database_id'] == db_id
    assert call_kwargs['filter'] == {
        "property": "完了フラグ",
        "checkbox": {
            "equals": False
        }
    }

def test_search_database_with_select_filter(notion_adapter, mock_notion_client):
    # Setup
    filter_conditions = json.dumps({"カテゴリ": "日用品"})
    mock_notion_client.databases.query.return_value = {"results": []}

    # Execute
    notion_adapter.search_database(
        database_name="shopping_list",
        filter_conditions=filter_conditions
    )

    # Verify
    call_kwargs = mock_notion_client.databases.query.call_args[1]
    assert call_kwargs['filter'] == {
        "property": "カテゴリ",
        "select": {
            "equals": "日用品"
        }
    }

def test_search_database_with_composite_filter(notion_adapter, mock_notion_client):
    # Setup
    filter_conditions = json.dumps({"完了フラグ": False, "カテゴリ": "食べ物"})
    mock_notion_client.databases.query.return_value = {"results": []}

    # Execute
    notion_adapter.search_database(
        database_name="shopping_list",
        filter_conditions=filter_conditions
    )

    # Verify
    call_kwargs = mock_notion_client.databases.query.call_args[1]
    assert "and" in call_kwargs['filter']
    filters = call_kwargs['filter']['and']
    assert len(filters) == 2

    # Order isn't guaranteed in JSON iteration, so check presence
    expected_checkbox = {"property": "完了フラグ", "checkbox": {"equals": False}}
    expected_select = {"property": "カテゴリ", "select": {"equals": "食べ物"}}

    assert expected_checkbox in filters
    assert expected_select in filters

def test_search_database_with_query_and_filter(notion_adapter, mock_notion_client):
    # Setup
    query = "牛乳"
    filter_conditions = json.dumps({"完了フラグ": False})
    mock_notion_client.databases.query.return_value = {"results": []}

    # Execute
    notion_adapter.search_database(
        query=query,
        database_name="shopping_list",
        filter_conditions=filter_conditions
    )

    # Verify
    call_kwargs = mock_notion_client.databases.query.call_args[1]
    assert "and" in call_kwargs['filter']
    filters = call_kwargs['filter']['and']
    assert len(filters) == 2

    expected_title = {"property": "名前", "title": {"contains": "牛乳"}}
    expected_checkbox = {"property": "完了フラグ", "checkbox": {"equals": False}}

    assert expected_title in filters
    assert expected_checkbox in filters

def test_search_database_with_unknown_property_defaults_to_rich_text(notion_adapter, mock_notion_client):
    # Setup - "UnknownProp" is not in the schema fixture
    filter_conditions = json.dumps({"UnknownProp": "some value"})
    mock_notion_client.databases.query.return_value = {"results": []}

    # Execute
    notion_adapter.search_database(
        database_name="shopping_list",
        filter_conditions=filter_conditions
    )

    # Verify
    call_kwargs = mock_notion_client.databases.query.call_args[1]
    # Should fallback to rich_text contains because _resolve_property_type returns None
    # and value is string
    assert call_kwargs['filter'] == {
        "property": "UnknownProp",
        "rich_text": {
            "contains": "some value"
        }
    }

def test_search_database_with_date_filter(notion_adapter, mock_notion_client):
    # Setup
    filter_conditions = json.dumps({"期限": {"after": "2025-01-01"}})
    mock_notion_client.databases.query.return_value = {"results": []}

    # Execute
    notion_adapter.search_database(
        database_name="shopping_list",
        filter_conditions=filter_conditions
    )

    # Verify
    call_kwargs = mock_notion_client.databases.query.call_args[1]
    assert call_kwargs['filter'] == {
        "property": "期限",
        "date": {
            "after": "2025-01-01"
        }
    }

def test_search_database_invalid_json_is_ignored(notion_adapter, mock_notion_client):
    # Setup
    filter_conditions = "{invalid_json"
    mock_notion_client.databases.query.return_value = {"results": []}

    # Execute
    notion_adapter.search_database(
        database_name="shopping_list",
        filter_conditions=filter_conditions
    )

    # Verify
    # Should execute without filters (or just query if provided)
    call_kwargs = mock_notion_client.databases.query.call_args[1]
    assert "filter" not in call_kwargs # No query, no valid filter
