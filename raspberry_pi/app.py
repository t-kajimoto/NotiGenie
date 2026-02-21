import os
import sys
import time
import requests
import datetime
import glob
import threading
import logging
from wake_word_engine import WakeWordEngine
from stt_client import STTClient, MicrophoneStream
from tts_factory import create_tts_client
from dotenv import load_dotenv
from epaper_display import draw_todo_list, get_todo_data, SAMPLE_DATA

# ログ設定
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
CLOUD_FUNCTIONS_URL = os.getenv("CLOUD_FUNCTIONS_URL")
NOTIGENIE_API_KEY = os.getenv("NOTIGENIE_API_KEY")

# E-Paper表示の更新間隔（秒）
EPAPER_UPDATE_INTERVAL = int(os.getenv("EPAPER_UPDATE_INTERVAL", "1800"))  # 30分

# E-Paper ToDo API URL（Cloud Functionsのtodo_listエンドポイント）
EPAPER_TODO_API_URL = os.getenv(
    "EPAPER_TODO_API_URL",
    "https://asia-northeast1-notigenie.cloudfunctions.net/notigenie-backend/api/todo_list"
)

def update_epaper_display():
    """
    E-Paperディスプレイを更新する。
    APIからToDoデータを取得し、画像を生成してE-Paperに表示する。
    一時的なネットワークエラーに備え、最大3回のリトライを行います。
    """
    MAX_RETRIES = 3
    RETRY_DELAY = 60  # 1分

    data = None
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"E-Paper: Fetching todo data (Attempt {attempt + 1}/{MAX_RETRIES})...")
            data = get_todo_data(EPAPER_TODO_API_URL, NOTIGENIE_API_KEY)
            if data:
                break
        except Exception as e:
            logger.warning(f"E-Paper: Fetch attempt {attempt + 1} failed: {e}")
        
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)

    if not data:
        logger.error("E-Paper: Failed to fetch data after all attempts. Aborting update to maintain current display.")
        return

    try:
        logger.info("E-Paper: Generating image...")
        image = draw_todo_list(data)

        logger.info("E-Paper: Initializing display...")
        # waveshare-epaperパッケージはネストされたパス構造のため、
        # sys.pathに追加してからインポートする必要がある
        import glob as _glob
        epd7in5_V2 = None
        for pattern in [
            '/usr/local/lib/python3.*/dist-packages/epaper/e-Paper/RaspberryPi_JetsonNano/python/lib',
            '/home/*/.local/lib/python3.*/site-packages/epaper/e-Paper/RaspberryPi_JetsonNano/python/lib',
        ]:
            matches = _glob.glob(pattern)
            for match in matches:
                if match not in sys.path:
                    sys.path.insert(0, match)
        try:
            from waveshare_epd import epd7in5_V2
        except ImportError as ie:
            logger.error(f"E-Paper: waveshare_epd import failed: {ie}")
            return

        epd = epd7in5_V2.EPD()
        epd.init()
        epd.Clear()

        logger.info("E-Paper: Displaying...")
        epd.display(epd.getbuffer(image))

        logger.info("E-Paper: Sleeping display...")
        epd.sleep()

        logger.info("E-Paper: Update complete!")
    except Exception as e:
        logger.error(f"E-Paper update error: {e}")


def epaper_periodic_update():
    """
    E-Paperディスプレイを定期的に更新するバックグラウンドスレッド。
    初回は即座に実行し、その後は指定間隔で繰り返す。
    """
    while True:
        update_epaper_display()
        logger.info(f"E-Paper: Next update in {EPAPER_UPDATE_INTERVAL}s")
        time.sleep(EPAPER_UPDATE_INTERVAL)


def main():
    """
    Main application loop.
    Wake Word -> Record -> STT -> Cloud Functions -> TTS
    E-Paper display updates run in a background thread.
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

    # E-Paperディスプレイの定期更新をバックグラウンドスレッドで起動
    epaper_thread = threading.Thread(target=epaper_periodic_update, daemon=True)
    epaper_thread.start()
    logger.info("E-Paper background update thread started.")

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
