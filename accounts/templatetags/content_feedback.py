from django import template
from accounts.content_lists import board_can_view, feedback_context, module_is_public, conversation_can_view, conversation_is_muted
register = template.Library()


@register.inclusion_tag('shared/content_feedback.html', takes_context=True)
def content_feedback(context, target, kind):
    request = context['request']
    available = (conversation_can_view(kind, target, request.user) and not conversation_is_muted(kind, target, request.user)) if kind in {'thread', 'response'} else board_can_view(target, request.user) if kind == 'board' else module_is_public(kind, target)
    if not available:
        return {}
    return {**feedback_context(kind, target, request.user), 'compact': kind in {'thread', 'response'}, 'request': request, 'csrf_token': context.get('csrf_token')}
