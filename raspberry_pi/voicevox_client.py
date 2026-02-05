import requests
import json
import sounddevice as sd
import numpy as np
import os
import subprocess
import re

from tts_interface import TTSClient


class VoicevoxClient(TTSClient):
    """
    VoiceVOX を使用したTTSクライアント。

    高品質な音声合成が可能だが、Raspberry Pi 3では処理に時間がかかる（50秒程度）。
    より高性能なハードウェアか、外部PCでのエンジン実行を推奨。
    """

    def __init__(self, host=None, port=50021, speaker_id=1):
        # Allow environment variable override, default to 'voicevox_core' (Docker service name)
        if host is None:
            host = os.getenv("VOICEVOX_HOST", "voicevox_core")

        self.base_url = f"http://{host}:{port}"
        self.speaker_id = speaker_id
        self.output_device_index = self._get_output_device_card_index()
        print(f"VoicevoxClient initialized for {self.base_url}")

    def _get_output_device_card_index(self):
        """
        Finds the ALSA card index for the USB Audio device using 'aplay -l'.
        Returns the card number (e.g., 2) as a string, or None.
        """
        try:
            result = subprocess.check_output(["aplay", "-l"], text=True)
            match = re.search(r'card\s+(\d+):.*USB.*Audio', result, re.IGNORECASE)
            if match:
                card_index = match.group(1)
                print(f"Found USB Audio Device at ALSA card {card_index}")
                return card_index
        except Exception as e:
            print(f"Error finding audio device using aplay -l: {e}")

        print("USB Audio device not found via aplay -l. Using default.")
        return None

    def speak(self, text: str) -> None:
        """
        テキストを音声に変換して再生する（TTSClient インターフェース実装）。
        """
        self.generate_and_play(text)

    def generate_and_play(self, text):
        """
        VoiceVOX APIを使用して音声を生成し再生する。

        Note: speak() メソッドからも呼び出される。後方互換性のため残存。
        """
        import time
        t0 = time.perf_counter()
        try:
            # 1. Audio Query
            print(f"Starting Audio Query for: {text[:30]}...")
            query_payload = {"text": text, "speaker": self.speaker_id}
            response = requests.post(f"{self.base_url}/audio_query", params=query_payload)
            response.raise_for_status()
            query_data = response.json()
            t1 = time.perf_counter()
            print(f"Audio Query took {t1-t0:.2f}s")

            # 2. Synthesis
            print(f"Starting Synthesis for speaker {self.speaker_id}...")
            synthesis_payload = {"speaker": self.speaker_id}
            response = requests.post(
                f"{self.base_url}/synthesis",
                params=synthesis_payload,
                json=query_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            audio_content = response.content
            t2 = time.perf_counter()
            print(f"Synthesis took {t2-t1:.2f}s")

            # 3. Play using aplay
            print(f"Starting playback using aplay (audio size: {len(audio_content)} bytes)...")
            cmd = ["aplay", "-q"]

            if self.output_device_index:
                device_name = f"plughw:{self.output_device_index},0"
                cmd.extend(["-D", device_name])

            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(input=audio_content)
            t3 = time.perf_counter()

            if process.returncode != 0:
                print(f"aplay failed with return code {process.returncode}")
                print(f"aplay stderr: {stderr.decode()}")
            else:
                print(f"aplay finished successfully in {t3-t2:.2f}s")

            print(f"Total generate_and_play took {t3-t0:.2f}s")

        except Exception as e:
            print(f"VOICEVOX Error: {e}")

