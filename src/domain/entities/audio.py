
from dataclasses import dataclass
import numpy as np

@dataclass
class AudioData:
    """音声データを表現するエンティティ"""
    samplerate: int
    data: np.ndarray
