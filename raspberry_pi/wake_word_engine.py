import pvporcupine
from pvrecorder import PvRecorder
import threading
import os

class WakeWordEngine:
    """
    Picovoice Porcupineを使用してウェイクワード検知を行うクラス。
    """
    def __init__(self, access_key, keywords=None, model_path=None, sensitivity=0.5):
        self.access_key = access_key
        self.keywords = keywords
        self.model_path = model_path
        self.sensitivity = sensitivity
        self.is_listening = False
        self._listen_thread = None
        self._callback = None

        # Porcupineの初期化
        try:
            if keywords is None:
                # デフォルトのキーワード（Porcupineなど）を使用
                self.porcupine = pvporcupine.create(access_key=access_key)
            else:
                self.porcupine = pvporcupine.create(
                    access_key=access_key,
                    keywords=keywords,
                    model_path=model_path,
                    sensitivities=[sensitivity] * len(keywords)
                )

            # Recorderの初期化
            self.recorder = PvRecorder(device_index=-1, frame_length=self.porcupine.frame_length)
            print(f"Porcupine initialized. Keywords: {self.keywords if self.keywords else 'Default'}")

        except Exception as e:
            print(f"WakeWordHandler初期化エラー: {e}")
            raise e

    def start_listening(self, callback):
        """
        ウェイクワードの監視を開始する。

        Args:
            callback (function): ウェイクワード検知時に実行されるコールバック関数。
        """
        if self.is_listening:
            print("すでに監視中です。")
            return

        self._callback = callback
        self.is_listening = True

        # 別スレッドで監視ループを開始
        self._listen_thread = threading.Thread(target=self._listen_loop)
        self._listen_thread.daemon = True
        self._listen_thread.start()
        print("ウェイクワードの監視を開始しました。")

    def stop_listening(self):
        """
        ウェイクワードの監視を停止する。
        """
        self.is_listening = False
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=1.0)
        self._listen_thread = None
        print("ウェイクワードの監視を停止しました。")

    def _listen_loop(self):
        """
        内部監視ループ。別スレッドで実行される。
        """
        try:
            self.recorder.start()
            print(f"Listening for wake word...")

            while self.is_listening:
                pcm = self.recorder.read()
                result = self.porcupine.process(pcm)

                if result >= 0:
                    print(f"ウェイクワードを検知しました！ (Index: {result})")
                    self._callback()

        except Exception as e:
            print(f"監視ループエラー: {e}")
        finally:
            if self.recorder.is_recording:
                self.recorder.stop()

    def cleanup(self):
        """
        リソースを解放する。
        """
        self.stop_listening()

        if hasattr(self, 'porcupine') and self.porcupine is not None:
            self.porcupine.delete()

        if hasattr(self, 'recorder') and self.recorder is not None:
            self.recorder.delete()

        print("WakeWordHandler cleanup complete.")
