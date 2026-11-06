"""Post log and reach sheet.

logs/posts.jsonl is append-only: one line per generated post, one line per 'published' mark.
export_reach_sheet() writes knowledge/feedback/reach_log.csv for you to fill in reach and replies.
Nothing is changed in the content from these numbers until you compare them against a baseline.
"""

import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "posts.jsonl"
SHEET = ROOT / "knowledge" / "feedback" / "reach_log.csv"
SHEET_COLUMNS = ["id", "date", "format", "angle", "topic", "provider", "attempts",
                 "cost_usd", "published_date", "reach", "replies", "notes"]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def read_all() -> list[dict]:
    return _read()


def log_post(record: dict) -> str:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    pid = datetime.now().strftime("%Y%m%d%H%M%S")
    row = {"event": "generated", "id": pid, "date": _now(), **record}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return pid


def mark_published(pid: str) -> bool:
    if not any(r.get("event") == "generated" and r["id"] == pid for r in _read()):
        return False
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "published", "id": pid, "date": _now()}, ensure_ascii=False) + "\n")
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
