import sounddevice as sd
import numpy as np
import requests
import json
import time
import os

# Configuration
HOST = "voicevox_core" 
BASE_URL = f"http://{HOST}:50021"
SPEAKER_ID = 1

def find_usb_device():
    print("Searching for USB Audio device...")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        name = device.get("name", "")
        max_output = device.get("max_output_channels", 0)
        if "usb" in name.lower() and "audio" in name.lower() and max_output > 0:
            print(f"Found USB Audio at index {i}: {name}")
            return i
    print("USB Audio NOT found.")
    return None

def resample_audio(audio_data, old_rate, new_rate):
    duration = len(audio_data) / old_rate
    new_len = int(len(audio_data) * new_rate / old_rate)
    x_old = np.linspace(0, duration, len(audio_data))
    x_new = np.linspace(0, duration, new_len)
    return np.interp(x_new, x_old, audio_data).astype(np.int16)

def specific_voicevox_test(device_idx):
    print("Testing VoiceVOX generation...")
    text = "聞こえますか？"
    try:
        # Query
        q_res = requests.post(f"{BASE_URL}/audio_query", params={"text": text, "speaker": SPEAKER_ID})
        q_res.raise_for_status()
        query = q_res.json()
        
        # Synthesis
        s_res = requests.post(f"{BASE_URL}/synthesis", params={"speaker": SPEAKER_ID}, json=query)
        s_res.raise_for_status()
        audio_content = s_res.content
        print(f"Received audio content size: {len(audio_content)} bytes")
        
        # Playback
        audio_array = np.frombuffer(audio_content, dtype=np.int16)
        
        # Resample to 48k
        print("Resampling 24k -> 48k...")
        audio_resampled = resample_audio(audio_array, 24000, 48000)
        
        print(f"Playing data with samplerate 48000 on device {device_idx}...")
        sd.play(audio_resampled, samplerate=48000, device=device_idx, blocking=True)
        print("VoiceVOX playback finished.")
        
    except Exception as e:
        print(f"VoiceVOX test error: {e}")

def main():
    device_idx = find_usb_device()
    if device_idx is None:
        print("Cannot proceed without device.")
        return

    print("--- Test 4: VoiceVOX API & Playback (Resampled to 48k) ---")
    if device_idx is not None:
         specific_voicevox_test(device_idx)

if __name__ == "__main__":
    main()
