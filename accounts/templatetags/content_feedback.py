from django import template
from accounts.content_lists import board_can_view, feedback_context, module_is_public
register = template.Library()


@register.inclusion_tag('shared/content_feedback.html', takes_context=True)
def content_feedback(context, target, kind):
    request = context['request']
    available = board_can_view(target, request.user) if kind == 'board' else module_is_public(kind, target)
    if not available:
        return {}
    return {**feedback_context(kind, target, request.user), 'request': request, 'csrf_token': context.get('csrf_token')}
