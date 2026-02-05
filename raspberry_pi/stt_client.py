from google.cloud import speech
import pyaudio
import queue
import os
import numpy as np

class STTClient:
    def __init__(self, language_code="ja-JP", rate=48000):
        self.language_code = language_code
        self.rate = rate
        self.client = speech.SpeechClient()
        self.config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.rate,
            language_code=self.language_code,
        )
        self.streaming_config = speech.StreamingRecognitionConfig(
            config=self.config,
            interim_results=False, # We want final result
        )

    def recognize_speech(self, audio_generator):
        """
        Transcribes speech from audio stream.
        """
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )

        responses = self.client.streaming_recognize(self.streaming_config, requests)

        for response in responses:
            for result in response.results:
                if result.is_final:
                    return result.alternatives[0].transcript
        return ""

class MicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate=48000, chunk=4800):
        self._rate = rate
        self._chunk = chunk
        self._buff = queue.Queue()
        self.closed = True
        self.device_index = None

    def _get_input_device_index(self, audio_interface):
        # 1. Try environment variable
        env_index = int(os.environ.get("PV_DEVICE_INDEX", -1))
        if env_index > -1:
             return env_index
        
        # 2. Search for USB Audio
        count = audio_interface.get_device_count()
        print(f"PyAudio found {count} devices.")
        for i in range(count):
            try:
                info = audio_interface.get_device_info_by_index(i)
                name = info.get("name", "")
                print(f"Device {i}: {name}")
                # Case-insensitive check for 'usb' and 'audio'
                if "usb" in name.lower() and "audio" in name.lower() and info.get("maxInputChannels", 0) > 0:
                    print(f"Auto-selected USB Audio device for STT at index {i}")
                    return i
            except Exception as e:
                print(f"Error checking device {i}: {e}")
        
        print("No USB Audio device found for STT, using default.")
        return None

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        
        if self.device_index is None:
            self.device_index = self._get_input_device_index(self._audio_interface)

        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue


    def generator(self):
        # Load gain from environment
        try:
            gain = float(os.getenv("MIC_GAIN", 1.0))
        except ValueError:
            gain = 1.0

        print(f"STT Gain: {gain}")

        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            raw_bytes = b"".join(data)
            
            # Apply Gain
            if gain != 1.0:
                try:
                    data_np = np.frombuffer(raw_bytes, dtype=np.int16)
                    data_np = data_np * gain
                    data_np = np.clip(data_np, -32768, 32767).astype(np.int16)
                    raw_bytes = data_np.tobytes()
                except Exception as e:
                    print(f"STT Gain Error: {e}")

            yield raw_bytes
