
from abc import ABC, abstractmethod
from src.domain.entities.audio import AudioData
from src.domain.entities.transcription import Transcription

class AudioRecorderGateway(ABC):
    """録音デバイスの抽象インターフェース（ポート）"""
    @abstractmethod
    def record(self, duration: int) -> AudioData:
        pass

class SpeechToTextGateway(ABC):
    """文字起こしサービスの抽象インターフェース（ポート）"""
    @abstractmethod
    def transcribe(self, audio: AudioData) -> Transcription:
        pass

class RecordAndTranscribeUseCase:
    """録音と文字起こしの一連の流れを実行するユースケース"""
    def __init__(self, recorder: AudioRecorderGateway, transcriber: SpeechToTextGateway):
        self.recorder = recorder
        self.transcriber = transcriber

    def execute(self, duration: int = 5) -> Transcription:
        print("ユースケース実行: 録音を開始します...")
        audio = self.recorder.record(duration)
        print("ユースケース: 録音完了、文字起こしを開始します...")
        transcription = self.transcriber.transcribe(audio)
        print(f"ユースケース: 文字起こし完了 -> {transcription.text}")
        return transcription
