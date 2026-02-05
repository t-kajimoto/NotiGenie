import time
from pvrecorder import PvRecorder
import os

def test_input():
    print("Listing devices...")
    devices = PvRecorder.get_available_devices()
    usb_index = -1
    for i, device in enumerate(devices):
        print(f"[{i}] {device}")
        if "USB Audio" in device:
            usb_index = i

    target_index = int(os.getenv("PV_DEVICE_INDEX", -1))
    if target_index == -1:
        target_index = usb_index
    
    print(f"Target Index: {target_index}")
    if target_index == -1:
        print("No USB device found!")
        # return

    print(f"Initializing PvRecorder (index={target_index}, frame_length=512)...")
    try:
        recorder = PvRecorder(device_index=target_index, frame_length=512)
        print("Recorder initialized.")
        
        print("Starting recorder...")
        recorder.start()
        print("Recorder started. Reading 50 frames...")
        
        start_t = time.time()
        for x in range(50):
            pcm = recorder.read()
            # simple RMS or just check if we got data
            max_val = max(pcm) if pcm else 0
            if x % 10 == 0:
                print(f"Frame {x}: read {len(pcm)} samples. Max: {max_val}")
        
        duration = time.time() - start_t
        print(f"Finished in {duration:.2f}s")
        
        recorder.stop()
        recorder.delete()
        print("Success.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_input()
