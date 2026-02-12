import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from google.genai import types
from cloud_functions.core.interfaces.gateways.gemini_adapter import GeminiAdapter

@pytest.fixture
def mock_genai_client():
    with patch("cloud_functions.core.interfaces.gateways.gemini_adapter.genai.Client") as mock:
        yield mock

@pytest.fixture
def adapter(mock_genai_client):
    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key"}):
        adapter = GeminiAdapter(
            system_instruction_template="System Instruction Template",
            notion_database_mapping={"master_db": {"id": "db_123"}},
            response_instruction="Response Instruction"
        )
        return adapter

def test_convert_to_gemini_contents_initial_turn(adapter):
    """初回ターン: ユーザー発言のみ"""
    user_utterance = "Hello"
    history = []
    tool_results = []
    current_turn_history = []

    contents = adapter._convert_to_gemini_contents(user_utterance, history, tool_results, current_turn_history)

    assert len(contents) == 1
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "Hello"

def test_convert_to_gemini_contents_with_history(adapter):
    """履歴あり: 履歴 + ユーザー発言"""
    user_utterance = "Next"
    history = [{"role": "user", "parts": ["Prev"]}, {"role": "model", "parts": ["Ans"]}]
    tool_results = []
    current_turn_history = []

    contents = adapter._convert_to_gemini_contents(user_utterance, history, tool_results, current_turn_history)

    assert len(contents) == 3
    assert contents[0].role == "user"
    assert contents[1].role == "model"
    assert contents[2].role == "user"
    assert contents[2].parts[0].text == "Next"

def test_convert_to_gemini_contents_multi_turn(adapter):
    """マルチターン中: ユーザー発言 + モデルツール呼び出し + 関数応答"""
    user_utterance = "Find text"
    history = [] # 簡略化
    tool_results = [] # ここでは使われない（current_turn_historyに含まれる前提）
    
    current_turn_history = [
        {
            "role": "model",
            "parts": [{"function_call": {"name": "search", "args": {"q": "text"}}}]
        },
        {
            "role": "function",
            "parts": [{"function_response": {"name": "search", "response": {"content": "found"}}}]
        }
    ]

    contents = adapter._convert_to_gemini_contents(user_utterance, history, tool_results, current_turn_history)

    # Expect: User -> Model(Call) -> Tool(Result)
    assert len(contents) == 3
    
    # 1. User
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "Find text"
    
    # 2. Model (Tool Call)
    assert contents[1].role == "model"
    assert contents[1].parts[0].function_call.name == "search"
    
    # 3. Tool (Function Response) - Adapter converts 'function' role to 'tool' or keeps as is depending on implementation
    # output implementation uses 'tool' role for function response
    assert contents[2].role == "tool"
    assert contents[2].parts[0].function_response.name == "search"

@pytest.mark.asyncio
async def test_generate_response_calls_api(adapter):
    """generate_responseが正しくAPIを呼ぶか"""
    user_utterance = "Summarize"
    tool_results = []
    
    # Mock API response
    mock_response = MagicMock()
    mock_response.text = "Summary"
    adapter.client.models.generate_content.return_value = mock_response

    # Call
    response = await adapter.generate_response(user_utterance, tool_results)

    assert response == "Summary"
    adapter.client.models.generate_content.assert_called_once()
    
    # Check args
    call_args = adapter.client.models.generate_content.call_args
    assert call_args.kwargs["model"] == adapter.model_name
    assert len(call_args.kwargs["contents"]) == 1 # User utterance only

def test_prompt_paths_resolve(adapter):
    """プロンプトファイルのパスが正しく解決され、実体が存在するかを確認"""
    import os
    print(f"System Instruction Path: {adapter.system_instruction_path}")
    print(f"Response Instruction Path: {adapter.response_instruction_path}")
    assert os.path.exists(adapter.system_instruction_path)
    assert os.path.exists(adapter.response_instruction_path)
