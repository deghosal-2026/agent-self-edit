"""Directory-watching trace adapter."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from ..trace import TraceStore
from .base import TraceAdapter

logger = logging.getLogger("agent_self_edit.adapters.file")


class FileAdapter(TraceAdapter):
    """Watches a directory for new ``.json`` trace files and ingests each.

    Each file must be a JSON object (one trace per file). After successful
    ingestion the file is moved to a ``.done`` sibling so it is not re-read.
    Uses the ``.done`` rename as the sole dedup mechanism — no in-memory
    filename cache, so repeated filenames are safe (ref #142).
    """

    def __init__(
        self, store: TraceStore, watch_dir: str | Path, poll_interval: float = 1.0
    ) -> None:
        super().__init__(store)
        self._watch_dir = Path(watch_dir)
        self._watch_dir.mkdir(parents=True, exist_ok=True)
        self._poll_interval = poll_interval

    def run(self) -> None:
        while not self._stopped():
            self._process_once()
            time.sleep(self._poll_interval)

    def _process_once(self) -> int:
        processed = 0
        for path in sorted(self._watch_dir.glob("*.json")):
            self._ingest_file(path)
            processed += 1
        return processed

    def _ingest_file(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping malformed trace file %s: %s", path, e)
            return
        if not isinstance(data, dict):
            logger.warning("Skipping trace file %s: expected a JSON object", path)
            return
        try:
            self._store.ingest(data)
        except ValueError as e:
            logger.warning("Skipping invalid trace %s: %s", path, e)
            return
        try:
            done = path.with_suffix(path.suffix + ".done")
            path.rename(done)
        except OSError as e:
            logger.warning("Could not move %s to .done: %s", path, e)
