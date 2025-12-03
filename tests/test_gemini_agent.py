import pytest
from unittest.mock import MagicMock, AsyncMock
from cloud_functions.gemini_agent import GeminiAgent

@pytest.fixture
def mock_genai_model(mocker):
    # google.generativeai.GenerativeModel をモック化
    mock_model_cls = mocker.patch('cloud_functions.gemini_agent.genai.GenerativeModel')
    mock_instance = mock_model_cls.return_value
    # generate_content_async を非同期モックにする
    mock_instance.generate_content_async = AsyncMock()
    return mock_instance

@pytest.fixture
def gemini_agent(mocker, mock_genai_model):
    mocker.patch('cloud_functions.gemini_agent.genai.configure')
    return GeminiAgent(
        command_prompt_template="Command Prompt: {user_utterance}",
        response_prompt_template="Response Prompt: {user_utterance}",
        notion_database_mapping={"TestDB": {"id": "123", "description": "Test DB"}}
    )

@pytest.mark.asyncio
async def test_generate_notion_command_success(gemini_agent, mock_genai_model):
    # 正常系: 正しいJSONが返ってくる場合
    mock_response = MagicMock()
    mock_response.text = '```json\n{"action": "query_database", "database_name": "TestDB"}\n```'
    mock_genai_model.generate_content_async.return_value = mock_response

    result = await gemini_agent.generate_notion_command("テスト", "2023-01-01")

    assert result == {"action": "query_database", "database_name": "TestDB"}
    mock_genai_model.generate_content_async.assert_called_once()

@pytest.mark.asyncio
async def test_generate_notion_command_json_error(gemini_agent, mock_genai_model):
    # 異常系: 壊れたJSONが返ってくる場合
    mock_response = MagicMock()
    mock_response.text = 'Invalid JSON'
    mock_genai_model.generate_content_async.return_value = mock_response

    result = await gemini_agent.generate_notion_command("テスト", "2023-01-01")

    assert result["action"] == "error"
    # メッセージは英語に変更されている
    assert "JSON parse error" in result["message"]

@pytest.mark.asyncio
async def test_generate_final_response_success(gemini_agent, mock_genai_model):
    # 正常系: 応答生成
    mock_response = MagicMock()
    mock_response.text = "これはテストの応答です。"
    mock_genai_model.generate_content_async.return_value = mock_response

    result = await gemini_agent.generate_final_response("こんにちは", "ツール実行結果")

    assert result == "これはテストの応答です。"
