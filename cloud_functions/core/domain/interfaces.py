from abc import ABC, abstractmethod
from typing import Dict, Any

class ILanguageModel(ABC):
    @abstractmethod
    async def generate_notion_command(self, user_utterance: str, current_date: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def generate_final_response(self, user_utterance: str, tool_result: str) -> str:
        pass

class INotionRepository(ABC):
    pass
