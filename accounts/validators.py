from django.core import validators
from django.utils.translation import gettext as _

class UnicodeEmailValidator(validators.RegexValidator):
    regex = r"^[\w.@+-]+\Z"
    message = _(
        "Enter a valid email."
    )
    flags = 0