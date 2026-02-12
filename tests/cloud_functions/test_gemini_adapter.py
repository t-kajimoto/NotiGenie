"""
GeminiAdapter (google-genai SDK) のテスト
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os
from google import genai
from google.genai import types

class TestGeminiAdapter:
    """GeminiAdapterのテストクラス"""

    @pytest.fixture
    def mock_genai(self, mocker):
        """google.genai をモック化"""
        mock_genai = mocker.patch('cloud_functions.core.interfaces.gateways.gemini_adapter.genai')
        # Clientのモック
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        return mock_genai

    @pytest.fixture
    def gemini_adapter(self, mock_genai, mocker):
        """テスト用GeminiAdapterインスタンス"""
        mocker.patch.dict(os.environ, {"GEMINI_API_KEY": "test_api_key"})
        
        # モジュール内の google.genai.types をモック化するか、実際のクラスを使用するか
        # ここでは実際のクラスがインポートされるが、gemini_adapter内で使われるものと整合させる
        
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
        mock_genai.Client.assert_called_once_with(api_key="test_api_key")
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





    @pytest.mark.asyncio
    async def test_generate_response_message(self, gemini_adapter):
        """最終応答の生成テスト"""
        mock_response = MagicMock()
        mock_response.text = "こんにちは"
        gemini_adapter.client.models.generate_content.return_value = mock_response

        response = await gemini_adapter.generate_response("hello", [], [])
        
        assert response == "こんにちは"
        
        args, kwargs = gemini_adapter.client.models.generate_content.call_args
        # contentsにユーザー発言が含まれているか
        contents = kwargs['contents']
        assert contents[-1].role == 'user'
        assert contents[-1].parts[0].text == 'hello'

    @pytest.mark.asyncio
    async def test_convert_contents_handling(self, gemini_adapter):
        """_convert_contents handles mixed input types correctly"""
        # Firestoreからの古い履歴形式を含むテストデータ
        raw_contents = [
            # Case 1: Simple string
            "simple string",
            # Case 2: Dict with string parts (Old Firestore format) - The Target Fix
            {"role": "user", "parts": ["string part"]},
            # Case 3: Dict with dict parts (Approaching correct format)
            {"role": "model", "parts": [{"text": "dict part"}]},
        ]
        
        converted = gemini_adapter._convert_contents(raw_contents)
        
        assert len(converted) == 3
        
        # 1. Simple string -> Content(role='user', parts=[Part(text='simple string')])
        c1 = converted[0]
        assert isinstance(c1, types.Content)
        assert c1.role == 'user'
        assert c1.parts[0].text == "simple string"
        
        # 2. Dict with string parts -> Content(role='user', parts=[Part(text='string part')])
        c2 = converted[1]
        assert isinstance(c2, types.Content)
        assert c2.role == 'user'
        assert c2.parts[0].text == "string part"
        
        # 3. Dict with dict parts -> Content(role='model', parts=[Part(text='dict part')])
        c3 = converted[2]
        assert isinstance(c3, types.Content)
        assert c3.role == 'model'
        assert c3.parts[0].text == "dict part"
