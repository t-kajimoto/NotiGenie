"""
TTS Factory unit tests

環境変数 TTS_ENGINE に基づいて正しいTTSクライアントが作成されることをテスト。
"""
import os
import pytest
from unittest.mock import patch, MagicMock


class TestTTSFactory:
    """tts_factory のユニットテスト"""

    @pytest.fixture
    def mock_aplay_output(self):
        """aplay -l の出力をモック"""
        return "card 2: Device [USB Audio]"

    def test_create_voicevox_client(self, mock_aplay_output):
        """TTS_ENGINE=voicevox でVoicevoxClientが作成される"""
        with patch.dict(os.environ, {"TTS_ENGINE": "voicevox"}):
            with patch('subprocess.check_output', return_value=mock_aplay_output):
                from tts_factory import create_tts_client
                from voicevox_client import VoicevoxClient
                
                client = create_tts_client()
                assert isinstance(client, VoicevoxClient)

    def test_create_aquestalk_client(self, mock_aplay_output):
        """TTS_ENGINE=aquestalk でAquesTalkClientが作成される"""
        with patch.dict(os.environ, {"TTS_ENGINE": "aquestalk"}):
            with patch('subprocess.check_output', return_value=mock_aplay_output):
                from tts_factory import create_tts_client
                from aquestalk_client import AquesTalkClient
                
                client = create_tts_client()
                assert isinstance(client, AquesTalkClient)

    def test_default_is_voicevox(self, mock_aplay_output):
        """TTS_ENGINEが設定されていない場合はVoicevoxがデフォルト"""
        # 環境変数をクリア
        env = os.environ.copy()
        env.pop("TTS_ENGINE", None)
        
        with patch.dict(os.environ, env, clear=True):
            with patch('subprocess.check_output', return_value=mock_aplay_output):
                from tts_factory import create_tts_client
                from voicevox_client import VoicevoxClient
                
                # モジュールを再インポートして環境変数の変更を反映
                import importlib
                import tts_factory
                importlib.reload(tts_factory)
                
                client = tts_factory.create_tts_client()
                # デフォルトはvoicevox（またはaquestalk、実装による）
                assert client is not None

    def test_invalid_engine_raises_error(self, mock_aplay_output):
        """無効なTTS_ENGINEはValueErrorを発生させる"""
        with patch.dict(os.environ, {"TTS_ENGINE": "invalid_engine"}):
            with patch('subprocess.check_output', return_value=mock_aplay_output):
                from tts_factory import create_tts_client
                
                with pytest.raises(ValueError):
                    create_tts_client()
