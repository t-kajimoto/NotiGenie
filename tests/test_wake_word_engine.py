import pytest
from unittest.mock import MagicMock, patch
import threading
from raspberry_pi.wake_word_engine import WakeWordEngine

@pytest.fixture
def mock_pvporcupine(mocker):
    mock = mocker.patch("raspberry_pi.wake_word_engine.pvporcupine")
    mock.create.return_value = MagicMock()
    mock.create.return_value.frame_length = 512
    return mock

@pytest.fixture
def mock_pvrecorder(mocker):
    mock = mocker.patch("raspberry_pi.wake_word_engine.PvRecorder")
    mock.return_value = MagicMock()
    return mock

class TestWakeWordEngine:
    def test_init(self, mock_pvporcupine, mock_pvrecorder):
        access_key = "test_key"
        engine = WakeWordEngine(access_key)

        mock_pvporcupine.create.assert_called_once_with(access_key=access_key)
        mock_pvrecorder.assert_called_once()
        assert engine.is_listening is False

    def test_start_listening(self, mock_pvporcupine, mock_pvrecorder):
        engine = WakeWordEngine("test_key")
        callback = MagicMock()

        with patch.object(threading.Thread, 'start') as mock_thread_start:
            engine.start_listening(callback)

            assert engine.is_listening is True
            assert engine._callback == callback
            mock_thread_start.assert_called_once()

    def test_stop_listening(self, mock_pvporcupine, mock_pvrecorder):
        engine = WakeWordEngine("test_key")
        engine.is_listening = True
        mock_thread = MagicMock()
        engine._listen_thread = mock_thread

        engine.stop_listening()

        assert engine.is_listening is False
        # WakeWordEngine内で self._listen_thread は None に設定されるため、
        # ここでは事前に保存しておいた mock_thread に対してアサーションを行う
        mock_thread.join.assert_called_once()

    def test_cleanup(self, mock_pvporcupine, mock_pvrecorder):
        engine = WakeWordEngine("test_key")
        engine.porcupine = MagicMock()
        engine.recorder = MagicMock()

        engine.cleanup()

        engine.porcupine.delete.assert_called_once()
        engine.recorder.delete.assert_called_once()

    def test_listen_loop_detects_keyword(self, mock_pvporcupine, mock_pvrecorder):
        engine = WakeWordEngine("test_key")
        engine.porcupine.process.side_effect = [-1, 0, -1] # 2回目に検知
        engine.recorder.read.return_value = [0] * 512
        engine.is_listening = True

        # 3回ループしたら停止するようにする
        def stop_after_3_calls(*args):
            if engine.porcupine.process.call_count >= 3:
                engine.is_listening = False
            return [0] * 512

        engine.recorder.read.side_effect = stop_after_3_calls

        # コールバックのモック
        callback = MagicMock()
        engine._callback = callback

        engine._listen_loop()

        assert engine.porcupine.process.call_count >= 2
        # コールバックが呼ばれたことを確認 (直接呼び出し)
        callback.assert_called()
