from .models import Course, Instructor, Person, Session
from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.db import models
from djcourses import admin as courses
from pagedown.widgets import AdminPagedownWidget

class ObjPermModelAdmin(admin.ModelAdmin):
    def has_change_permission(self, request, obj=None):
        opts = self.opts
        codename = get_permission_codename('change', opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename), obj)

class InstructorAdmin(ObjPermModelAdmin):
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    search_fields = ['first_name', 'last_name', 'bio', 'phone_number']

class SessionAdmin(ObjPermModelAdmin):
    search_fields = ['name', 'description']
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    readonly_fields = ('event',)

class CourseAdmin(ObjPermModelAdmin):
    self_edit_allowed = ()
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    search_fields = ['name', 'description']

class PersonAdmin(ObjPermModelAdmin):
    search_fields = ['first_name', 'last_name', 'phone_number']

admin.site.register(Course, CourseAdmin)
admin.site.register(Session, SessionAdmin)
admin.site.register(Instructor, InstructorAdmin)
admin.site.register(Person, PersonAdmin)
