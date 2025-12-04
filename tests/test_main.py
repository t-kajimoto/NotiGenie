import pytest
from unittest.mock import MagicMock, AsyncMock
import json
import cloud_functions.main as cf_main

class TestCloudFunctionMain:

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        # Patch the global handlers in the main module
        self.mock_gemini = mocker.patch.object(cf_main, "gemini_agent")
        self.mock_notion = mocker.patch.object(cf_main, "notion_handler")
        self.mock_line_handler = mocker.patch.object(cf_main, "line_handler")

    def test_line_webhook(self):
        # Mock Request
        req = MagicMock()
        req.headers = {"X-Line-Signature": "sig"}
        req.get_data.return_value = "body"

        # Execute
        resp = cf_main.main(req)

        assert resp == "OK"
        self.mock_line_handler.handle_request.assert_called_with("body", "sig")

    def test_rpi_request_success(self):
        # Setup Async Mocks
        self.mock_gemini.generate_notion_command = AsyncMock(return_value={"action": "test"})
        self.mock_notion.execute_tool = MagicMock(return_value="result")
        self.mock_gemini.generate_final_response = AsyncMock(return_value="Response")

        # Mock Request
        req = MagicMock()
        req.headers = {}
        req.get_json.return_value = {"text": "hello", "date": "2023-01-01"}
        req.get_data.return_value = None # Ensure it doesn't try to read body as text for LINE check if not needed

        # Execute
        resp = cf_main.main(req)

        # Verify
        resp_json = json.loads(resp)
        assert resp_json["response"] == "Response"

        self.mock_gemini.generate_notion_command.assert_called_once()
        self.mock_notion.execute_tool.assert_called_once()
        self.mock_gemini.generate_final_response.assert_called_once()

    def test_rpi_request_error(self):
        # Setup Error
        self.mock_gemini.generate_notion_command = AsyncMock(side_effect=Exception("Test Error"))

        # Mock Request
        req = MagicMock()
        req.headers = {}
        req.get_json.return_value = {"text": "hello"}

        # Execute
        resp, code = cf_main.main(req) # main returns (json, 500) on error

        assert code == 500
        assert "Test Error" in resp

    def test_config_error(self, mocker):
        # Test case where handlers are None (e.g. init failed)
        mocker.patch.object(cf_main, "gemini_agent", None)

        req = MagicMock()
        resp, code = cf_main.main(req)
        assert code == 500
        assert "Server Configuration Error" in resp
