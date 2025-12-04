import pvporcupine
from pvrecorder import PvRecorder
import os

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

            # Initialize Recorder
            self.recorder = PvRecorder(device_index=-1, frame_length=self.porcupine.frame_length)

            keywords_str = f"Paths: {keyword_paths}" if keyword_paths else f"Keywords: {keywords if keywords else 'Default'}"
            print(f"Porcupine initialized. {keywords_str}")

        except Exception as e:
            print(f"WakeWordEngine initialization error: {e}")
            raise e

    def wait_for_wake_word(self):
        """
        Blocks until the wake word is detected.

        Returns:
            int: The index of the detected keyword.
        """
        try:
            self.recorder.start()
            print("Listening for wake word...")

            while True:
                pcm = self.recorder.read()
                result = self.porcupine.process(pcm)

                if result >= 0:
                    print(f"Wake word detected! (Index: {result})")
                    return result

        except KeyboardInterrupt:
            print("Stopping...")
            raise
        except Exception as e:
            print(f"Error in wait_for_wake_word: {e}")
            raise e
        finally:
            if self.recorder.is_recording:
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
