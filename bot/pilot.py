"""Access and budget control for pilot users.

Owner (OWNER_CHAT_ID) is unlimited. Every other user is a pilot with two caps:
  max_posts  number of generated posts
  max_usd    estimated model cost in dollars
A pilot is refused before any model call when either cap would be reached.
Config: data/pilots.json (gitignored). Usage is read from logs/posts.jsonl.
Both live under STATE_DIR. Set STATE_DIR to a persistent disk path on Render (for example /var/data),
so pilot limits survive redeploys. Without it, they are stored inside the project folder."""

import json
import os
from datetime import date
from pathlib import Path

from postlog import read_all

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.getenv("STATE_DIR") or ROOT)
CONFIG = STATE_DIR / "data" / "pilots.json"
DEFAULT_POSTS = 10
DEFAULT_USD = 1.00
PER_POST_CAP_USD = 0.25   # worst-case cost of one post; checked before each call


def _load() -> dict:
    if not CONFIG.exists():
        return {"pilots": {}}
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def owner_id() -> int:
    return int(os.getenv("OWNER_CHAT_ID", "0") or 0)


def is_owner(chat_id: int) -> bool:
    return owner_id() != 0 and chat_id == owner_id()


def get_pilot(chat_id: int) -> dict | None:
    return _load()["pilots"].get(str(chat_id))


def usage(chat_id: int) -> tuple[int, float]:
    rows = [r for r in read_all()
            if r.get("event") == "generated" and str(r.get("chat_id")) == str(chat_id)]
    return len(rows), sum(float(r.get("cost_usd", 0)) for r in rows)


def check(chat_id: int) -> tuple[bool, str]:
    """(allowed, message). Called before every generation."""
    if is_owner(chat_id):
        return True, ""
    p = get_pilot(chat_id)
    if not p or not p.get("active"):
        return False, "الحساب مو مفعّل للتجربة. ارسل /id لصاحب البوت حتى يفعّله."
    posts, cost = usage(chat_id)
    if posts >= p["max_posts"]:
        return False, f"خلصت التجربة ({posts} من {p['max_posts']} منشور). شكراً! كلم صاحب البوت لتكملة."
    if cost + PER_POST_CAP_USD > p["max_usd"]:
        return False, "خلصت ميزانية التجربة. كلم صاحب البوت لتكملة."
    return True, ""


def quota_text(chat_id: int) -> str:
    p = get_pilot(chat_id)
    if is_owner(chat_id):
        return "أنت صاحب البوت: بدون حدود."
    if not p:
        return "الحساب مو مفعّل للتجربة."
    posts, cost = usage(chat_id)
    return (f"منشورات: {posts} من {p['max_posts']} (باقي {p['max_posts'] - posts})\n"
            f"ميزانية: ${cost:.2f} من ${p['max_usd']:.2f}")


def add(chat_id: int, name: str, max_posts: int = DEFAULT_POSTS, max_usd: float = DEFAULT_USD) -> None:
    data = _load()
    data["pilots"][str(chat_id)] = {"name": name, "max_posts": max_posts, "max_usd": max_usd,
                                    "active": True, "added": date.today().isoformat()}
    _save(data)


def set_active(chat_id: int, active: bool) -> bool:
    data = _load()
    p = data["pilots"].get(str(chat_id))
    if not p:
        return False
    p["active"] = active
    _save(data)
    return True


def list_text() -> str:
    pilots = _load()["pilots"]
    if not pilots:
        return "ماكو تجارب مسجلة."
    lines = []
    for cid, p in pilots.items():
        posts, cost = usage(int(cid))
        state = "فعّال" if p.get("active") else "متوقف"
        lines.append(f"{p['name']} ({cid}): {state} | منشورات {posts}/{p['max_posts']} | "
                     f"${cost:.2f}/${p['max_usd']:.2f}")
    return "\n".join(lines)
