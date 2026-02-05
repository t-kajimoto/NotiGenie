"""
TTS Factory

環境変数 TTS_ENGINE に基づき、適切なTTSクライアントを生成するファクトリ。
"""
import os

from tts_interface import TTSClient


def create_tts_client() -> TTSClient:
    """
    環境変数に基づいてTTSクライアントを生成する。

    環境変数:
        TTS_ENGINE: "aquestalk" (default) または "voicevox"

    Returns:
        TTSClient: 選択されたTTSエンジンのクライアントインスタンス
    """
    engine = os.getenv("TTS_ENGINE", "aquestalk").lower()

    if engine == "voicevox":
        from voicevox_client import VoicevoxClient
        print("TTS Engine: VoiceVOX")
        return VoicevoxClient()
    else:
        from aquestalk_client import AquesTalkClient
        print("TTS Engine: AquesTalk Pi")
        return AquesTalkClient()
