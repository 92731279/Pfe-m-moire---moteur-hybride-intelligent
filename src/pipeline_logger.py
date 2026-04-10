"""pipeline_logger.py — Logger structuré pour le pipeline complet"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any


@dataclass
class LogEvent:
    step: str
    level: str
    message: str
    timestamp: str
    data: Dict[str, Any] = field(default_factory=dict)


class PipelineLogger:
    def __init__(self):
        self.events: List[LogEvent] = []

    def log(self, step: str, message: str, level: str = "INFO", **data):
        self.events.append(
            LogEvent(
                step=step,
                level=level,
                message=message,
                timestamp=datetime.now().strftime("%H:%M:%S"),
                data=data,
            )
        )

    def as_dicts(self) -> List[Dict[str, Any]]:
        return [
            {
                "step": e.step,
                "level": e.level,
                "message": e.message,
                "timestamp": e.timestamp,
                "data": e.data,
            }
            for e in self.events
        ]

    def format_console(self) -> str:
        lines = []
        for e in self.events:
            base = f"[{e.timestamp}] [{e.level}] [{e.step}] {e.message}"
            if e.data:
                details = " | ".join(f"{k}={v}" for k, v in e.data.items())
                base += f" | {details}"
            lines.append(base)
        return "\n".join(lines)
