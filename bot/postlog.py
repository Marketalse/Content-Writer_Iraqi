"""Post log and reach sheet.

logs/posts.jsonl is append-only: one line per generated post, one line per 'published' mark.
export_reach_sheet() writes knowledge/feedback/reach_log.csv for you to fill in reach and replies.
Nothing is changed in the content from these numbers until you compare them against a baseline.
"""

import csv
import json
import logging
import os
from threading import RLock
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from storage import StorageError, atomic_write_bytes

log = logging.getLogger('postlog')
_LOCK = RLock()

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.getenv("STATE_DIR") or ROOT)  # persistent disk on Render, see pilot.py
LOG = STATE_DIR / "logs" / "posts.jsonl"
SHEET = ROOT / "knowledge" / "feedback" / "reach_log.csv"
SHEET_COLUMNS = ["id", "date", "format", "angle", "topic", "provider", "attempts",
                 "cost_usd", "published_date", "reach", "replies", "notes"]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read() -> list[dict]:
    with _LOCK:
        if not LOG.exists():
            return []
        data = LOG.read_bytes()
        lines = data.splitlines(keepends=True)
        rows = []
        offset = 0
        for index, line in enumerate(lines):
            if line.strip():
                try:
                    row = json.loads(line)
                except (ValueError, UnicodeError) as exc:
                    if index == len(lines) - 1 and not line.endswith((b'\n', b'\r')):
                        # Preserve the exact bytes before repairing only a torn final append.
                        quarantine = LOG.with_name(LOG.name + '.torn-' + uuid4().hex)
                        atomic_write_bytes(quarantine, line)
                        atomic_write_bytes(LOG, data[:offset])
                        log.warning('Incomplete journal tail quarantined and repaired; bytes=%d', len(line))
                        return rows
                    raise StorageError('Journal contains a malformed complete record') from exc
                if not isinstance(row, dict):
                    raise StorageError('Journal record is not an object')
                rows.append(row)
            offset += len(line)
        return rows


def _append(row: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    separator = ''
    if LOG.exists() and LOG.stat().st_size:
        with LOG.open('rb') as file:
            file.seek(-1, os.SEEK_END)
            separator = '' if file.read(1) == b'\n' else '\n'
    with LOG.open('a', encoding='utf-8') as file:
        file.write(separator + json.dumps(row, ensure_ascii=False) + '\n')
        file.flush()
        os.fsync(file.fileno())


def read_all() -> list[dict]:
    return _read()


def log_post(record: dict, *, event: str = 'generated') -> str:
    if event not in ('generated', 'clarification'):
        raise ValueError('unsupported generation event')
    pid = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
    row = {**record, "event": event, "id": pid, "date": _now()}
    with _LOCK:
        _read()
        _append(row)
    return pid


def mark_published(pid: str) -> bool:
    with _LOCK:
        rows = _read()
        if not any(r.get('event') == 'generated' and r.get('id') == pid
                   and r.get('quality_status', 'accepted') == 'accepted' for r in rows):
            return False
        if not any(r.get('event') == 'published' and r.get('id') == pid for r in rows):
            _append({'event': 'published', 'id': pid, 'date': _now()})
        return True


def export_reach_sheet() -> Path:
    rows = _read()
    published = {r["id"]: r["date"] for r in rows if r.get("event") == "published"}
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    with SHEET.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
        w.writeheader()
        for r in rows:
            if r.get("event") != "generated":
                continue
            w.writerow({
                "id": r["id"], "date": r["date"], "format": r.get("format", ""),
                "angle": r.get("angle", ""), "topic": r.get("topic", ""),
                "provider": r.get("provider", ""), "attempts": r.get("attempts", ""),
                "cost_usd": f"{r.get('cost_usd', 0):.5f}",
                "published_date": published.get(r["id"], ""),
                "reach": "", "replies": "", "notes": "",
            })
    return SHEET


if __name__ == "__main__":
    print(export_reach_sheet())
