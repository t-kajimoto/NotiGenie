import os
import time
import requests
import datetime
from wake_word_engine import WakeWordEngine
from stt_client import STTClient, MicrophoneStream
from voicevox_client import VoicevoxClient
from dotenv import load_dotenv

load_dotenv()

# Configuration
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
CLOUD_FUNCTIONS_URL = os.getenv("CLOUD_FUNCTIONS_URL")

def main():
    """
    メインアプリケーションループ。
    ウェイクワードを検知 -> 音声録音 -> STT -> Cloud Functions -> TTS
    """
    if not PICOVOICE_ACCESS_KEY:
        print("Error: PICOVOICE_ACCESS_KEY is not set.")
        return

    if not CLOUD_FUNCTIONS_URL:
        print("Warning: CLOUD_FUNCTIONS_URL is not set. Requests will fail.")

    # Initialize components
    wake_word_engine = WakeWordEngine(access_key=PICOVOICE_ACCESS_KEY)
    stt_client = STTClient()
    voicevox_client = VoicevoxClient(host="voicevox_core") # Docker compose service name

    print("NotiGenie Client Started. Waiting for wake word...")

    def on_wake_word_detected():
        print("Wake word detected! Listening for command...")

        # Play a sound or visual cue here if needed

        # Start recording and STT
        try:
            with MicrophoneStream(rate=16000, chunk=1600) as stream:
                audio_generator = stream.generator()
                text = stt_client.recognize_speech(audio_generator)

                if text:
                    print(f"Recognized: {text}")

                    # Send to Cloud Functions
                    payload = {
                        "text": text,
                        "date": datetime.datetime.now().strftime("%Y-%m-%d")
                    }
                    try:
                        response = requests.post(CLOUD_FUNCTIONS_URL, json=payload)
                        response.raise_for_status()
                        response_data = response.json()

                        answer = response_data.get("response", "すみません、よくわかりませんでした。")
                        print(f"Response: {answer}")

                        # TTS
                        voicevox_client.generate_and_play(answer)

                    except Exception as e:
                        print(f"Backend Error: {e}")
                        voicevox_client.generate_and_play("すみません、エラーが発生しました。")
                else:
                    print("No speech detected.")
        except Exception as e:
            print(f"Error during processing: {e}")

        print("Waiting for wake word...")

    try:
        wake_word_engine.start_listening(on_wake_word_detected)

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        wake_word_engine.cleanup()

if __name__ == "__main__":
    main()
