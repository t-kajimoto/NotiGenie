import time
from dotenv import load_dotenv

# .envファイルをロード
load_dotenv()

from adapter.controllers.main_controller import MainController
from adapter.gateways.audio_recorder_gateway import AudioRecorderGatewayImpl
from adapter.gateways.speech_to_text_gateway import SpeechToTextGatewayImpl
from domain.use_cases.record_and_transcribe import RecordAndTranscribeUseCase
from hardware.button_handler import ButtonHandler

def main():
    """
    アプリケーションのメインエントリポイント。
    依存関係の注入（DI）とアプリケーションの起動を行う。
    """
    print("NotiGenieアプリケーションを起動します...")

    # ------------------------------------------
    # 1. 依存関係の注入 (DI)
    # ------------------------------------------
    print("依存関係を構築しています...")
    try:
        audio_recorder_gateway = AudioRecorderGatewayImpl()
        speech_to_text_gateway = SpeechToTextGatewayImpl()
        record_and_transcribe_use_case = RecordAndTranscribeUseCase(
            recorder=audio_recorder_gateway, 
            transcriber=speech_to_text_gateway
        )
        main_controller = MainController(use_case=record_and_transcribe_use_case)
        button_handler = ButtonHandler()

        # ボタン押下のコールバックとしてコントローラのアクションを登録
        button_handler.set_button_press_callback(main_controller.on_button_pressed)
        print("依存関係の構築が完了しました。")

    except Exception as e:
        print(f"依存関係の構築中にエラーが発生しました: {e}")
        return

    # ------------------------------------------
    # 2. アプリケーションのメインループ
    # ------------------------------------------
    print("\nアプリケーションが起動しました。ボタンの押下を待っています...")
    print("（PCでのテストの場合、コンソールでEnterキーを押してください）")
    try:
        # ボタンのイベントループはButtonHandler内で実行されるため、
        # main.pyはここで待機するだけで良い。
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nアプリケーションを終了します。")
    finally:
        button_handler.cleanup()

if __name__ == "__main__":
    main()