"""Small scoped editorial lessons with provenance; never official algorithm facts."""
import json
import tomllib
from functools import lru_cache
from pathlib import Path
from platform_intelligence import LEGACY_FORMATS, PROFILES

PATH = Path(__file__).resolve().parents[1] / 'knowledge/source_lessons.toml'


@lru_cache(maxsize=1)
def catalog() -> dict:
    with PATH.open('rb') as file:
        data = tomllib.load(file)
    if data['version'] != 1:
        raise ValueError('unsupported lesson catalog')
    ids = set()
    for lesson in data['lessons']:
        if (lesson['id'] in ids or lesson['source'] not in data['sources']
                or not set(lesson['formats']) <= set(PROFILES) | {'all'}):
            raise ValueError('invalid source lesson')
        ids.add(lesson['id'])
    return data


def scoped_lessons(fmt: str, distribution: str = 'organic') -> list[dict]:
    key = LEGACY_FORMATS.get(fmt, fmt)
    if key not in PROFILES:
        raise ValueError('unknown format')
    data = catalog()
    return [{**lesson, 'provenance': data['sources'][lesson['source']]} for lesson in data['lessons']
            if (key in lesson['formats'] or 'all' in lesson['formats'])
            and lesson.get('distribution', distribution) == distribution]


def lesson_prompt(fmt: str, distribution: str = 'organic') -> str:
    return ('# Scoped editorial lessons (hypotheses, not official rules or evidence for claims)\n'
            + json.dumps(scoped_lessons(fmt, distribution), ensure_ascii=False)
            + '\nDo not infer fixed posting cadence, frame counts, conversion benchmarks, caption lengths, '
              'hashtag limits, recommendation eligibility or sound-off statistics from these sources. '
              'Technical features and current platform limits require official verification.')
