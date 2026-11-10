"""Synthetic research fixtures; never evidence of a successful live search."""
import json
from llm import Result


def routed(action='research', **overrides):
    data = {'action': action, 'factual_claims': action == 'research', 'needs_numbers': False,
            'official_sources_required': False,
            'reason': 'factual_topic' if action == 'research' else 'style_only' if action == 'rewrite' else 'no_factual_claims',
            'clarification': ''}
    data.update(overrides)
    return Result(json.dumps(data), 'mock')


def researched():
    return Result(json.dumps({'status': 'ready', 'clarification': '',
                              'summary': 'Synthetic primary-source background for offline tests.'}),
                  'mock', sources=[{'url': 'https://cbi.iq/example', 'title': 'Test fixture',
                                    'excerpt': 'Synthetic source excerpt.'}], search_requests=1)
