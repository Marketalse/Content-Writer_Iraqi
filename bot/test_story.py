"""One local story generation, without Telegram.

Usage (from the repo root, with .env filled in):
    python3 bot/test_story.py
    python3 bot/test_story.py "your own topic here"
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prompts import build_system_prompt  # noqa: E402

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if not ENV_FILE.exists():
    sys.exit(f"No .env file at {ENV_FILE}. Run: cp .env.example .env, then fill it in.")
load_dotenv(ENV_FILE)

api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
if not api_key:
    sys.exit(
        "ANTHROPIC_API_KEY is empty. In .env, the line must read ANTHROPIC_API_KEY=<key>\n"
        "(no spaces around =, no quotes, and the word ANTHROPIC_API_KEY must be on that line)."
    )

DEFAULT_TOPIC = (
    "صاحب محل ملابس بالبتاوين، بداية الشهر كانت الحركة ميتة، "
    "وقرر يسوي شي مختلف: يرجع أول زبون صار يشتري منه ويسولف معاه"
)
topic = " ".join(sys.argv[1:]).strip() or DEFAULT_TOPIC

client = Anthropic(api_key=api_key)
response = client.messages.create(
    model="claude-opus-5-5",
    max_tokens=4000,
    system=[
        {
            "type": "text",
            "text": build_system_prompt("story"),
            "cache_control": {"type": "ephemeral"},
        }
    ],
    messages=[{"role": "user", "content": f"الموضوع: {topic}"}],
)

u = response.usage
print(f"stop_reason={response.stop_reason} in={u.input_tokens} out={u.output_tokens} "
      f"cache_read={u.cache_read_input_tokens} cache_write={u.cache_creation_input_tokens}")
print("-" * 60)
print("".join(b.text for b in response.content if b.type == "text"))
