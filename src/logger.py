"""logger.py — Système de logs étape par étape"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class StepLogger:
    enabled: bool = True
    logs: List[str] = field(default_factory=list)

    def _add(self, level: str, message: str) -> None:
        line = f"[{level}] {message}"
        self.logs.append(line)
        if self.enabled:
            print(line)

    def info(self, message: str) -> None:
        self._add("INFO", message)

    def ok(self, message: str) -> None:
        self._add("OK", message)

    def warn(self, message: str) -> None:
        self._add("WARN", message)

    def error(self, message: str) -> None:
        self._add("ERROR", message)
