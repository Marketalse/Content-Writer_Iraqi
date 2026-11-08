"""Optional structured intent, evidence and production constraints, validated before calls."""
import json
from dataclasses import asdict, dataclass
from platform_intelligence import LEGACY_FORMATS, get_profile

STORY_MODES = ('moment', 'teaching', 'poll', 'reveal', 'demonstration', 'referral')
VIDEO_FORMATS = ('instagram_reel', 'tiktok_video')


@dataclass(frozen=True)
class Brief:
    audience: str = ''
    purpose: str = 'educate'
    takeaway: str = ''
    desired_action: str = ''
    journey_stage: str = 'awareness'
    distribution: str = 'organic'
    story_mode: str = 'moment'
    production: bool = False
    duration_seconds: int = 30
    filming_constraints: str = ''
    source_material: str = ''
    evidence: tuple[dict, ...] = ()

    def __post_init__(self):
        for name in ('audience', 'takeaway', 'desired_action', 'filming_constraints'):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) > 1000:
                raise ValueError(f'invalid brief {name}')
        if not isinstance(self.source_material, str) or len(self.source_material) > 16000:
            raise ValueError('invalid source material')
        if self.purpose not in ('educate', 'entertain', 'trust', 'conversation', 'promote'):
            raise ValueError('invalid purpose')
        if self.journey_stage not in ('awareness', 'consideration', 'decision', 'relationship'):
            raise ValueError('invalid journey stage')
        if self.distribution not in ('organic', 'paid') or self.story_mode not in STORY_MODES:
            raise ValueError('invalid distribution or Story mode')
        if type(self.production) is not bool or type(self.duration_seconds) is not int or not 5 <= self.duration_seconds <= 180:
            raise ValueError('invalid production settings')
        if not isinstance(self.evidence, tuple) or len(self.evidence) > 12:
            raise ValueError('invalid evidence')
        for item in self.evidence:
            if (not isinstance(item, dict) or set(item) != {'text', 'source'}
                    or any(not isinstance(v, str) or not v.strip() or len(v) > 1200 for v in item.values())):
                raise ValueError('evidence requires text and provenance')

    def validate_format(self, fmt: str):
        key = LEGACY_FORMATS.get(fmt, fmt)
        get_profile(key)
        if self.story_mode != 'moment' and key not in ('instagram_story', 'tiktok_story'):
            raise ValueError('Story modes require a Story format')
        if self.production and key not in VIDEO_FORMATS:
            raise ValueError('production mode requires Instagram Reel or TikTok Video')

    def data(self) -> dict:
        return asdict(self)


def parse_brief(raw: str) -> Brief:
    if len(raw) > 22000:
        raise ValueError('brief too large')
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) - set(Brief.__dataclass_fields__):
        raise ValueError('unknown brief fields')
    if 'evidence' in data:
        if not isinstance(data['evidence'], list):
            raise ValueError('evidence must be a list')
        data['evidence'] = tuple(data['evidence'])
    return Brief(**data)
