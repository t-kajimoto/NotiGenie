import pytest
from unittest.mock import MagicMock, AsyncMock
from adapter.gateways.gemini_gateway import GeminiGateway

@pytest.fixture
def mock_genai_model(mocker):
    # google.generativeai.GenerativeModel をモック化
    mock_model_cls = mocker.patch('adapter.gateways.gemini_gateway.genai.GenerativeModel')
    mock_instance = mock_model_cls.return_value
    # generate_content_async を非同期モックにする
    mock_instance.generate_content_async = AsyncMock()
    return mock_instance

@pytest.fixture
def gemini_gateway(mocker, mock_genai_model):
    mocker.patch('adapter.gateways.gemini_gateway.genai.configure')
    return GeminiGateway(
        api_key="fake_key",
        command_prompt_template="Command Prompt: {user_utterance}",
        response_prompt_template="Response Prompt: {user_utterance}",
        notion_database_mapping={"TestDB": {"id": "123", "description": "Test DB"}}
    )

@pytest.mark.asyncio
async def test_generate_notion_command_success(gemini_gateway, mock_genai_model):
    # 正常系: 正しいJSONが返ってくる場合
    mock_response = MagicMock()
    mock_response.text = '```json\n{"action": "query_database", "database_name": "TestDB"}\n```'
    mock_genai_model.generate_content_async.return_value = mock_response

    result = await gemini_gateway.generate_notion_command("テスト", "2023-01-01")
    
    assert result == {"action": "query_database", "database_name": "TestDB"}
    mock_genai_model.generate_content_async.assert_called_once()

@pytest.mark.asyncio
async def test_generate_notion_command_json_error(gemini_gateway, mock_genai_model):
    # 異常系: 壊れたJSONが返ってくる場合
    mock_response = MagicMock()
    mock_response.text = 'Invalid JSON'
    mock_genai_model.generate_content_async.return_value = mock_response

    result = await gemini_gateway.generate_notion_command("テスト", "2023-01-01")
    
    assert result["action"] == "error"
    assert "JSONの解析に失敗しました" in result["message"]

@pytest.mark.asyncio
async def test_generate_final_response_success(gemini_gateway, mock_genai_model):
    # 正常系: 応答生成
    mock_response = MagicMock()
    mock_response.text = "これはテストの応答です。"
    mock_genai_model.generate_content_async.return_value = mock_response

    result = await gemini_gateway.generate_final_response("こんにちは", "ツール実行結果")
    
    assert result == "これはテストの応答です。"
