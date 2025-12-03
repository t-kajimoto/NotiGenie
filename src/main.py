import asyncio
import os
import yaml
from dotenv import load_dotenv

# .envファイルをロード
load_dotenv()

from adapter.controllers.main_controller import MainController
from adapter.gateways.audio_recorder_gateway import AudioRecorderGatewayImpl
from adapter.gateways.speech_to_text_gateway import SpeechToTextGatewayImpl
from adapter.gateways.gemini_gateway import GeminiGateway
from adapter.gateways.notion_client_gateway import NotionClientGateway
from domain.use_cases.record_and_transcribe import RecordAndTranscribeUseCase
from domain.use_cases.interpret_and_execute import InterpretAndExecuteUseCase
from hardware.wakeword_handler import WakeWordHandler

async def main():
    """
    アプリケーションのメインエントリポイント。
    依存関係の注入（DI）とアプリケーションの起動を行う。
    """
    print("NotiGenieアプリケーションを起動します...")

    # ------------------------------------------
    # 1. 設定ファイルの読み込み
    # ------------------------------------------
    print("設定ファイルを読み込んでいます...")
    try:
        # config.yamlからデータベースマッピングを読み込む
        with open("config.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        notion_database_mapping = config.get("notion_databases", {})

        # プロンプトファイルを読み込む
        with open("prompts/notion_command_generator.md", 'r', encoding='utf-8') as f:
            command_prompt_template = f.read()
        with open("prompts/final_response_generator.md", 'r', encoding='utf-8') as f:
            response_prompt_template = f.read()

        # APIキーを読み込む
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError(".envファイルにGEMINI_API_KEYが設定されていません。")
        
        notion_api_key = os.getenv("NOTION_API_KEY")
        if not notion_api_key:
            raise ValueError(".envファイルにNOTION_API_KEYが設定されていません。")

        picovoice_access_key = os.getenv("PICOVOICE_ACCESS_KEY")
        if not picovoice_access_key:
            raise ValueError(".envファイルにPICOVOICE_ACCESS_KEYが設定されていません。")

        print("設定ファイルの読み込みが完了しました。")

    except FileNotFoundError as e:
        print(f"設定ファイルが見つかりません: {e}")
        return
    except Exception as e:
        print(f"設定の読み込み中にエラーが発生しました: {e}")
        return

    # ------------------------------------------
    # 2. 依存関係の注入 (DI)
    # ------------------------------------------
    print("依存関係を構築しています...")
    try:
        # Gateways
        audio_recorder_gateway = AudioRecorderGatewayImpl()
        speech_to_text_gateway = SpeechToTextGatewayImpl()
        gemini_gateway = GeminiGateway(
            api_key=gemini_api_key, 
            command_prompt_template=command_prompt_template, 
            response_prompt_template=response_prompt_template, 
            notion_database_mapping=notion_database_mapping
        )
        notion_client_gateway = NotionClientGateway(notion_api_key=notion_api_key, notion_database_mapping=notion_database_mapping)

        # Use Cases
        record_and_transcribe_use_case = RecordAndTranscribeUseCase(
            recorder=audio_recorder_gateway, 
            transcriber=speech_to_text_gateway
        )
        interpret_and_execute_use_case = InterpretAndExecuteUseCase(
            intent_and_response_gateway=gemini_gateway,
            notion_client_gateway=notion_client_gateway
        )

        # Controller
        main_controller = MainController(
            record_and_transcribe_use_case=record_and_transcribe_use_case,
            interpret_and_execute_use_case=interpret_and_execute_use_case
        )

        # Hardware
        # WakeWordHandlerの初期化（デフォルトのキーワード 'porcupine' を使用）
        wakeword_handler = WakeWordHandler(access_key=picovoice_access_key)

        # ウェイクワード検知のコールバックとしてコントローラのアクションを登録
        wakeword_handler.start_listening(main_controller.on_button_pressed)
        print("依存関係の構築が完了しました。")

    except Exception as e:
        print(f"依存関係の構築中にエラーが発生しました: {e}")
        return

    # ------------------------------------------
    # 3. アプリケーションのメインループ
    # ------------------------------------------
    print("\nアプリケーションが起動しました。ウェイクワード（'Porcupine'）を待っています...")
    try:
        # アプリケーションが終了しないように待機
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nアプリケーションを終了します。")
    finally:
        if 'wakeword_handler' in locals():
            wakeword_handler.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

