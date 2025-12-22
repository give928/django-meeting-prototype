from django import template
import markdown
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='markdown_to_html')
def markdown_to_html(value):
    if value:
        html = markdown.markdown(value)
        return mark_safe(html)
    return ""