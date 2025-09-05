
from gtts import gTTS
import os
import sys

# 引数からテキストを取得
if len(sys.argv) > 1:
    text = sys.argv[1]
else:
    text = "こんにちは、これはテストです。"

# 出力ファイルパスを定義 (MP3形式)
output_path = os.path.join(os.path.dirname(__file__), '..', 'sample_data', 'test_audio.mp3')

print(f"'{text}' というテキストからMP3ファイルを生成します...")

# gTTSを使って音声ファイルを生成
try:
    tts = gTTS(text=text, lang='ja')
    tts.save(output_path)
    print(f"音声ファイル '{output_path}' を作成しました。")

except Exception as e:
    print(f"エラー: 音声ファイルの作成に失敗しました。")
    print(f"エラー詳細: {e}")
