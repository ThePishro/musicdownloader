from abc import ABC, abstractmethod
from typing import List
from core.models.track import TrackResult


class BaseSearchProvider(ABC):

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[TrackResult]:
        pass
 