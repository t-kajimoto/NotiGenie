"""
GeminiAdapter のテスト

現在のクリーンアーキテクチャに対応したテストケース。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os


class TestGeminiAdapter:
    """GeminiAdapterのテストクラス"""

    @pytest.fixture
    def mock_genai(self, mocker):
        """google.generativeai をモック化"""
        mock_genai = mocker.patch('cloud_functions.core.interfaces.gateways.gemini_adapter.genai')
        mock_genai.configure = MagicMock()
        return mock_genai

    @pytest.fixture
    def gemini_adapter(self, mock_genai, mocker):
        """テスト用GeminiAdapterインスタンス"""
        mocker.patch.dict(os.environ, {"GEMINI_API_KEY": "test_api_key"})

        from cloud_functions.core.interfaces.gateways.gemini_adapter import GeminiAdapter
        return GeminiAdapter(
            system_instruction_template="Test prompt: {current_date} {database_descriptions}",
            notion_database_mapping={
                "test_db": {
                    "id": "test-db-id",
                    "title": "テストDB",
                    "description": "テスト用データベース",
                    "properties": {
                        "Name": {"type": "title"},
                        "Status": {"type": "select", "options": ["Todo", "Done"]}
                    }
                }
            }
        )

    def test_init_with_api_key(self, gemini_adapter, mock_genai):
        """APIキーが設定されている場合に正常初期化される"""
        mock_genai.configure.assert_called_once_with(api_key="test_api_key")
        assert gemini_adapter.model_name == 'gemini-2.5-flash-lite'

    def test_init_without_api_key(self, mocker):
        """APIキーがない場合にValueErrorが発生する"""
        mocker.patch.dict(os.environ, {}, clear=True)
        mocker.patch('cloud_functions.core.interfaces.gateways.gemini_adapter.genai')

        from cloud_functions.core.interfaces.gateways.gemini_adapter import GeminiAdapter
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiAdapter(
                system_instruction_template="test",
                notion_database_mapping={}
            )

    def test_build_db_selection_instruction(self, gemini_adapter):
        """DB選択用プロンプトが正しく構築される"""
        instruction = gemini_adapter._build_db_selection_instruction("2024-01-15")
        assert "2024-01-15" in instruction
        assert "test_db" in instruction
        assert "テスト用データベース" in instruction

    def test_build_tool_generation_instruction(self, gemini_adapter):
        """ツール生成用プロンプトが正しく構築される"""
        schema = {
            "id": "test_db",
            "title": "テストDB",
            "description": "テスト用データベース",
            "properties": {
                "Name": {"type": "title"},
                "Status": {"type": "select", "options": ["Todo", "Done"]}
            }
        }
        instruction = gemini_adapter._build_tool_generation_instruction("2024-01-15", schema)
        assert "2024-01-15" in instruction
        assert "test_db" in instruction

    def test_sanitize_arg_with_dict(self, gemini_adapter):
        """辞書型の引数が正しくサニタイズされる"""
        result = gemini_adapter._sanitize_arg({"key": "value", "nested": {"a": 1}})
        assert result == {"key": "value", "nested": {"a": 1}}

    def test_sanitize_arg_with_list(self, gemini_adapter):
        """リスト型の引数が正しくサニタイズされる"""
        result = gemini_adapter._sanitize_arg(["a", "b", {"c": "d"}])
        assert result == ["a", "b", {"c": "d"}]

    def test_sanitize_arg_with_string(self, gemini_adapter):
        """文字列型の引数がそのまま返される"""
        result = gemini_adapter._sanitize_arg("test_string")
        assert result == "test_string"

    def test_sanitize_arg_with_number(self, gemini_adapter):
        """数値型の引数がそのまま返される"""
        result = gemini_adapter._sanitize_arg(42)
        assert result == 42

    @pytest.mark.asyncio
    async def test_select_databases_returns_list(self, gemini_adapter, mock_genai):
        """select_databasesがリストを返す"""
        # モックレスポンスの設定
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        mock_chat = MagicMock()
        mock_model.start_chat.return_value = mock_chat

        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_fn = MagicMock()
        mock_fn.name = "select_databases"
        mock_fn.args = {"db_names": ["test_db"]}
        mock_part.function_call = mock_fn
        mock_response.parts = [mock_part]
        mock_chat.send_message.return_value = mock_response

        result = await gemini_adapter.select_databases("テストクエリ", "2024-01-15")

        assert isinstance(result, list)
        assert "test_db" in result

    @pytest.mark.asyncio
    async def test_select_databases_empty_result(self, gemini_adapter, mock_genai):
        """DB選択で空リストが返る場合"""
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        mock_chat = MagicMock()
        mock_model.start_chat.return_value = mock_chat

        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_fn = MagicMock()
        mock_fn.name = "select_databases"
        mock_fn.args = {"db_names": []}
        mock_part.function_call = mock_fn
        mock_response.parts = [mock_part]
        mock_chat.send_message.return_value = mock_response

        result = await gemini_adapter.select_databases("こんにちは", "2024-01-15")

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_generate_response_without_tools(self, gemini_adapter, mock_genai):
        """ツール結果がない場合、ユーザー発言がそのままプロンプトになる"""
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_chat = MagicMock()
        mock_model.start_chat.return_value = mock_chat
        mock_response = MagicMock()
        mock_response.text = "こんにちは！"
        mock_chat.send_message.return_value = mock_response

        # tool_results=[] (空リスト)
        response = await gemini_adapter.generate_response("hello", [], [{"role": "user", "parts": ["hi"]}])

        assert response == "こんにちは！"
        # start_chatには元の履歴だけが渡されるべき (ユーザー発言は追加されない)
        mock_model.start_chat.assert_called_once()
        call_kwargs = mock_model.start_chat.call_args[1]
        assert call_kwargs["history"] == [{"role": "user", "parts": ["hi"]}]
        
        # send_messageにはユーザー発言がそのまま渡されるべき
        mock_chat.send_message.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_generate_response_with_tools(self, gemini_adapter, mock_genai):
        """ツール結果がある場合、ツール結果がプロンプトになる"""
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_chat = MagicMock()
        mock_model.start_chat.return_value = mock_chat
        mock_response = MagicMock()
        mock_response.text = "検索結果です"
        mock_chat.send_message.return_value = mock_response

        tool_results = [{"name": "search", "result": "found"}]
        await gemini_adapter.generate_response("search something", tool_results, [])

        # start_chatの履歴にはユーザー発言が含まれているべき
        mock_model.start_chat.assert_called_once()
        history_arg = mock_model.start_chat.call_args[1]["history"]
        assert len(history_arg) == 1
        assert history_arg[0]["role"] == "user"
        assert history_arg[0]["parts"][0] == "search something"

        # send_messageにはツール結果(FunctionResponse)が渡されるべき
        mock_chat.send_message.assert_called_once()
        args = mock_chat.send_message.call_args[0]
        # args[0] はリスト(tool_feedback)になっているはず
        assert isinstance(args[0], list)
