import pvporcupine
from pvrecorder import PvRecorder
import os
import numpy as np

class WakeWordEngine:
    """
    Class for wake word detection using Picovoice Porcupine.
    """
    def __init__(self, access_key, keywords=None, keyword_paths=None, model_path=None, sensitivity=0.5):
        self.access_key = access_key
        self.keywords = keywords
        self.keyword_paths = keyword_paths
        self.model_path = model_path
        self.sensitivity = sensitivity
        self.porcupine = None
        self.recorder = None

        try:
            # Initialize Porcupine
            if keyword_paths:
                self.porcupine = pvporcupine.create(
                    access_key=access_key,
                    keyword_paths=keyword_paths,
                    model_path=model_path,
                    sensitivities=[sensitivity] * len(keyword_paths)
                )
            elif keywords:
                 self.porcupine = pvporcupine.create(
                    access_key=access_key,
                    keywords=keywords,
                    model_path=model_path,
                    sensitivities=[sensitivity] * len(keywords)
                )
            else:
                self.porcupine = pvporcupine.create(access_key=access_key)

            # Recorder is initialized on demand
            self.recorder = None
            
            keywords_str = f"Paths: {keyword_paths}" if keyword_paths else f"Keywords: {keywords if keywords else 'Default'}"
            print(f"Porcupine initialized. {keywords_str}")

        except Exception as e:
            print(f"WakeWordEngine initialization error: {e}")
            raise e

    def _init_recorder(self):
        """Initializes the PvRecorder if not already exists."""
        if self.recorder is not None:
            return

        devices = PvRecorder.get_available_devices()
        print(f"Available Audio Devices: {devices}")
        
        device_index = int(os.getenv("PV_DEVICE_INDEX", -1))
        
        # Auto-detect USB Audio if default -1 is used
        if device_index == -1:
            for i, device in enumerate(devices):
                if "USB Audio" in device:
                    print(f"Auto-selected USB Audio device at index {i}: {device}")
                    device_index = i
                    break

        self.recorder = PvRecorder(device_index=device_index, frame_length=self.porcupine.frame_length)
        print(f"Initialized PvRecorder with device index: {device_index}")

    def release_recorder(self):
        """Releases the recorder resource explicitly."""
        if self.recorder is not None:
            self.recorder.delete()
            self.recorder = None
            print("PvRecorder released.")

    def wait_for_wake_word(self):
        """
        Blocks until the wake word is detected.

        Returns:
            int: The index of the detected keyword.
        """
        try:
            self._init_recorder()
            self.recorder.start()
            print("Listening for wake word...")

            print(f"Debug: Loop started. Recorder active: {self.recorder.is_recording}")
            frame_count = 0
            
            # Load gain from environment
            try:
                gain = float(os.getenv("MIC_GAIN", 1.0))
            except ValueError:
                gain = 1.0
            print(f"Audio Gain: {gain}")

            while True:
                pcm = self.recorder.read()
                
                # Apply Software Gain
                if gain != 1.0:
                    try:
                        audio_np = np.array(pcm, dtype=np.int16)
                        audio_np = audio_np * gain
                        audio_np = np.clip(audio_np, -32768, 32767).astype(np.int16)
                        # pcm must be list for Porcupine
                        pcm = audio_np.tolist()
                    except Exception as e:
                        print(f"Gain Error: {e}")

                # Debug logging
                # User requested to remove DEBUG_AMP logs
                # if frame_count % 50 == 0:
                #    max_val = max(pcm) if pcm else 0
                #    print(f"DEBUG_AMP (Boosted): {max_val}", flush=True)
                frame_count += 1

                result = self.porcupine.process(pcm)

                if result >= 0:
                    print(f"\nWake word detected! (Index: {result})")
                     # Reset frame_count to avoid overflow (though python handles large ints)
                    frame_count = 0
                    return result

        except KeyboardInterrupt:
            print("Stopping...")
            raise
        except Exception as e:
            print(f"Error in wait_for_wake_word: {e}")
            raise e
        finally:
            if self.recorder is not None and self.recorder.is_recording:
                self.recorder.stop()

    def cleanup(self):
        """
        Releases resources.
        """
        if hasattr(self, 'porcupine') and self.porcupine is not None:
            self.porcupine.delete()

        if hasattr(self, 'recorder') and self.recorder is not None:
            self.recorder.delete()

        print("WakeWordEngine cleanup complete.")
