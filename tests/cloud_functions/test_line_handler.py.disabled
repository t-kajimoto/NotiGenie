import pytest
from unittest.mock import MagicMock, AsyncMock
from cloud_functions.line_handler import LineHandler

class TestLineHandler:

    @pytest.fixture
    def mock_agents(self):
        gemini = MagicMock()
        gemini.generate_notion_command = AsyncMock()
        gemini.generate_final_response = AsyncMock()

        notion = MagicMock()
        notion.execute_tool = MagicMock()

        return gemini, notion

    @pytest.fixture
    def line_handler(self, mock_agents, mocker):
        gemini, notion = mock_agents

        # Mock env vars
        mocker.patch.dict("os.environ", {
            "LINE_CHANNEL_ACCESS_TOKEN": "test_token",
            "LINE_CHANNEL_SECRET": "test_secret"
        })

        # Mock LINE API clients
        mocker.patch("cloud_functions.line_handler.ApiClient")
        mocker.patch("cloud_functions.line_handler.MessagingApi")
        mocker.patch("cloud_functions.line_handler.WebhookHandler")

        handler = LineHandler(gemini, notion)
        return handler

    def test_handle_text_message_success(self, line_handler, mock_agents):
        gemini, notion = mock_agents

        # Setup mocks
        gemini.generate_notion_command.return_value = {
            "action": "query_database",
            "database_name": "TestDB"
        }
        notion.execute_tool.return_value = '{"results": []}'
        gemini.generate_final_response.return_value = "Done."

        # Create a mock event
        event = MagicMock()
        event.reply_token = "reply_token"
        event.message.text = "Test message"

        # Execute
        line_handler._handle_text_message(event)

        # Assertions
        gemini.generate_notion_command.assert_called_once()
        notion.execute_tool.assert_called_once()
        gemini.generate_final_response.assert_called_once()

        # Verify reply was sent
        args, _ = line_handler.messaging_api.reply_message.call_args
        assert args[0].reply_token == "reply_token"
        assert args[0].messages[0].text == "Done."

    def test_handle_text_message_error_handling(self, line_handler, mock_agents):
        gemini, notion = mock_agents

        # Setup error
        gemini.generate_notion_command.side_effect = Exception("API Error")

        # Create a mock event
        event = MagicMock()
        event.reply_token = "reply_token"
        event.message.text = "Test message"

        # Execute
        line_handler._handle_text_message(event)

        # Verify error reply was sent
        args, _ = line_handler.messaging_api.reply_message.call_args
        assert args[0].reply_token == "reply_token"
        assert "申し訳ありません" in args[0].messages[0].text
