
from gtts import gTTS
import os

# テキストを定義
text = "こんにちは、これはテストです。"

# 出力ファイルパスを定義
output_path = "test_audio.mp3"

print(f"'{text}' というテキストから音声ファイルを生成します...")

# gTTSを使って音声ファイルを生成
try:
    tts = gTTS(text=text, lang='ja')
    tts.save(output_path)
    print(f"音声ファイル '{output_path}' を作成しました。")

except Exception as e:
    print(f"エラー: 音声ファイルの作成に失敗しました。")
    print(f"エラー詳細: {e}")
