"""Utilitário interno de carimbo de tempo."""

from datetime import UTC, datetime


def agora_iso() -> str:
    return datetime.now(UTC).isoformat()
