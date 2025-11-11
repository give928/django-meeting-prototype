from django import template

register = template.Library()

@register.filter
def exclusive_range(start, end):
    return range(start, end)

@register.filter
def inclusive_range(start, end):
    return range(start, end + 1)