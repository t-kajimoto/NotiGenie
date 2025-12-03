import requests
import json
import sounddevice as sd
import numpy as np

class VoicevoxClient:
    def __init__(self, host="localhost", port=50021, speaker_id=1):
        self.base_url = f"http://{host}:{port}"
        self.speaker_id = speaker_id

    def generate_and_play(self, text):
        try:
            # 1. Audio Query
            query_payload = {"text": text, "speaker": self.speaker_id}
            response = requests.post(f"{self.base_url}/audio_query", params=query_payload)
            response.raise_for_status()
            query_data = response.json()

            # 2. Synthesis
            synthesis_payload = {"speaker": self.speaker_id}
            response = requests.post(
                f"{self.base_url}/synthesis",
                params=synthesis_payload,
                json=query_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            audio_content = response.content

            # 3. Play
            # Converting bytes to numpy array for sounddevice
            audio_array = np.frombuffer(audio_content, dtype=np.int16)
            # Assuming 24000Hz as default for Voicevox
            sd.play(audio_array, samplerate=24000)
            sd.wait()

        except Exception as e:
            print(f"VOICEVOX Error: {e}")
