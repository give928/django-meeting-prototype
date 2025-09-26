from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin

from .models import User, Department


class DepartmentAdmin(DraggableMPTTAdmin):
    list_display = (
        'tree_actions',
        'indented_title',
        'group',
    )
    # prepopulated_fields = {'group.name': ('group',)}
    mptt_level_indent = 20

admin.site.register(User)
admin.site.register(Department, DepartmentAdmin)