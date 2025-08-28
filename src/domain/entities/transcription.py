
from dataclasses import dataclass

@dataclass
class Transcription:
    """文字起こし結果を表現するエンティティ"""
    text: str
    confidence: float = 0.0
