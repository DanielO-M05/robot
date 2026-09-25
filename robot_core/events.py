from dataclasses import dataclass
from typing import Optional


@dataclass
class Event:
    kind: str
    detail: Optional[str] = None  # e.g. a vision description, free-text context
