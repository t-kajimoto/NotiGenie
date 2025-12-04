import pytest
from unittest.mock import MagicMock, AsyncMock
import json
import cloud_functions.main as cf_main

class TestCloudFunctionMain:

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        # Patch the global handlers in the main module
        # Note: In the new architecture, these are 'line_controller' and 'process_message_use_case'
        self.mock_line_controller = MagicMock()
        self.mock_use_case = MagicMock()

        mocker.patch.object(cf_main, "line_controller", self.mock_line_controller)
        mocker.patch.object(cf_main, "process_message_use_case", self.mock_use_case)

    def test_line_webhook(self):
        # Mock Request
        req = MagicMock()
        req.headers = {"X-Line-Signature": "sig"}
        req.get_data.return_value = "body"

        # Execute
        resp = cf_main.main(req)

        assert resp == "OK"
        self.mock_line_controller.handle_request.assert_called_with("body", "sig")

    def test_rpi_request_success(self):
        # Setup Async Mocks
        self.mock_use_case.execute = AsyncMock(return_value="Response")

        # Mock Request
        req = MagicMock()
        req.headers = {}
        req.get_json.return_value = {"text": "hello", "date": "2023-01-01"}
        req.get_data.return_value = None

        # Execute
        resp = cf_main.main(req)

        # Verify
        resp_json = json.loads(resp)
        assert resp_json["response"] == "Response"

        self.mock_use_case.execute.assert_called_once()

    def test_rpi_request_error(self):
        # Setup Error
        self.mock_use_case.execute = AsyncMock(side_effect=Exception("Test Error"))

        # Mock Request
        req = MagicMock()
        req.headers = {}
        req.get_json.return_value = {"text": "hello"}

        # Execute
        resp = cf_main.main(req) # main returns (json, 500) on error

        assert isinstance(resp, tuple)
        assert resp[1] == 500
        assert "Test Error" in resp[0]

    def test_config_error(self, mocker):
        # Test case where handlers are None (e.g. init failed)
        mocker.patch.object(cf_main, "process_message_use_case", None)

        req = MagicMock()
        resp = cf_main.main(req)
        # main returns "Server Internal Configuration Error...", 500
        assert isinstance(resp, tuple)
        assert resp[1] == 500
        assert "Server Internal Configuration Error" in resp[0]
