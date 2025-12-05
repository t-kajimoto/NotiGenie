import pytest
from unittest.mock import MagicMock
import json
import uuid
from cloud_functions.core.interfaces.gateways.notion_adapter import NotionAdapter

class TestNotionAdapterURL:

    @pytest.fixture
    def adapter(self):
        mapping = {
            "test_db": {
                "id": "1ff1ac9c8c708098bf4ac641178c9b8d",
                "properties": {
                    "Name": {"type": "title"}
                }
            },
            "bad_db": {
                "id": "bad-id", # Invalid UUID
                "properties": {}
            },
            "empty_db": {
                "id": "",
                "properties": {}
            }
        }
        adapter = NotionAdapter(notion_database_mapping=mapping)
        adapter.client = MagicMock()
        # Ensure 'databases' is also a MagicMock so we can check calls to it
        adapter.client.databases = MagicMock()
        return adapter

    def test_search_database_valid_uuid_formatting(self, adapter):
        # Even if stored as hex string without dashes, it should be formatted with dashes in the URL
        # NOTE: This test verifies the UUID normalization logic.

        query = "test"
        adapter.search_database(query, "test_db")

        expected_uuid = str(uuid.UUID("1ff1ac9c8c708098bf4ac641178c9b8d")) # This will have dashes

        # Check if the code used the modern databases.query method (which it should by default if mocked)
        if hasattr(adapter.client.databases, 'query'):
            adapter.client.databases.query.assert_called_once()
            call_kwargs = adapter.client.databases.query.call_args[1]
            assert call_kwargs["database_id"] == expected_uuid
        else:
            # Fallback for legacy
            expected_path = f"databases/{expected_uuid}/query"
            adapter.client.request.assert_called_once()
            call_args = adapter.client.request.call_args[1]
            assert call_args["path"] == expected_path

    def test_search_database_valid_uuid_formatting_legacy(self, adapter):
        # Explicitly test the legacy path by removing the query method from the mock
        del adapter.client.databases.query

        # Mock the underlying httpx client response
        mock_response = MagicMock()
        mock_response.is_error = False
        mock_response.json.return_value = {"results": []}
        adapter.client.client.post.return_value = mock_response

        query = "test"
        adapter.search_database(query, "test_db")

        expected_uuid = str(uuid.UUID("1ff1ac9c8c708098bf4ac641178c9b8d"))
        expected_url = f"https://api.notion.com/v1/databases/{expected_uuid}/query"

        adapter.client.client.post.assert_called_once()
        call_kwargs = adapter.client.client.post.call_args[1]
        assert call_kwargs["url"] == expected_url

    def test_search_database_invalid_uuid(self, adapter):
        # Should return error and NOT call client.request
        query = "test"
        result = adapter.search_database(query, "bad_db")

        adapter.client.request.assert_not_called()
        adapter.client.databases.query.assert_not_called()
        res_json = json.loads(result)
        assert "error" in res_json
        assert "Invalid Database ID" in res_json["error"]

    def test_search_database_empty_id(self, adapter):
        # Should return error and NOT call client.request
        query = "test"
        result = adapter.search_database(query, "empty_db")

        adapter.client.request.assert_not_called()
        adapter.client.databases.query.assert_not_called()
        res_json = json.loads(result)
        # Depending on _resolve_database_id implementation, it returns None if empty string
        # If it returned None, "not found in configuration" error.
        # But _resolve_database_id was updated to strip and check.
        # Let's verify _resolve_database_id behavior for empty string

        # If ID is "", _resolve_database_id returns None (because of `if val:`)
        assert "Database 'empty_db' not found" in res_json["error"]

    def test_create_page_valid_uuid(self, adapter):
        adapter.client.pages.create.return_value = {"id": "new_page_id", "url": "http://page"}

        adapter.create_page("test_db", "My Page")

        adapter.client.pages.create.assert_called_once()
        call_args = adapter.client.pages.create.call_args[1]
        expected_uuid = str(uuid.UUID("1ff1ac9c8c708098bf4ac641178c9b8d"))
        assert call_args["parent"]["database_id"] == expected_uuid

    def test_create_page_invalid_uuid(self, adapter):
        result = adapter.create_page("bad_db", "My Page")

        adapter.client.pages.create.assert_not_called()
        res_json = json.loads(result)
        assert "error" in res_json
