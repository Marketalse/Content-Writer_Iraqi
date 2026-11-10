"""Batch: classify Notion topics into story / reel / linkedin, then write a script for each.

Steps (run on your own computer or server, where ANTHROPIC_API_KEY is set in .env):

  1. Export the topics table from Notion to CSV (Notion: ... > Export > CSV).
     Save it as knowledge/topics/topics.csv. Only rows with Forma = Topic are used.

  2. Classify (cheap, Haiku):
       python3 bot/topics_batch.py classify --csv knowledge/topics/topics.csv
     Writes output/classification.csv. Open it, read the format column, and change any
     row you disagree with. Set format to "skip" to leave a topic out.

  3. Write (Sonnet, about 3 to 4 calls per topic):
       python3 bot/topics_batch.py write --max-usd 40
     Writes output/scripts/<id>-<format>.md and output/scripts_index.csv.
     Reserves each pipeline's configured spending allowance before starting work.
     --max-usd controls observed spend plus in-flight reservations; provider billing
     can exceed a per-run observed stop on a final call. Run again to continue: topics that
     already have a file are skipped.

Formats:
  story     30 second story script (about 75 words)
  reel      60+ second reel script (about 150 words)
  linkedin  professional LinkedIn post
"""

import argparse
import asyncio
import csv
import json
import logging
import math
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BOT = Path(__file__).resolve().parent
ROOT = BOT.parent
sys.path.insert(0, str(BOT))
load_dotenv(ROOT / ".env")

from llm import FAST_MODEL, generate  # noqa: E402
from pipeline import run_pipeline  # noqa: E402
from revision import Settings  # noqa: E402
from prompts import ANGLES, build_system_prompt  # noqa: E402

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
for noisy in ("httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("topics-batch")

OUT = ROOT / "output"
CLASSIFICATION = OUT / "classification.csv"
INDEX = OUT / "scripts_index.csv"
SCRIPTS = OUT / "scripts"
WRITE_FORMATS = ("story", "reel", "linkedin")
CLASSIFY_BATCH = 25
ANGLE_KEYS = list(ANGLES)  # rotated per topic so the batch does not repeat one angle

CLASSIFY_SYSTEM = """أنت مخطط محتوى لصفحة عراقية. صنّف كل موضوع حسب الفورمة المناسبة له:
- story: ستوري ٣٠ ثانية (حوالي ٧٥ كلمة). فكرة وحدة، نصيحة، أو خرافة واحدة. بدون خطوات طويلة ولا قصة.
- reel: ريل ٦٠ ثانية فما فوق (حوالي ١٥٠ كلمة). موضوع يحتاج مثال، موقف قصير، أو شرح بصري يناسب الفكرة، بدون عدد خطوات ثابت.
- linkedin: منشور احترافي لأصحاب المشاريع والمسوقين. تحليل، درس من تجربة، رأي، أو قرار عن التسعير أو الفريق أو الإدارة.
ارجع فقط JSON بهذا الشكل، بدون أي شرح خارجه:
[{"id": "...", "format": "story|reel|linkedin", "reason": "سبب قصير"}]"""


def read_topics(path: Path) -> list[dict]:
    """Reads a Notion CSV export. Column names are matched without case."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    topics = []
    for r in rows:
        cols = {k.strip().lower(): k for k in r if k}

        def get(*names: str) -> str:
            for n in names:
                key = cols.get(n.lower())
                if key and (r.get(key) or "").strip():
                    return r[key].strip()
            return ""

        if get("Forma") and get("Forma") != "Topic":
            continue  # headers and notes in the Notion table
        name = get("Name")
        if not name:
            continue
        topics.append({
            "id": get("userDefined:ID", "ID") or str(len(topics) + 1),
            "name": name,
            "pillar": get("Pillar"),
        })
    return topics


def parse_json_list(text: str) -> list[dict]:
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


async def classify(topics: list[dict]) -> list[dict]:
    decided: dict[str, dict] = {}
    cost = 0.0
    for i in range(0, len(topics), CLASSIFY_BATCH):
        batch = topics[i:i + CLASSIFY_BATCH]
        user = "\n".join(f'{t["id"]} | {t["name"]} | {t["pillar"]}' for t in batch)
        res = await generate(CLASSIFY_SYSTEM, user, model=FAST_MODEL, max_tokens=2500)
        cost += res.cost_usd
        for item in parse_json_list(res.text):
            decided[str(item.get("id"))] = item
        log.info("classified %d/%d", min(i + CLASSIFY_BATCH, len(topics)), len(topics))

    rows = []
    for t in topics:
        item = decided.get(t["id"], {})
        fmt = str(item.get("format", "review")).strip().lower()
        if fmt not in WRITE_FORMATS + ("skip",):
            fmt = "review"  # model gave an unknown answer: check it by hand
        rows.append({**t, "format": fmt, "reason": item.get("reason", "no answer from model")})
    log.info("classification cost $%.4f", cost)
    return rows


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def cmd_classify(args) -> None:
    topics = read_topics(Path(args.csv))
    log.info("%d topics read from %s", len(topics), args.csv)
    rows = asyncio.run(classify(topics))
    write_csv(CLASSIFICATION, rows, ["id", "name", "pillar", "format", "reason"])
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["format"]] = counts.get(r["format"], 0) + 1
    print(f"Wrote {CLASSIFICATION}")
    print("Counts:", counts)
    print("Open the file, check the format column, then run the write step.")


def load_classification() -> list[dict]:
    if not CLASSIFICATION.exists():
        raise SystemExit("Run the classify step first (no output/classification.csv).")
    with CLASSIFICATION.open(encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if (r.get("format") or "").strip() in WRITE_FORMATS]


def append_index(record: dict) -> None:
    columns = ["id", "name", "pillar", "format", "angle", "status", "attempts",
               "failures", "provider", "cost_usd", "file"]
    new = not INDEX.exists()
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    with INDEX.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(record)


async def write_all(rows: list[dict], budget: float, concurrency: int) -> None:
    if type(concurrency) is not int or not 1 <= concurrency <= 16:
        raise ValueError('concurrency must be an integer from 1 to 16')
    if type(budget) not in (int, float) or not math.isfinite(budget) or budget <= 0:
        raise ValueError('budget must be finite and positive')
    settings = Settings.from_env()
    reservation = settings.max_cost_usd
    systems = {fmt: build_system_prompt(fmt) for fmt in WRITE_FORMATS}
    sem = asyncio.Semaphore(concurrency)
    available = asyncio.Condition()
    state = {"cost": 0.0, "reserved": 0.0, "active": 0, "done": 0,
             "stopped": False, "uncertain": False}

    async def one(idx: int, row: dict) -> None:
        fmt = row["format"].strip()
        key = f'{row["id"]}-{fmt}'
        path = SCRIPTS / f"{key}.md"
        if path.exists():  # a file means this topic and format were already written
            return
        async with sem:
            async with available:
                while not state['stopped'] and state['cost'] + state['reserved'] + reservation > budget + 1e-12:
                    if state['active'] == 0:
                        state['stopped'] = True
                        available.notify_all()
                        return
                    await available.wait()
                if state['stopped']:
                    return
                state['reserved'] += reservation
                state['active'] += 1
            angle = ANGLE_KEYS[idx % len(ANGLE_KEYS)]
            base = {"id": row["id"], "name": row["name"], "pillar": row.get("pillar", ""),
                    "format": fmt, "angle": angle}
            try:
                run = await run_pipeline(fmt, systems[fmt], row["name"], ANGLES[angle], settings=settings)
                usage_known = (all(call.usage_known for call in run.calls)
                               and all(timing['status'] == 'ok' for timing in run.timings))
                state['cost'] += run.cost_usd
                state['done'] += 1
                if not usage_known or run.cost_usd > reservation + 1e-12:
                    state['stopped'] = True
                    state['uncertain'] = not usage_known
                    log.warning('Batch stopped: unknown usage or per-run spending allowance exceeded')
                save_result(row, base, run, path)
            except asyncio.CancelledError:
                state['stopped'] = state['uncertain'] = True
                raise
            except Exception as exc:
                # Failed attempts may already have been billed: do not start more work.
                state['stopped'] = state['uncertain'] = True
                log.error('Batch stopped after incomplete attempt; type=%s', type(exc).__name__)
                append_index({**base, 'status': 'error', 'failures': 'incomplete attempt; usage may be unknown'})
            finally:
                async with available:
                    state['reserved'] -= reservation
                    state['active'] -= 1
                    available.notify_all()
            if state['done'] and state['done'] % 25 == 0:
                log.info('%d written, observed spend $%.2f', state['done'], state['cost'])

    await asyncio.gather(*(one(i, r) for i, r in enumerate(rows)))
    if state['stopped']:
        log.warning('Batch stopped: no safe reservation remains or an attempt needs review; budget $%.2f', budget)
    log.info('finished: %d written this run, observed spend %s$%.2f', state['done'],
             'at least ' if state['uncertain'] else '', state['cost'])


def save_result(row: dict, base: dict, run, path: Path) -> None:
    checked = run.checked
    if checked.clarification:
        status = "needs_clarification"
    elif checked.refused:
        status = "refused"
    elif not checked.text:
        status = "empty"
    elif checked.failures:
        status = "check_failed"
    else:
        status = "ok"

    file_rel = ""
    if checked.text:
        SCRIPTS.mkdir(parents=True, exist_ok=True)
        body = f"# {row['name']}\n\nID: {row['id']} | {base['format']} | زاوية: {base['angle']}\n\n{checked.text}\n"
        if checked.owner_note:
            body += f"\n---\nملاحظة لك (لا تنشرها):\n{checked.owner_note}\n"
        path.write_text(body, encoding="utf-8")
        file_rel = str(path.relative_to(ROOT))

    append_index({**base, "status": status, "attempts": checked.attempts,
                  "failures": " | ".join(checked.failures + ([checked.clarification] if checked.clarification else []))[:500],
                  "provider": checked.provider, "cost_usd": round(run.cost_usd, 5),
                  "file": file_rel})


def cmd_write(args) -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set in .env")
    rows = load_classification()
    if args.format:
        rows = [r for r in rows if r["format"] == args.format]
    if args.limit:
        rows = rows[:args.limit]
    print(f"{len(rows)} topics to write (budget ${args.max_usd:.2f})")
    try:
        asyncio.run(write_all(rows, args.max_usd, args.concurrency))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify", help="pick story / reel / linkedin for each topic")
    c.add_argument("--csv", default=str(ROOT / "knowledge" / "topics" / "topics.csv"))
    c.set_defaults(func=cmd_classify)

    w = sub.add_parser("write", help="write a script for each classified topic")
    w.add_argument("--max-usd", type=float, default=40.0, help="stop when spend reaches this")
    w.add_argument("--limit", type=int, default=0, help="only the first N topics (for a test run)")
    w.add_argument("--format", choices=WRITE_FORMATS, help="only one format")
    w.add_argument("--concurrency", type=int, default=3)
    w.set_defaults(func=cmd_write)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
