"""One local story generation, without Telegram.

Usage (from the repo root, with .env filled in):
    python3 bot/test_story.py
    python3 bot/test_story.py "your own topic here"
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

from llm import LLMError, generate  # noqa: E402
from prompts import build_system_prompt  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

DEFAULT_TOPIC = (
    "صاحب محل ملابس بالبتاوين، بداية الشهر كانت الحركة ميتة، "
    "وقرر يسوي شي مختلف: يرجع أول زبون صار يشتري منه ويسولف معاه"
)
topic = " ".join(sys.argv[1:]).strip() or DEFAULT_TOPIC


async def main():
    try:
        result = await generate(build_system_prompt("story"), f"الموضوع: {topic}")
    except LLMError as exc:
        sys.exit(f"Generation failed: {exc}")
    print(f"provider={result.provider} refused={result.refused}")
    print("-" * 60)
    print(result.text or "(empty answer)")


asyncio.run(main())
