
from domain.use_cases.record_and_transcribe import AudioRecorderGateway
from domain.entities.audio import AudioData
from hardware.audio_recorder import AudioRecorder, IS_MICROPHONE_AVAILABLE
from scipy.io.wavfile import write, read
import numpy as np
import io

class AudioRecorderGatewayImpl(AudioRecorderGateway):
    """AudioRecorderGatewayの具体的な実装"""
    def __init__(self):
        self.recorder = AudioRecorder()

    def record(self, duration: int) -> AudioData:
        # ファイルに一度保存してから読み込む方式（ハードウェア操作を抽象化）
        temp_filename = "temp_recording.wav"
        self.recorder.record(duration, temp_filename, dummy_input_file="/app/sample_data/test_audio.wav")
        
        # 保存したWAVファイルを読み込む
        samplerate, data = read(temp_filename)
        return AudioData(samplerate=samplerate, data=data)
