"""Trace adapter interface."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod

from ..trace import TraceStore


class TraceAdapter(ABC):
    """Abstract adapter that ingests traces from a specific source."""

    def __init__(self, store: TraceStore) -> None:
        self._store = store
        self._stop_event = threading.Event()

    @abstractmethod
    def run(self) -> None:
        """Blocking run loop; calls ``store.ingest()`` per trace."""

    def stop(self) -> None:
        """Signal the run loop to exit."""
        self._stop_event.set()

    def _stopped(self) -> bool:
        return self._stop_event.is_set()
