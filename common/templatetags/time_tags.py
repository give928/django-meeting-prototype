from django import template

register = template.Library()

@register.filter(name="ms_to_hms")
def ms_to_hms(value):
    try:
        if not value:
            return "00:00:00"

        ms = int(value)
        if ms <= 0:
            return "00:00:00"

        total_seconds = ms // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception:
        return "00:00:00"