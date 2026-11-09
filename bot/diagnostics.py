"""Read-only, access-scoped failure summaries; never expose model/SDK payloads."""
from editorial import authorized_post
from reviewer import DIMENSIONS, GATES
from platform_intelligence import PROFILES

NEXT_ACTIONS = {
    'accepted': 'المحاولة اجتازت المراجعة.',
    'invalid_structure': 'تعذّر ترتيب النص بالصيغة المطلوبة. تگدر تغيّر البنية أو تعيد المحاولة.',
    'verified_fact_missing': 'المسودة ما حافظت على المعلومات المطلوبة. نحتاج مراجعتها قبل عرضها.',
    'critical_gate': 'المسودة توقفت عند فحص إلزامي وتحتاج مراجعة قبل عرضها.',
    'creative_threshold': 'المسودة ما وصلت لمستوى الجودة المطلوب بعد المراجعة.',
    'revision_no_improvement': 'التعديل ما حسّن المسودة للمستوى المطلوب.',
    'provider_error': 'تعذّر الاتصال بخدمة الكتابة أو المراجعة. جرّب بعد شوية.',
    'provider_timeout': 'خدمة الكتابة أو المراجعة تأخرت وتوقفت المحاولة. جرّب بعد شوية.',
    'unknown_pricing': 'توقفت المحاولة لأن كلفة الموديل مو معروفة بالإعدادات. يحتاج صاحب البوت يراجعها.',
    'resource_limit': 'وصلت المحاولة لحد الوقت أو الاستخدام المحدد. يحتاج صاحب البوت يراجع التشخيص.',
    'invalid_response': 'خدمة الكتابة أو المراجعة رجعت جواب ما نكدر نعالجه. يحتاج مراجعة التشخيص.',
    'review_truncated': 'جواب المراجعة ما اكتمل. يحتاج صاحب البوت يراجع التشخيص.',
    'review_empty': 'خدمة المراجعة ما رجّعت تقييم. جرّب بعد شوية.',
    'review_refused': 'خدمة المراجعة ما گدرت تقيّم هالمسودة.',
    'writer_truncated': 'نص المسودة ما اكتمل، لذلك ما عرضناه.',
    'writer_refused': 'خدمة الكتابة ما گدرت تجهّز هالمسودة.',
    'revision_refused': 'خدمة التعديل ما گدرت تكمّل هالمسودة.',
    'revision_truncated': 'جواب التعديل ما اكتمل، لذلك ما عرضناه.',
    'missing_information': 'الموضوع يحتاج تفاصيل إضافية قبل الكتابة.',
}

# Fixed parser codes share a user message; diagnosis retains the exact safe code.
for _code in ('invalid_review_json', 'duplicate_review_key', 'oversized_review',
              'invalid_review_keys', 'invalid_review_dimensions', 'invalid_review_scores',
              'invalid_review_gates', 'invalid_review_issues', 'invalid_review_section_issue'):
    NEXT_ACTIONS[_code] = 'جواب المراجعة ما طابق صيغة التقييم المطلوبة. يحتاج صاحب البوت يراجع التشخيص.'


def validation_checks(record: dict) -> list[str]:
    """Fixed tags for historical validator messages; never echo their text."""
    tags = set()
    for item in record.get('failures') or []:
        if not isinstance(item, str):
            continue
        for marker, tag in (
            ('missing or empty', 'missing_field'), ('required order', 'section_order'),
            ('unrecognized content before', 'unexpected_preamble'),
            ('short Story exceeds', 'short_story_length'), ('editorial word target', 'editorial_length'),
            ('retired', 'retired_template'), ('duplicate native section', 'duplicate_section'),
            ('too many hashtags', 'hashtag_limit'), ('AI cliche', 'cliche'),
            ('numbering must be consecutive', 'sequence_numbering'),
            ('too dense', 'slide_density')):
            if marker in item:
                tags.add(tag)
        if item.startswith(tuple(key + ':' for key in PROFILES)):
            tags.add('native_format_check')
    return sorted(tags)


def failure_code(record: dict) -> str:
    """Classify historical records conservatively; unknown reasons stay unknown."""
    code = record.get('failure_code')
    if isinstance(code, str) and code in NEXT_ACTIONS:
        return code
    failures = record.get('failures') or []
    if record.get('quality_status') == 'accepted' and not failures:
        return 'accepted'
    if any(isinstance(item, str) and item.startswith(tuple(g + ':' for g in GATES)) for item in failures):
        return 'critical_gate'
    if 'creative thresholds not met' in failures:
        return 'creative_threshold'
    if 'verified fact missing or altered' in failures:
        return 'verified_fact_missing'
    if validation_checks(record):
        return 'invalid_structure'
    if any(isinstance(item, str) and item.startswith('quality assessment incomplete:') for item in failures):
        suffix = next(item.rsplit(':', 1)[-1].strip() for item in failures
                      if isinstance(item, str) and item.startswith('quality assessment incomplete:'))
        return {'LLMError':'provider_error','TimeoutError':'provider_timeout'}.get(suffix,'unknown')
    return 'unknown'


def failure_message(record: dict, pid: str) -> str:
    message = NEXT_ACTIONS.get(failure_code(record), 'المحاولة ما اكتملت. نحتاج نشوف التشخيص حتى نحدد السبب.')
    return message + '\nرقم المراجعة: ' + pid + '\nللتشخيص: /diagnose ' + pid + '\nلتغيير الاختيارات: /format'


def diagnostic_report(pid: str, actor: int) -> dict:
    record = authorized_post(pid, actor)
    out = {key: record[key] for key in (
        'id', 'quality_status', 'format', 'story_mode', 'story_intent', 'structure_id',
        'transport_normalized', 'manual_review_ready', 'delivery_status', 'failure_stage', 'calls', 'attempts', 'usage_known',
        'elapsed_ms', 'input_tokens', 'output_tokens', 'cost_usd') if key in record}
    out['planning'] = {key: record.get('planning', {}).get(key)
                       for key in ('purpose','framework','fallback','fallback_reason')
                       if key in record.get('planning', {})}
    out['failure_code'] = failure_code(record)
    out['validation_checks'] = validation_checks(record)
    out['next_action'] = NEXT_ACTIONS.get(out['failure_code'], 'راجع مراحل المحاولة؛ السجل القديم ما يحدد السبب بدقة.')
    out['build'] = {key: record.get('build', {}).get(key, 'unknown')
                    for key in ('commit', 'source', 'workflow')}
    out['stages'] = [{key: timing[key] for key in (
        'stage', 'status', 'elapsed_ms', 'output_chars', 'truncated', 'refused', 'usage_known',
        'provider', 'model', 'stop_reason', 'thinking_blocks', 'structured_output', 'effort',
        'input_tokens', 'output_tokens') if key in timing} for timing in record.get('stage_timings', [])]
    out['reviews'] = [{
        'attempt': review.get('attempt'), 'score': review.get('score'),
        'gates': {key: review.get('gates', {}).get(key, 'unknown') for key in GATES},
        'scores': {key: review.get('scores', {}).get(key) for key in DIMENSIONS},
    } for review in record.get('review_history', [])]
    # Never return topic, draft, analyst notes, issue reasons, raw failures or SDK errors.
    return out
