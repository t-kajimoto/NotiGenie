"""
NotionAdapter coverage improvement tests.
Focuses on edge cases, error handling, and private helper methods.
"""
import pytest
import logging
import sys
from unittest.mock import MagicMock, patch

# notion_clientの有無を確認
try:
    from notion_client import APIResponseError, Client
    from cloud_functions.core.interfaces.gateways.notion_adapter import NotionAdapter
    HAS_NOTION_CLIENT = True
except ImportError:
    HAS_NOTION_CLIENT = False
    # ダミー定義（ImportErrorを防ぐため）
    APIResponseError = Exception
    NotionAdapter = object

pytestmark = pytest.mark.skipif(not HAS_NOTION_CLIENT, reason="notion-client not installed")

class TestNotionAdapterCoverage:
    
    @pytest.fixture
    def mock_client(self, mocker):
        if not HAS_NOTION_CLIENT:
            pytest.skip("notion-client not installed")
            
        mocker.patch.dict('os.environ', {'NOTION_API_KEY': 'test_key'})
        mock = mocker.patch('cloud_functions.core.interfaces.gateways.notion_adapter.Client')
        return mock.return_value

    @pytest.fixture
    def adapter(self, mock_client):
        mapping = {
            "test_db": {
                "id": "12345678-1234-5678-1234-567812345678",
                "properties": {
                    "Name": {"type": "title"},
                    "Tags": {"type": "multi_select"},
                    "Date": {"type": "date"},
                    "Count": {"type": "number"},
                    "Status": {"type": "status"},
                    "Check": {"type": "checkbox"},
                    "Memo": {"type": "rich_text"},
                    "Link": {"type": "url"}
                }
            }
        }
        return NotionAdapter(mapping)

    def test_init_without_api_key_logs_warning(self, mocker, caplog):
        """APIキーがない場合に警告が出るか"""
        mocker.patch.dict('os.environ', {}, clear=True)
        caplog.set_level(logging.WARNING)
        
        adapter = NotionAdapter({})
        
        assert adapter.client is None
        assert "NOTION_API_KEY not set" in caplog.text

    def test_validate_connection_failures(self, adapter, mock_client, caplog):
        """接続確認の失敗パターン"""
        # APIResponseError
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        err = APIResponseError(message="Auth failed", response=mock_resp)
        err.code = 401
        
        mock_client.users.me.side_effect = err
        assert adapter.validate_connection() is False
        assert "Notion API Connection Failed: 401" in caplog.text

        # Unexpected Exception
        mock_client.users.me.side_effect = Exception("Network error")
        assert adapter.validate_connection() is False
        assert "Notion API Connection Failed (Unexpected)" in caplog.text
        
        # Client not initialized
        adapter.client = None
        assert adapter.validate_connection() is False

    def test_normalize_uuid_error(self, adapter, caplog):
        """UUID正規化失敗時の挙動"""
        invalid_uuid = "not-a-uuid"
        result = adapter._normalize_uuid(invalid_uuid)
        assert result == invalid_uuid
        assert "Failed to normalize UUID" in caplog.text

    def test_format_properties_extended(self, adapter):
        """_format_properties_for_api の詳細な分岐テスト"""
        db_name = "test_db"
        
        # Multi-select
        props = {"Tags": ["A", "B"]}
        res = adapter._format_properties_for_api(db_name, props)
        assert res["Tags"]["multi_select"][0]["name"] == "A"
        assert res["Tags"]["multi_select"][1]["name"] == "B"

        props = {"Tags": "Single"}
        res = adapter._format_properties_for_api(db_name, props)
        assert res["Tags"]["multi_select"][0]["name"] == "Single"

        # Date
        props = {"Date": "2023-01-01"}
        res = adapter._format_properties_for_api(db_name, props)
        assert res["Date"]["date"]["start"] == "2023-01-01"

        # Number
        props = {"Count": "10.5"} # String to number
        res = adapter._format_properties_for_api(db_name, props)
        assert res["Count"]["number"] == 10.5

        props = {"Count": "invalid"} # Invalid number
        res = adapter._format_properties_for_api(db_name, props)
        assert res["Count"] == "invalid" # Fallback

        # Status
        props = {"Status": "In Progress"}
        res = adapter._format_properties_for_api(db_name, props)
        assert res["Status"]["status"]["name"] == "In Progress"

        # Checkbox
        props = {"Check": 1} # Integer to bool
        res = adapter._format_properties_for_api(db_name, props)
        assert res["Check"]["checkbox"] is True

        # URL
        props = {"Link": "http://example.com"}
        res = adapter._format_properties_for_api(db_name, props)
        assert res["Link"]["url"] == "http://example.com"

        # Unknown Property (should pass through)
        props = {"Unknown": "val"}
        res = adapter._format_properties_for_api(db_name, props)
        assert res["Unknown"] == "val"

    def test_search_database_errors(self, adapter, mock_client):
        """search_database のエラー系テスト"""
        # Client not initialized
        adapter.client = None
        res = adapter.search_database("query")
        assert "Notion Client not initialized" in res["error"]
        adapter.client = mock_client # Restore

        # DB not found
        res = adapter.search_database(database_name="unknown_db")
        assert "not found in configuration" in res["error"]

        # Invalid UUID (force resolve to return invalid UUID string)
        adapter.notion_database_mapping["bad_db"] = {"id": "invalid-uuid"}
        res = adapter.search_database(database_name="bad_db")
        assert "Invalid Database ID format" in res["error"]

        # JSON Decode Error in filters
        res = adapter.search_database(database_name="test_db", filter_conditions="{invalid_json")
        # Should proceed without filter (warning log)
        mock_client.databases.query.assert_called() 

        # Exception during API call
        mock_client.databases.query.side_effect = Exception("API Crash")
        res = adapter.search_database(database_name="test_db")
        assert "Unexpected Error" in res["error"]

    def test_create_page_errors(self, adapter, mock_client):
        """create_page のエラー系テスト"""
        # API Response Error
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        err = APIResponseError(message="Bad Req", response=mock_resp)
        err.code = 400

        mock_client.pages.create.side_effect = err
        res = adapter.create_page("test_db", "Title")
        assert "Notion API Error" in res["error"]

        # Client not init
        adapter.client = None
        res = adapter.create_page("test_db", "Title")
        assert "initialized" in res["error"]

    def test_update_page_property_inference(self, adapter, mock_client):
        """update_page のプロパティ推論ロジック"""
        # "Tags" is in test_db schema as multi_select
        props = {"Tags": ["New Tag"]}
        
        mock_client.pages.update.return_value = {"id": "page-1"}
        adapter.update_page("page-1", props)
        
        # Verify call arguments
        assert mock_client.pages.update.called
        call_args = mock_client.pages.update.call_args[1]
        
        # Should be formatted as multi_select object because it inferred the type from mapping
        assert "multi_select" in call_args["properties"]["Tags"]
        assert call_args["properties"]["Tags"]["multi_select"][0]["name"] == "New Tag"

    def test_append_block(self, adapter, mock_client):
        """append_block のテスト"""
        # Success
        mock_client.blocks.children.append.return_value = {"results": [{}]}
        res = adapter.append_block("block-1", [])
        
        # Verify success structure depending on actual implementation
        if "status" in res:
             assert res["status"] == "success"
        else:
             # Fallback check if 'status' key is not present in success response of real implementation
             assert "results_count" in res

        # Client not init
        adapter.client = None
        res = adapter.append_block("block-1", [])
        assert "initialized" in res["error"]
        adapter.client = mock_client

        # API Error
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        err = APIResponseError(message="Err", response=mock_resp)
        err.code = 500
        
        mock_client.blocks.children.append.side_effect = err
        res = adapter.append_block("block-1", [])
        assert "Notion API Error" in res["error"]
