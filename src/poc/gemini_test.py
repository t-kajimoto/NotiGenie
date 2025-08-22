
import os
import google.generativeai as genai
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# APIキーを設定
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("エラー: .envファイルにGEMINI_API_KEYが設定されていません。")
else:
    genai.configure(api_key=api_key)

    try:
        print("Gemini APIへの接続テストを開始します...")
        # 使用するモデルを選択
        model = genai.GenerativeModel('gemini-2.0-flash')

        # 簡単なプロンプトを送信
        prompt = "日本の首都はどこですか？"
        print(f"プロンプト: {prompt}")

        response = model.generate_content(prompt)

        # 応答を表示
        print("\n--- レスポンス ---")
        print(response.text)
        print("\n[SUCCESS] Gemini APIとの通信に成功しました！")

    except Exception as e:
        print(f"\n[FAILED] Gemini APIとの通信中にエラーが発生しました。")
        print(f"エラー詳細: {e}")

