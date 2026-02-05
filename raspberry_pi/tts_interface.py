"""
TTS (Text-to-Speech) Interface

共通インターフェースを定義し、異なるTTSエンジン間で切り替え可能にします。
"""
from abc import ABC, abstractmethod


class TTSClient(ABC):
    """TTSクライアントの抽象基底クラス"""

    @abstractmethod
    def speak(self, text: str) -> None:
        """
        テキストを音声に変換して再生する。

        Args:
            text: 読み上げるテキスト
        """
        pass
