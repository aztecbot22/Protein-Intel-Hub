from abc import ABC, abstractmethod
from typing import Any


class Adapter(ABC):
    name: str

    @abstractmethod
    def fetch(self, query: str, context: dict | None = None) -> dict[str, Any]:
        raise NotImplementedError
