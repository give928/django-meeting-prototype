from django import template

register = template.Library()

@register.simple_tag
def querystring_without_page(request, prefix=''):
    qs = request.GET.copy()
    qs.pop('page', None)
    encoded = qs.urlencode()
    return f"{prefix}{encoded}" if encoded else ""