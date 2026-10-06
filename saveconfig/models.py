from dataclasses import dataclass, asdict
from threading import Event

class Cancelled(Exception):
    pass

class Operation:
    def __init__(self, callback=lambda message: None):
        self.cancel = Event()
        self.callback = callback

    def check(self):
        if self.cancel.is_set():
            raise Cancelled('cancelled')

@dataclass
class Entry:
    program: str
    path: str
    kind: str = 'unknown'
    sensitive: bool = False
    selected: bool = False
    known: bool = False
    exists: bool = False
    size: int = 0
    files: int = 0
    modified: float = 0
    status: str = 'missing'
    config_id: int | None = None
    category: str = 'unknown'

    def data(self):
        return asdict(self)
