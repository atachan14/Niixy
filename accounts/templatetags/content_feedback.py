from django import template
from accounts.content_lists import board_can_view, feedback_context
from interfaces.models import Interface
register = template.Library()


@register.inclusion_tag('shared/content_feedback.html', takes_context=True)
def content_feedback(context, target, kind):
    request = context['request']
    available = board_can_view(target, request.user) if kind == 'board' else target.status == Interface.ACTIVE and bool(target.current_version_id)
    if not available:
        return {}
    return {**feedback_context(kind, target, request.user), 'request': request, 'csrf_token': context.get('csrf_token')}
