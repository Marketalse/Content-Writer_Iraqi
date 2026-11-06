"""One local story generation, without Telegram.

Usage (from the repo root, with .env filled in):
    python3 bot/test_story.py                       # story, default topic
    python3 bot/test_story.py "your topic"          # story, your topic
    python3 bot/test_story.py linkedin "your topic" # any format: story, carousel, reel, linkedin
"""

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
import asyncio  # noqa: E402

from llm import LLMError  # noqa: E402
from quality import generate_checked  # noqa: E402
from prompts import build_system_prompt  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

DEFAULT_TOPIC = (
    "صاحب محل ملابس بالبتاوين، بداية الشهر كانت الحركة ميتة، "
    "وقرر يسوي شي مختلف: يرجع أول زبون صار يشتري منه ويسولف معاه"
)
from prompts import FORMATS  # noqa: E402

args = sys.argv[1:]
fmt = "story"
if args and args[0] in FORMATS:
    fmt = args.pop(0)
topic = " ".join(args).strip() or DEFAULT_TOPIC


async def main():
    try:
        result = await generate_checked(fmt, build_system_prompt(fmt), topic)
    except LLMError as exc:
        sys.exit(f"Generation failed: {exc}")
    print(f"provider={result.provider} refused={result.refused} attempts={result.attempts}")
    if result.failures:
        print("QUALITY CHECK FAILED:\n- " + "\n- ".join(result.failures))
    print("-" * 60)
    print(result.text or "(empty answer)")
    if result.owner_note:
        print("-" * 60)
        print("OWNER NOTE (do not publish):\n" + result.owner_note)


asyncio.run(main())
