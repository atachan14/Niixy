import uuid

from django.db import IntegrityError, transaction


def submission_id_from(value):
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return uuid.uuid4()


def run_once(model, submission_id, operation):
    """Run a create operation once and return its existing result on retry."""
    try:
        with transaction.atomic():
            return operation(), True
    except IntegrityError:
        existing = model.objects.filter(submission_id=submission_id).first()
        if existing is None:
            raise
        return existing, False
