
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import time
import os

from hardware.button_handler import IS_RASPBERRY_PI

# --------------------------------------------------------------------------
# 1. マイク存在確認とダミーモード設定
# --------------------------------------------------------------------------
# sounddeviceライブラリは、利用可能なオーディオデバイスがない場合、
# sd.query_devices()などでエラーを発生させる可能性があります。
# ここでは、利用可能な入力デバイス（マイク）があるかどうかを確認し、
# なければダミーモードで動作するようにします。
IS_MICROPHONE_AVAILABLE = False
try:
    devices = sd.query_devices()
    for device in devices:
        if device['max_input_channels'] > 0:
            IS_MICROPHONE_AVAILABLE = True
            break
    if not IS_MICROPHONE_AVAILABLE:
        print("利用可能なマイクが見つかりません。ダミーモードで実行します。")
except Exception as e:
    print(f"オーディオデバイスのクエリ中にエラーが発生しました: {e}")
    print("ダミーモードで実行します。")

# Raspberry Pi以外の環境では、マイクの有無に関わらずダミーモードを強制
if not IS_RASPBERRY_PI:
    IS_MICROPHONE_AVAILABLE = False
    print("Raspberry Pi以外の環境のため、マイクの有無に関わらずダミーモードを強制します。")

# --------------------------------------------------------------------------
# 2. AudioRecorderクラスの定義
# --------------------------------------------------------------------------
class AudioRecorder:
    """
    マイクから音声を録音し、WAVファイルとして保存する責務を持つクラス。
    """
    def __init__(self, samplerate=44100, channels=1):
        """
        コンストラクタ

        Args:
            samplerate (int): サンプリングレート (Hz)。CD音質に近い44100が一般的。
            channels (int): チャンネル数 (1: モノラル, 2: ステレオ)
        """
        self.samplerate = samplerate
        self.channels = channels
        self.recording = False

    def record(self, duration, output_filename="recording.wav", dummy_input_file=None):
        """
        指定された時間だけ録音し、ファイルに保存する。

        Args:
            duration (int): 録音時間（秒）
            output_filename (str): 保存するファイル名
        """
        if not IS_MICROPHONE_AVAILABLE:
            self._create_dummy_file(duration, output_filename, dummy_input_file)
            return

        try:
            print(f"{duration}秒間の録音を開始します... ファイル名: {output_filename}")
            self.recording = True
            # sounddeviceのrec関数で録音を開始。dtype='int16'はWAVファイルで一般的なデータ型。
            recording_data = sd.rec(int(duration * self.samplerate), samplerate=self.samplerate, channels=self.channels, dtype='int16')
            sd.wait()  # 録音が完了するまで待機
            self.recording = False
            print("録音が完了しました。")

            # 録音データをファイルに書き込み
            write(output_filename, self.samplerate, recording_data)
            print(f"音声ファイルを'{output_filename}'として保存しました。")

        except Exception as e:
            print(f"録音中にエラーが発生しました: {e}")
            self.recording = False

    def _create_dummy_file(self, duration, output_filename, input_filename=None):
        """
        ダミーモード時に、指定されたファイルをコピーする。
        """
        if input_filename and os.path.exists(input_filename):
            print(f"[DUMMY] '{input_filename}'を'{output_filename}'としてコピーします。")
            import shutil
            shutil.copy(input_filename, output_filename)
            print(f"[DUMMY] ダミーファイル'{output_filename}'を作成しました。")
        else:
            raise FileNotFoundError(f"ダミーモード用の入力ファイル'{input_filename}'が見つかりません。")

# --------------------------------------------------------------------------
# 3. 動作確認用のサンプルコード
# --------------------------------------------------------------------------
if __name__ == '__main__':
    print("音声録音スクリプトを開始します。")

    # AudioRecorderのインスタンスを作成
    recorder = AudioRecorder()

    # ダミーモードで、既存の音声ファイル(test_audio.mp3)をコピーするテスト
    if not IS_MICROPHONE_AVAILABLE:
        print("\n--- ダミーモード（ファイルコピー）のテスト ---")
        # 事前にgTTSなどで作成したテスト用の音声ファイル
        input_file = "sample_data/test_audio.wav" 
        if not os.path.exists(input_file):
            print(f"テスト用の入力ファイル'{input_file}'が見つかりません。")
        else:
            recorder.record(duration=0, output_filename="test_recording_from_file.wav", dummy_input_file=input_file)

    # 実際の録音（マイクがある場合）またはエラー（マイクがない場合）
    print("\n--- 通常の録音テスト（ダミーモードではエラー）---")
    try:
        recorder.record(duration=3, output_filename="test_recording_silent.wav")
    except FileNotFoundError as e:
        print(f"エラー: {e}")


    print("\nスクリプトを終了します。")

