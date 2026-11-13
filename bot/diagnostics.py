"""Read-only, access-scoped failure summaries; never expose model/SDK payloads."""
from editorial import authorized_post
from reviewer import DIMENSIONS, GATES
from platform_intelligence import PROFILES

NEXT_ACTIONS = {
    'storage_error': 'تعذّر قراءة أو حفظ البيانات. كلم صاحب البوت حتى يراجع التخزين.',
    'application_error': 'تعذّر إكمال المعالجة داخل البوت. يحتاج صاحب البوت يراجع التشخيص؛ السبب الدقيق بعده مو مؤكد.',
    'provider_search_unavailable': '⚠️ ما گدرنا ننفّذ البحث الموثّق بهذا المسار. Nous يگدر يكتب ويراجع، '
        'بس أداة البحث الحالية مرتبطة بـ Anthropic. صاحب البوت يحتاج يعالج وصول البحث؛ ما راح نخترع مصادر.',
    'provider_fallback_unconfigured': '⚠️ المزوّد البديل Nous مو مربوط بهذا التشغيل. صاحب البوت يحتاج يراجع إعداد NOUS_API_KEY.',
    'provider_credit_exhausted': '⚠️ رصيد خدمة الذكاء الاصطناعي غير كافي أو حد الإنفاق مستنفد حسب رد المزوّد. '
        'هاي مشكلة فوترة، مو مشكلة بالموضوع أو صيغة المحتوى. صاحب البوت يحتاج يراجع الرصيد وحدود الصرف، وبعدها تگدر تعيد المحاولة.',
    'provider_billing_required': '⚠️ خدمة الذكاء الاصطناعي تطلب معالجة الفوترة. صاحب البوت يحتاج يراجع إعدادات الدفع قبل إعادة المحاولة.',
    'provider_authentication': '⚠️ خدمة الذكاء الاصطناعي رفضت مفتاح الوصول. صاحب البوت يحتاج يراجع المفتاح بالإعدادات؛ تغيير الموضوع ما يحل المشكلة.',
    'provider_permission': '⚠️ الحساب ما عنده صلاحية للطلب أو الموديل. صاحب البوت يحتاج يراجع صلاحيات خدمة الذكاء الاصطناعي.',
    'provider_model_unavailable': '⚠️ الموديل المحدد مو متاح للحساب. صاحب البوت يحتاج يراجع اسم الموديل وإمكانية الوصول إله.',
    'provider_rate_limit': '⚠️ وصلنا لحد الطلبات المؤقت بخدمة الذكاء الاصطناعي. جرّب بعد شوية؛ هذا مو تأكيد إن الرصيد خلص.',
    'provider_request_rejected': '⚠️ خدمة الذكاء الاصطناعي رفضت إعدادات الطلب. صاحب البوت يحتاج يراجع التشخيص؛ ما عدنا تأكيد إن السبب هو الرصيد.',
    'provider_connection': '⚠️ تعذّر الاتصال بخدمة الذكاء الاصطناعي. جرّب لاحقاً؛ هذا مو تأكيد إن الرصيد خلص.',
    'provider_unavailable': '⚠️ خدمة الذكاء الاصطناعي مو متاحة حالياً. جرّب بعد شوية.',
    'routing_unavailable': 'تعذّر تحديد إذا الطلب يحتاج بحث أو إعادة صياغة. جرّب بعد شوية أو وضّح طلبك.',
    'research_unsupported': 'ما لگينا دليل موثوق وكافي يدعم الموضوع. دز مصدر رسمي أو وضّح الادعاء حتى نراجعه قبل الكتابة.',
    'research_unavailable': 'البحث ما اكتمل أو ما رجّع مصادر قابلة للتحقق، لذلك وقفنا قبل الكتابة. جرّب لاحقاً أو راجع إعدادات البحث.',
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


CATEGORY_LABELS = {
    'content': '📝 المحتوى المقترح لهالموضوع ما اجتاز المراجعة.',
    'model': '🤖 مشكلة بخدمة الذكاء الاصطناعي أو جواب النموذج.',
    'application': '⚙️ مشكلة تقنية بالتطبيق أو إعداداته.',
    'limit': '⏳ توقفت المحاولة لأن وصلت للحد المسموح.',
    'unknown': '❓ المحاولة ما اكتملت؛ السبب يحتاج تشخيص.',
}


def failure_category(record: dict) -> str:
    """Describe the observed failure area, never infer a coding defect from a rejection."""
    code = failure_code(record)
    if code == 'accepted':
        return 'accepted'
    if code in {'creative_threshold', 'critical_gate', 'revision_no_improvement',
                'verified_fact_missing', 'research_unsupported', 'missing_information'}:
        return 'content'
    if code in {'storage_error', 'application_error', 'unknown_pricing',
                'provider_fallback_unconfigured'}:
        return 'application'
    if code == 'resource_limit':
        return 'limit'
    if (code.startswith('provider_') or code.startswith('review_')
            or code.startswith(('writer_', 'revision_'))
            or code in {'invalid_structure', 'invalid_review_json', 'duplicate_review_key',
                        'oversized_review'} or code.startswith('invalid_review_')):
        return 'model'
    # Routing, research and generic parsing failures have multiple possible causes.
    return 'unknown'


def safe_structure(record):
    from quality import FIELDS
    allowed = {name for names in FIELDS.values() for name in names}
    data = record.get('structure_details') or {}
    if not isinstance(data, dict):
        return {}
    out = {key: [name for name in data[key] if isinstance(name, str) and name in allowed][:20]
           for key in ('expected', 'present', 'missing', 'empty', 'duplicates')
           if isinstance(data.get(key), list)}
    out.update({key: data[key] for key in ('order_valid', 'unexpected_fields')
                if type(data.get(key)) is bool})
    return out


def failure_summary(record: dict) -> str:
    code = failure_code(record)
    message = NEXT_ACTIONS.get(code, 'المحاولة ما اكتملت. نحتاج نشوف التشخيص حتى نحدد السبب.')
    category = failure_category(record)
    if category in CATEGORY_LABELS:
        message = CATEGORY_LABELS[category] + '\n' + message
    if code == 'invalid_structure':
        details = safe_structure(record)
        for key, label in (('missing', 'حقول ناقصة'), ('empty', 'حقول فارغة'),
                           ('duplicates', 'حقول مكررة')):
            if details.get(key):
                message += '\n' + label + ': ' + ', '.join(details[key])
        if details.get('order_valid') is False:
            message += '\nترتيب الحقول غير مطابق. المطلوب: ' + ' → '.join(details.get('expected', []))
    if code != 'critical_gate':
        if any(t.get('fallback_status') == 'not_configured' for t in record.get('stage_timings', [])):
            message += '\nالبديل Nous مو مربوط بهذا التشغيل. صاحب البوت يحتاج يراجع إعداد NOUS_API_KEY.'
        return message
    labels = {
        'factual_integrity': 'دقة المعلومات',
        'safety': 'سلامة المحتوى',
        'topic_preservation': 'الحفاظ على الموضوع',
        'voice_preservation': 'الحفاظ على النبرة',
        'format_identity': 'مطابقة نوع المحتوى',
    }
    history = record.get('review_history') or []
    gates = history[-1].get('gates', {}) if history else {}
    if not gates:
        gates = dict(item.split(': ', 1) for item in record.get('failures', [])
                     if isinstance(item, str) and item in {
                         f'{gate}: {state}' for gate in GATES for state in ('fail', 'uncertain')})
    reasons = [labels[gate] + (': المراجع ما گدر يتأكد منها' if state == 'uncertain'
                             else ': ما اجتازت الفحص')
               for gate, state in gates.items()
               if gate in labels and state in ('fail', 'uncertain')]
    if not reasons:
        return message
    message += '\nسبب الحجب: ' + '؛ '.join(reasons) + '.'
    if gates.get('factual_integrity') == 'uncertain':
        message += '\nهذا مو إثبات إن المعلومات غلط؛ نحتاج مصدر موثوق أو توضيح للادعاءات قبل عرضها.'
    return message


def failure_message(record: dict, pid: str) -> str:
    message = failure_summary(record)
    return message + '\nرقم المراجعة: ' + pid + '\nللتشخيص: /diagnose ' + pid + '\nلتغيير الاختيارات: /format'


def diagnostic_report(pid: str, actor: int) -> dict:
    record = authorized_post(pid, actor)
    out = {key: record[key] for key in (
        'id', 'quality_status', 'format', 'story_mode', 'story_intent', 'structure_id', 'feature_id', 'strategy_id',
        'transport_normalized', 'manual_review_ready', 'delivery_status', 'failure_stage', 'calls', 'attempts', 'usage_known',
        'elapsed_ms', 'input_tokens', 'output_tokens', 'cost_usd') if key in record}
    out['planning'] = {key: record.get('planning', {}).get(key)
                       for key in ('purpose','framework','fallback','fallback_reason')
                       if key in record.get('planning', {})}
    research = record.get('research') or {}
    out['routing'] = {key: record.get('routing', {}).get(key) for key in (
        'action', 'reason', 'factual_claims', 'needs_numbers', 'official_sources_required', 'fallback')
        if key in record.get('routing', {})}
    out['research'] = {'status': research.get('status', 'not_run'),
                       'retrieved_at': research.get('retrieved_at'),
                       'search_requests': research.get('search_requests', 0),
                       'source_count': len(research.get('sources') or []),
                       'source_urls': [source['url'] for source in research.get('sources', [])]}
    out['failure_code'] = failure_code(record)
    out['failure_category'] = failure_category(record)
    out['validation_checks'] = validation_checks(record)
    out['structure_details'] = safe_structure(record)
    out['next_action'] = failure_summary(record)
    out['build'] = {key: record.get('build', {}).get(key, 'unknown')
                    for key in ('commit', 'source', 'workflow')}
    out['stages'] = [{key: timing[key] for key in (
        'stage', 'status', 'elapsed_ms', 'output_chars', 'truncated', 'refused', 'usage_known',
        'provider', 'model', 'stop_reason', 'thinking_blocks', 'structured_output', 'effort',
        'input_tokens', 'output_tokens', 'error_code', 'http_status', 'fallback_reason', 'fallback_status') if key in timing} for timing in record.get('stage_timings', [])]
    out['reviews'] = [{
        'attempt': review.get('attempt'), 'score': review.get('score'),
        'gates': {key: review.get('gates', {}).get(key, 'unknown') for key in GATES},
        'scores': {key: review.get('scores', {}).get(key) for key in DIMENSIONS},
    } for review in record.get('review_history', [])]
    # Never return topic, draft, analyst notes, issue reasons, raw failures or SDK errors.
    return out
