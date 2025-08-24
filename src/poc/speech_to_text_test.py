
import os
from google.cloud import speech
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# 認証情報が設定されているか確認
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    print("エラー: .envファイルにGOOGLE_APPLICATION_CREDENTIALSが設定されていません。")
else:
    try:
        print("Google Cloud Speech-to-Text APIへの接続テストを開始します...")

        # クライアントを初期化
        client = speech.SpeechClient()

        # 音声ファイルを指定
        audio_file = "test_audio.mp3"
        print(f"音声ファイル: {audio_file}")

        # 音声ファイルを読み込む
        with open(audio_file, "rb") as f:
            content = f.read()

        audio = speech.RecognitionAudio(content=content)

        # 音声認識の各種設定
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=24000, # gTTSのデフォルトは24kHz
            language_code="ja-JP",
        )

        # 音声認識を実行
        print("音声認識を実行中...")
        response = client.recognize(config=config, audio=audio)

        # 結果を表示
        print("\n--- 文字起こし結果 ---")
        for result in response.results:
            print(f"Transcript: {result.alternatives[0].transcript}")
        
        if not response.results:
            print("文字起こしの結果がありませんでした。")

        print("\n[SUCCESS] Speech-to-Text APIとの通信に成功しました！")

    except Exception as e:
        print(f"\n[FAILED] Speech-to-Text APIとの通信中にエラーが発生しました。")
        print(f"エラー詳細: {e}")
