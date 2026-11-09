"""A below-threshold draft can be shown only after a fresh all-pass gate review.

The user authorized labeled manual-review drafts. This never upgrades quality_status
or supplies an approval/publication path. Recheck native structure at delivery too.
"""
import hashlib
import json
import math
from quality import Checked
from reviewer import GATES


def artifact_fingerprint(checked: Checked) -> str:
    payload=json.dumps({'text':checked.text,'production':checked.production_plan},
                       ensure_ascii=False,sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def manual_review_eligible(checked: Checked) -> bool:
    if (checked.status != 'needs_review' or checked.refused or not checked.text
            or checked.failure_code not in ('creative_threshold','revision_no_improvement')
            or not checked.review_history or not checked.reviewed_artifact_hash
            or 'creative thresholds not met' not in checked.failures
            or any(reason not in ('creative thresholds not met','revision did not improve score')
                   for reason in checked.failures)):
        return False
    latest=checked.review_history[-1]
    gates=latest.get('gates') if isinstance(latest,dict) else None
    score=latest.get('score') if isinstance(latest,dict) else None
    if type(score) not in (int,float) or not math.isfinite(score) or not 0 <= score <= 10:
        return False
    if not isinstance(gates,dict) or set(gates) != set(GATES) or any(value != 'pass' for value in gates.values()):
        return False
    try:
        return checked.reviewed_artifact_hash == artifact_fingerprint(checked)
    except (ValueError,TypeError):
        return False


def manual_review_warning(checked: Checked) -> str:
    score=checked.review_history[-1]['score']
    return (f'⚠️ مسودة للمراجعة اليدوية — غير معتمدة. التقييم الإبداعي: {score:.2f}/10.\n'
            'راجع النص وعدّله قبل النشر؛ ما اجتاز كل معايير الجودة الإبداعية.')
