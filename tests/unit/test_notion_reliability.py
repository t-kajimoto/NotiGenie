import unittest
from unittest.mock import MagicMock, patch
from tenacity import RetryError
from notion_client import APIResponseError
from cloud_functions.core.interfaces.gateways.notion_adapter import NotionAdapter

class TestNotionAdapterReliability(unittest.TestCase):
    def setUp(self):
        self.valid_uuid = "00000000-0000-0000-0000-000000000000"
        self.mock_mapping = {"test_db": {"id": self.valid_uuid, "properties": {"Name": {"type": "title"}}}}
        with patch.dict('os.environ', {'NOTION_API_KEY': 'dummy_key'}):
            self.adapter = NotionAdapter(self.mock_mapping)
            self.adapter.client = MagicMock()

    def test_search_database_success(self):
        """Test successful search without retry."""
        self.adapter.client.databases.query.return_value = {"results": []}
        result = self.adapter.search_database(database_name="test_db", query="test")
        self.assertIsInstance(result, list)
        self.adapter.client.databases.query.assert_called_once()

    def test_search_database_retry_on_500(self):
        """Test retry logic on 500 error."""
        # 500 error then success
        error_500 = APIResponseError(response=MagicMock(), message="Server Error", code="internal_server_error")
        error_500.status = 500
        
        self.adapter.client.databases.query.side_effect = [error_500, error_500, {"results": []}]
        
        result = self.adapter.search_database(database_name="test_db", query="test")
        self.assertIsInstance(result, list)
        self.assertEqual(self.adapter.client.databases.query.call_count, 3)

    def test_search_database_fail_after_retries(self):
        """Test failure after max retries."""
        error_500 = APIResponseError(response=MagicMock(), message="Server Error", code="internal_server_error")
        error_500.status = 500
        
        self.adapter.client.databases.query.side_effect = error_500
        
        result = self.adapter.search_database(database_name="test_db", query="test")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("Max retries exceeded", result["error"])
        
    def test_create_page_400_no_retry(self):
        """Test non-retryable error (400) does not retry."""
        error_400 = APIResponseError(response=MagicMock(), message="Bad Request", code="validation_error")
        error_400.status = 400
        # Mocking __str__ to behave predictably
        error_400.__str__ = MagicMock(return_value="Bad Request")
        
        self.adapter.client.pages.create.side_effect = error_400
        
        result = self.adapter.create_page(database_name="test_db", title="test")
        # Matches: Notion API Error in create_page (Non-retryable): validation_error - Bad Request
        self.assertIn("Notion API Error in create_page (Non-retryable): validation_error - Bad Request", result.get("error"))
        self.adapter.client.pages.create.assert_called_once() # No retry

if __name__ == '__main__':
    unittest.main()
