from django_object_actions import DjangoObjectActions
from .models import Course, Instructor, Person, Session, Room
from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.db import models
import django_eventbrite
from pagedown.widgets import AdminPagedownWidget
from django.shortcuts import redirect

class ObjPermModelAdmin(admin.ModelAdmin):
    """Admin for models that use object-based permissions

    Also supports permissioned fields, which takes a tuple/list of 2-tuples
    that makes fields readonly unless the requesting user has the given
    permission:

    permissioned_fields = (
        ('classes.change_user', ('user','other_field')),
        )
    """
    permissioned_fields = ()
    def get_readonly_fields(self, request, obj=None):
        ro = list(super(admin.ModelAdmin, self).get_readonly_fields(request, obj))
        for entry in self.permissioned_fields:
            if not request.user.has_perm(entry[0]):
                for field in entry[1]:
                    ro.append(field)
        return ro
    def has_change_permission(self, request, obj=None):
        opts = self.opts
        codename = get_permission_codename('change', opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename), obj)


@admin.register(Person)
class PersonAdmin(ObjPermModelAdmin):
    search_fields = ['first_name', 'last_name', 'phone_number']
    permissioned_fields = (
        ('classes.change_user', ('user',)),
        )

@admin.register(Instructor)
class InstructorAdmin(PersonAdmin):
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    search_fields = ['first_name', 'last_name', 'bio', 'phone_number']
    admin_fields = (
                'employment_type',
                'payment_type',
                'instructor_percentage',
                'asylum_percentage',
                'user',
                'emergency_contact',
                )
    permissioned_fields = (
            ('classes.admin_instructor', admin_fields),
        )

    def get_fieldsets(self, request, obj=None):
        classes = []
        if not request.user.has_perm('classes.admin_instructor'):
            classes.append('collapse')
        admin_fields = ('Administrative Options', {
            'classes': classes,
            'fields': self.admin_fields
            }
        )

        other_fields = self.get_fields(request, obj)
        for admin_field in admin_fields[1]['fields']:
            other_fields.remove(admin_field)
        fieldsets = (
            (None, {
                'fields': other_fields,
            }),
            admin_fields
            )
        return fieldsets

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }

@admin.register(Session)
class SessionAdmin(ObjPermModelAdmin):
    search_fields = ['name', 'description']
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    readonly_fields = ('event',)

@admin.register(Course)
class CourseAdmin(DjangoObjectActions, ObjPermModelAdmin):
    self_edit_allowed = ()
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    search_fields = ['name', 'description']
    def make_session(self, request, obj):
        session=obj.create_session()
        return redirect('/admin/classes/session/%d/' % session.id)
    make_session.label='Create Session'
    make_session.short_description='Create session of course'
    objectactions = ('make_session',)

def make_course(modeladmin, request, queryset):
    for event in queryset:
        c=Course()
        c.set_from_event(event)
        c.save()

make_course.description='Convert Event into a Course'

# Override the django_eventbrite model to allow for course conversion.
admin.site.unregister(django_eventbrite.models.Event)

@admin.register(django_eventbrite.models.Event)
class EventAdmin(django_eventbrite.admin.EventAdmin):
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    actions=[make_course]

