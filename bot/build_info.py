"""Safe runtime identity for deployment diagnosis; never read or report secrets."""
import hashlib
import os
import re
from pathlib import Path

from format_contracts import FORMAT_CONTRACT_VERSION
from content_choices import WORKFLOW_VERSION

ROOT = Path(__file__).resolve().parent
SOURCE_FILES = ('bot.py', 'llm.py', 'build_info.py', 'prompts.py', 'format_contracts.py',
                'diagnostics.py', 'draft_transport.py', 'platform_intelligence.py', 'pipeline.py', 'revision.py', 'quality.py', 'reviewer.py',
                'frameworks.py', 'content_choices.py', 'briefs.py', 'story_styles.py', 'production.py', 'source_knowledge.py', 'editorial.py',
                '../knowledge/frameworks.toml', '../knowledge/source_lessons.toml')


def _source_digest() -> str:
    digest = hashlib.sha256()
    for name in SOURCE_FILES:
        digest.update(name.encode())
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()[:12]


# Snapshot once, describing the sources used by this process at import/startup.
SOURCE_DIGEST = _source_digest()


def build_info(system_prompt: str = '') -> dict[str, str]:
    commit = os.getenv('RENDER_GIT_COMMIT') or os.getenv('APP_GIT_COMMIT') or ''
    branch = os.getenv('RENDER_GIT_BRANCH') or ''
    return {
        'format_contract': FORMAT_CONTRACT_VERSION,
        'workflow': WORKFLOW_VERSION,
        'commit': commit if re.fullmatch(r'[0-9a-fA-F]{7,40}', commit) else 'unknown',
        'branch': branch if re.fullmatch(r'[A-Za-z0-9_./-]{1,100}', branch) else 'unknown',
        'source': SOURCE_DIGEST,
        'prompt': hashlib.sha256(system_prompt.encode()).hexdigest()[:12] if system_prompt else 'none',
        'entrypoint': 'bot/bot.py',
    }
