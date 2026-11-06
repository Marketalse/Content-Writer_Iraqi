"""One local generation through the full pipeline, without Telegram.

Usage (from the repo root, with .env filled in):
    python3 bot/test_story.py                          # story, default topic and angle
    python3 bot/test_story.py reel "your topic"        # any format: story, carousel, reel, linkedin
    python3 bot/test_story.py linkedin myth "topic"    # optional angle key first: myth, tip, behind, pain, offer, flip
"""

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
if not ENV_FILE.exists():
    sys.exit(f"No .env file at {ENV_FILE}. Run: cp .env.example .env, then fill it in.")
load_dotenv(ENV_FILE)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import LLMError  # noqa: E402
from pipeline import run_pipeline  # noqa: E402
from prompts import ANGLES, FORMATS, build_system_prompt  # noqa: E402

for noisy in ("httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

DEFAULT_TOPIC = "صاحب محل ملابس بالبتاوين، بداية الشهر كانت الحركة ميتة، وقرر يسوي شي مختلف"

args = sys.argv[1:]
fmt = "story"
angle = "tip"
if args and args[0] in FORMATS:
    fmt = args.pop(0)
if args and args[0] in ANGLES:
    angle = args.pop(0)
topic = " ".join(args).strip() or DEFAULT_TOPIC


async def main():
    try:
        run = await run_pipeline(fmt, build_system_prompt(fmt), topic, ANGLES[angle])
    except LLMError as exc:
        sys.exit(f"Generation failed: {exc}")
    c = run.checked
    print(f"format={fmt} angle={angle} provider={c.provider} attempts={c.attempts} refused={c.refused}")
    print(f"calls={len(run.calls)} input_tokens={run.input_tokens} output_tokens={run.output_tokens} "
          f"cost≈${run.cost_usd:.5f}")
    if c.failures:
        print("QUALITY CHECK FAILED:\n- " + "\n- ".join(c.failures))
    print("-" * 60)
    print(c.text or "(empty answer)")
    if c.owner_note:
        print("-" * 60)
        print("OWNER NOTE (do not publish):\n" + c.owner_note)


asyncio.run(main())
