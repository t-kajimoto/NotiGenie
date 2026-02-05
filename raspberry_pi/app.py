import os
import time
import requests
import datetime
import glob
from wake_word_engine import WakeWordEngine
from stt_client import STTClient, MicrophoneStream
from tts_factory import create_tts_client
from dotenv import load_dotenv

load_dotenv()

# Configuration
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
CLOUD_FUNCTIONS_URL = os.getenv("CLOUD_FUNCTIONS_URL")
NOTIGENIE_API_KEY = os.getenv("NOTIGENIE_API_KEY")

def main():
    """
    Main application loop.
    Wake Word -> Record -> STT -> Cloud Functions -> TTS
    """
    if not PICOVOICE_ACCESS_KEY:
        print("Error: PICOVOICE_ACCESS_KEY is not set.")
        return

    if not CLOUD_FUNCTIONS_URL:
        print("Warning: CLOUD_FUNCTIONS_URL is not set. Requests will fail.")

    # Wake Word Configuration
    # Try to find a 'genie' keyword file (e.g., genie_raspberry-pi.ppn)
    keyword_paths = glob.glob("*.ppn")
    genie_path = None
    for path in keyword_paths:
        if "genie" in path.lower():
            genie_path = path
            break

    wake_word_kwargs = {}
    if genie_path:
        print(f"Found custom wake word model: {genie_path}")
        wake_word_kwargs["keyword_paths"] = [genie_path]
    else:
        print("No custom 'Genie' wake word model found (*.ppn).")
        print("Falling back to default 'Jarvis' (acting as Genie).")
        # 'jarvis' is a standard keyword usually available.
        # If not, it will fail, so we might want to check available ones.
        # But Porcupine standard keywords depend on the library version/platform.
        # Safest is just not passing keywords (defaults to 'porcupine').
        # But user asked for Genie. Let's try 'jarvis' or 'porcupine'.
        wake_word_kwargs["keywords"] = ["porcupine"]

    # Initialize components
    try:
        wake_word_engine = WakeWordEngine(access_key=PICOVOICE_ACCESS_KEY, **wake_word_kwargs)
    except Exception as e:
        print(f"Failed to initialize WakeWordEngine: {e}")
        return

    stt_client = STTClient(rate=48000)
    tts_client = create_tts_client()  # 環境変数 TTS_ENGINE で切り替え

    print("NotiGenie Client Started.")

    try:
        while True:
            # 1. Wait for Wake Word
            wake_word_engine.wait_for_wake_word()

            # Release recorder to free ALSA device for PyAudio (STT)
            wake_word_engine.release_recorder()

            # 2. Wake Word Detected - Play a sound (optional, skipping for simplicity) or just print
            print("Wake word detected! Listening for command...")

            # 3. Record & STT
            text = ""
            try:
                # We use a new MicrophoneStream context for each interaction to ensure clean audio capture
                # and avoid conflicts with Porcupine which was just stopped.
                # Device natively supports 48000Hz (AT-CSP1)
                print("Starting STT (listening)...")
                stt_t0 = time.perf_counter()
                with MicrophoneStream(rate=48000, chunk=4800) as stream:
                    audio_generator = stream.generator()
                    # recognize_speech returns when it detects a final result or timeout (handled by STTClient logic usually)
                    # Note: STTClient.recognize_speech relies on Google Cloud stream which waits for silence.
                    text = stt_client.recognize_speech(audio_generator)
                stt_duration = time.perf_counter() - stt_t0
                print(f"STT complete. Duration: {stt_duration:.2f}s")
            except Exception as e:
                print(f"STT Error: {e}")
                tts_client.speak("聞き取れませんでした。")
                continue

            if text:
                print(f"Recognized: {text}")

                # 4. Send to Cloud Functions
                print("Sending to Backend (Cloud Functions)...")
                backend_t0 = time.perf_counter()
                payload = {
                    "text": text,
                    "date": datetime.datetime.now().strftime("%Y-%m-%d")
                }
                headers = {}
                if NOTIGENIE_API_KEY:
                    headers["X-API-Key"] = NOTIGENIE_API_KEY
                try:
                    response = requests.post(CLOUD_FUNCTIONS_URL, json=payload, headers=headers)
                    response.raise_for_status()
                    backend_duration = time.perf_counter() - backend_t0
                    print(f"Backend response received in {backend_duration:.2f}s")
                    
                    response_data = response.json()
                    answer = response_data.get("response", "すみません、よくわかりませんでした。")
                    print(f"Response: {answer}")

                    # 5. TTS
                    tts_client.speak(answer)

                except Exception as e:
                    print(f"Backend Error: {e}")
                    tts_client.speak("すみません、エラーが発生しました。")
            else:
                print("No speech detected.")

            # Loop continues to wait for wake word again

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        wake_word_engine.cleanup()

if __name__ == "__main__":
    main()
