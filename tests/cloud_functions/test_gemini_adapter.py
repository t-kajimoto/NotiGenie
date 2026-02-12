import pytest
import asyncio
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
    assert len(call_args.kwargs["contents"]) == 1 # User utterance only (Reflection moved to system_instruction)

@pytest.mark.asyncio
async def test_generate_response_uses_dynamic_system_instruction(adapter):
    """回答生成時にツール結果に応じたシステムプロンプトが注入されるかを確認"""
    adapter.client.models.generate_content = MagicMock()
    
    # Clear the fixed response_instruction so it uses the mocked _get_response_instruction
    adapter.response_instruction = ""
    # Mocking _get_response_instruction to return a template
    adapter._get_response_instruction = MagicMock(return_value="{tool_execution_status}\nBase instruction\n{research_results}")
    
    # 1. ツール実行なしの場合
    await adapter.generate_response("hello", [], [])
    call_args = adapter.client.models.generate_content.call_args
    system_instruction = call_args.kwargs["config"].system_instruction
    assert "ツールは1つも実行されませんでした" in system_instruction
    
    # 2. ツール実行ありの場合
    await adapter.generate_response("hello", [{"name": "test", "result": "ok"}], [])
    call_args = adapter.client.models.generate_content.call_args
    system_instruction = call_args.kwargs["config"].system_instruction
    assert "ツール実行結果は 1 件です" in system_instruction

    # 3. 調査結果がある場合 (Round 4)
    research_results = "HoneyMoon in Hawaii"
    adapter._get_response_instruction = MagicMock(return_value="{tool_execution_status}\n{research_results}")
    await adapter.generate_response("hello", [], [], research_results=research_results)
    call_args = adapter.client.models.generate_content.call_args
    system_instruction = call_args.kwargs["config"].system_instruction
    assert "HoneyMoon in Hawaii" in system_instruction

def test_prompt_paths_resolve(adapter):
    """プロンプトファイルのパスが正しく解決され、実体が存在するかを確認"""
    import os
    print(f"System Instruction Path: {adapter.system_instruction_path}")
    print(f"Response Instruction Path: {adapter.response_instruction_path}")
    assert os.path.exists(adapter.system_instruction_path)
    assert os.path.exists(adapter.response_instruction_path)

@pytest.mark.asyncio
async def test_generate_tool_calls_uses_deterministic_config(adapter):
    """ツール生成時に temperature=0.0 と Proximal Reminder が使われることを確認 (Round 5)"""
    adapter.client.models.generate_content = MagicMock()
    
    # Mock response to avoid parse errors
    mock_response = MagicMock()
    mock_response.text = "[]"
    adapter.client.models.generate_content.return_value = mock_response

    user_utterance = "ハネムーンの情報を保存して"
    # Use a minimal but valid schema
    single_db_schema = {
        "id": "master_db", 
        "title": "Task List",
        "description": "test", 
        "properties": {}
    }
    
    await adapter.generate_tool_calls(user_utterance, "2026-02-12", [], single_db_schema)
    
    call_args = adapter.client.models.generate_content.call_args
    config = call_args.kwargs["config"]
    contents = call_args.kwargs["contents"]
    
    # 1. Temperature が 0.0 であること
    assert config.temperature == 0.0
    
    # 2. User Utterance に Proximal Reminder が含まれていること
    user_text = contents[0].parts[0].text
    assert user_utterance in user_text
    assert "必ず search_database を実行してください" in user_text

    # 3. tools が渡されていること (Round 6)
    assert call_args.kwargs["config"].tools is not None
    assert len(call_args.kwargs["config"].tools) > 0

    # 4. 関数がある場合は tool_config (FunctionCallingConfig) が設定されていること (Round 7)
    assert call_args.kwargs["config"].tool_config is not None
    assert call_args.kwargs["config"].tool_config.function_calling_config is not None

@pytest.mark.asyncio
async def test_perform_research_uses_shared_config(adapter):
    """リサーチ時に適切なツール構成が使われることを確認 (Round 6)"""
    adapter.client.models.generate_content = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "調査結果"
    adapter.client.models.generate_content.return_value = mock_response

    await adapter.perform_research("カフェを調べて", "2026-02-12")
    
    call_args = adapter.client.models.generate_content.call_args
    config = call_args.kwargs["config"]
    
    # 1. tools に Google Search が含まれていること
    assert config.tools is not None
    assert any(hasattr(t, 'google_search') or 'google_search' in str(t) for t in config.tools)

    # 2. 関数がない場合は tool_config (FunctionCallingConfig) が None であること (Round 7)
    # これにより 400 INVALID_ARGUMENT を回避
    assert config.tool_config is None

