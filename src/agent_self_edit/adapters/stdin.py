"""Stdin-aware trace adapter for JSON-lines input."""

from __future__ import annotations

import json
import sys
from typing import TextIO

from ..trace import TraceStore
from .base import TraceAdapter


class StdinAdapter(TraceAdapter):
    """Reads JSON-lines from stdin, one trace object per line, and ingests each."""

    def __init__(
        self, store: TraceStore, stream: TextIO | None = None, batch_size: int = 1000
    ) -> None:
        super().__init__(store)
        self._stream = stream if stream is not None else sys.stdin
        self._batch_size = batch_size
        self._ingested = 0

    def run(self) -> None:
        for line in self._stream:
            if self._stopped():
                break
            line = line.strip()
            if not line:
                continue
            try:
                trace = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"agent-self-edit: skipping malformed line: {e}", file=sys.stderr)
                continue
            try:
                self._store.ingest(trace)
                self._ingested += 1
            except ValueError as e:
                print(
                    f"agent-self-edit: skipping invalid trace: {e}",
                    file=sys.stderr,
                )
            if self._ingested % self._batch_size == 0:
                print(
                    f"agent-self-edit: ingested {self._ingested} traces",
                    file=sys.stderr,
                )
