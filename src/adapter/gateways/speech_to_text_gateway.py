
from src.domain.use_cases.record_and_transcribe import SpeechToTextGateway
from src.domain.entities.audio import AudioData
from src.domain.entities.transcription import Transcription
from google.cloud import speech
import os
from scipy.io.wavfile import write
import io

class SpeechToTextGatewayImpl(SpeechToTextGateway):
    """SpeechToTextGatewayの具体的な実装"""
    def __init__(self):
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError("環境変数 GOOGLE_APPLICATION_CREDENTIALS が設定されていません。")
        self.client = speech.SpeechClient()

    def transcribe(self, audio: AudioData) -> Transcription:
        # Numpy配列をバイトデータに変換
        bytes_wav = io.BytesIO()
        write(bytes_wav, audio.samplerate, audio.data)
        content = bytes_wav.getvalue()

        recognition_audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=audio.samplerate,
            language_code="ja-JP",
        )

        print("Gateway: Speech-to-Text APIにリクエストを送信します...")
        response = self.client.recognize(config=config, audio=recognition_audio)

        if response.results:
            result = response.results[0].alternatives[0]
            return Transcription(text=result.transcript, confidence=result.confidence)
        else:
            return Transcription(text="", confidence=0.0)
