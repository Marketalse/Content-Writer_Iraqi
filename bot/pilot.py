"""Access and budget control for pilot users.

Owner (OWNER_CHAT_ID) is unlimited. Every other user is a pilot with two caps:
  max_posts  number of generated posts
  max_usd    estimated model cost in dollars
A pilot is refused before any model call when either cap would be reached.
Config: data/pilots.json (gitignored). Usage is read from logs/posts.jsonl.
Both live under STATE_DIR. Set STATE_DIR to a persistent disk path on Render (for example /var/data),
so pilot limits survive redeploys. Without it, they are stored inside the project folder."""

import json
import logging
import math
import os
from datetime import date
from pathlib import Path

from postlog import read_all
from storage import StorageError, atomic_write_bytes

log = logging.getLogger('pilot')

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.getenv("STATE_DIR") or ROOT)
CONFIG = STATE_DIR / "data" / "pilots.json"
DEFAULT_POSTS = 10
DEFAULT_USD = 1.00
PER_POST_CAP_USD = 0.25   # worst-case cost of one post; checked before each call


def _load() -> dict:
    if not CONFIG.exists():
        return {"pilots": {}}
    try:
        data = json.loads(CONFIG.read_text(encoding='utf-8'))
        _validate(data)
        return data
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise StorageError('Pilot configuration is invalid; operator review required') from exc


def _validate(data: dict) -> None:
    if not isinstance(data, dict) or not isinstance(data.get('pilots'), dict):
        raise ValueError('invalid pilot configuration')
    for item in data['pilots'].values():
        if (not isinstance(item, dict) or type(item.get('active')) is not bool
                or type(item.get('max_posts')) is not int or item['max_posts'] < 0
                or type(item.get('max_usd')) not in (int, float)
                or not math.isfinite(item['max_usd']) or item['max_usd'] < 0):
            raise ValueError('invalid pilot record')


def _save(data: dict) -> None:
    _validate(data)
    contents = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    if CONFIG.exists():
        _load()  # Never overwrite a corrupt settings file or silently restore old permissions.
        atomic_write_bytes(CONFIG.with_suffix(CONFIG.suffix + '.bak'), CONFIG.read_bytes())
    atomic_write_bytes(CONFIG, contents)


def owner_id() -> int:
    return int(os.getenv("OWNER_CHAT_ID", "0") or 0)


def is_owner(chat_id: int) -> bool:
    return owner_id() != 0 and chat_id == owner_id()


def get_pilot(chat_id: int) -> dict | None:
    return _load()["pilots"].get(str(chat_id))


def usage(chat_id: int) -> tuple[int, float]:
    rows = [r for r in read_all()
            if r.get("event") in ("generated", "clarification") and str(r.get("chat_id")) == str(chat_id)]
    return sum(r["event"] == "generated" for r in rows), sum(
        float(r.get("quota_cost_usd", r.get("cost_usd", 0))) for r in rows)


def check(chat_id: int) -> tuple[bool, str]:
    """(allowed, message). Called before every generation."""
    allowed = {int(x) for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if x.strip()}
    if is_owner(chat_id) or chat_id in allowed:
        return True, ""
    try:
        p = get_pilot(chat_id)
        posts, cost = usage(chat_id) if p and p.get('active') else (0, 0)
    except OSError:
        log.error('Pilot admission denied: persistent account data unavailable')
        return False, 'تعذّر قراءة بيانات الحساب أو سجل الاستخدام. كلم صاحب البوت حتى يراجع التخزين.'
    if not p or not p.get("active"):
        return False, "الحساب مو مفعّل للتجربة. ارسل /id لصاحب البوت حتى يفعّله."
    if posts >= p["max_posts"]:
        return False, f"خلصت التجربة ({posts} من {p['max_posts']} منشور). شكراً! كلم صاحب البوت لتكملة."
    if cost + PER_POST_CAP_USD > p["max_usd"]:
        return False, "خلصت ميزانية التجربة. كلم صاحب البوت لتكملة."
    return True, ""


def quota_text(chat_id: int) -> str:
    p = get_pilot(chat_id)
    if is_owner(chat_id):
        return "أنت صاحب البوت: بدون حدود."
    if chat_id in {int(x) for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if x.strip()}:
        return "حسابك مفعّل بدون حدود."
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
