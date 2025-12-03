import pytest
from unittest.mock import MagicMock, patch, ANY
import asyncio
import threading
from hardware.wakeword_handler import WakeWordHandler

@pytest.fixture
def mock_pvporcupine(mocker):
    mock = mocker.patch("hardware.wakeword_handler.pvporcupine")
    mock.create.return_value = MagicMock()
    mock.create.return_value.frame_length = 512
    return mock

@pytest.fixture
def mock_pvrecorder(mocker):
    mock = mocker.patch("hardware.wakeword_handler.PvRecorder")
    mock.return_value = MagicMock()
    return mock

@pytest.fixture
def mock_asyncio(mocker):
    mock = mocker.patch("hardware.wakeword_handler.asyncio")
    return mock

class TestWakeWordHandler:
    def test_init(self, mock_pvporcupine, mock_pvrecorder):
        access_key = "test_key"
        handler = WakeWordHandler(access_key)

        mock_pvporcupine.create.assert_called_once_with(access_key=access_key)
        mock_pvrecorder.assert_called_once()
        assert handler.is_listening is False

    def test_start_listening(self, mock_pvporcupine, mock_pvrecorder):
        handler = WakeWordHandler("test_key")
        callback = MagicMock()

        with patch.object(threading.Thread, 'start') as mock_thread_start:
            handler.start_listening(callback)

            assert handler.is_listening is True
            assert handler._callback == callback
            mock_thread_start.assert_called_once()

    def test_stop_listening(self, mock_pvporcupine, mock_pvrecorder):
        handler = WakeWordHandler("test_key")
        handler.is_listening = True
        mock_thread = MagicMock()
        handler._listen_thread = mock_thread

        handler.stop_listening()

        assert handler.is_listening is False
        # WakeWordHandler内で self._listen_thread は None に設定されるため、
        # ここでは事前に保存しておいた mock_thread に対してアサーションを行う
        mock_thread.join.assert_called_once()

    def test_cleanup(self, mock_pvporcupine, mock_pvrecorder):
        handler = WakeWordHandler("test_key")
        handler.porcupine = MagicMock()
        handler.recorder = MagicMock()

        handler.cleanup()

        handler.porcupine.delete.assert_called_once()
        handler.recorder.delete.assert_called_once()

    def test_listen_loop_detects_keyword(self, mock_pvporcupine, mock_pvrecorder):
        handler = WakeWordHandler("test_key")
        handler.porcupine.process.side_effect = [-1, 0, -1] # 2回目に検知
        handler.recorder.read.return_value = [0] * 512
        handler.is_listening = True

        # 3回ループしたら停止するようにする
        def stop_after_3_calls(*args):
            if handler.porcupine.process.call_count >= 3:
                handler.is_listening = False
            return [0] * 512

        handler.recorder.read.side_effect = stop_after_3_calls

        # コールバックのモック
        callback = MagicMock()
        handler._callback = callback

        # モックのイベントループを設定
        handler.loop = MagicMock()

        handler._listen_loop()

        assert handler.porcupine.process.call_count >= 2
        # コールバックが呼ばれたことを確認
        # _trigger_callback 内で loop.call_soon_threadsafe または run_coroutine_threadsafe が呼ばれる
        handler.loop.call_soon_threadsafe.assert_called_with(callback)
