from abc import ABC, abstractmethod
class BaseScraper(ABC):
    name: str = "base"
    @abstractmethod
    def fetch_listings(self) -> list[dict]:
        raise NotImplementedError
