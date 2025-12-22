from django.db import models


class BaseCode(models.TextChoices):
    @classmethod
    def find_by_value(cls, value):
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"invalid code value: {value}")

    @classmethod
    def find_by_label(cls, label):
        for member in cls:
            if member.label == label:
                return member
        raise ValueError(f"invalid code label: {label}")