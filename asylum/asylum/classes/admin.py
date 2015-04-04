from .models import Course, Instructor, Person, Session, Room
from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.db import models
from django.shortcuts import redirect
from django.utils.module_loading import autodiscover_modules
from django_eventbrite import admin as eb_admin
from django_object_actions import DjangoObjectActions
from pagedown.widgets import AdminPagedownWidget
import django_eventbrite

class AsylumAdminSite(admin.AdminSite):
    site_header = "Artisan's Asylum Courses"

admin_site = AsylumAdminSite()

def steal_registrations_from_stock_admin_site():
    """Steals all the registrations from the admin site and reregisters them here

    Lots of things register with the standard admin page automatically when the
    autodiscovery is called. This is great ... except when using a custom
    AdminSite. There doesn't seem to be a clean way to do this The Right Way,
    so this hack is in place. This lets them all do their registration thing,
    then unregisters them from the stock admin and re-registers them here.

    """
    autodiscover_modules('admin')

    for k,v in admin.site._registry.copy().iteritems():
        try:
            admin.site.unregister(k)
        except admin.sites.NotRegistered:
            pass # Alright. We were stealing them anyhow
        try:
            admin_site.register(k,type(v))
        except admin.sites.AlreadyRegistered:
            pass # Also alright. No honor amongst thieves

steal_registrations_from_stock_admin_site()

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


@admin.register(Person, site=admin_site)
class PersonAdmin(ObjPermModelAdmin):
    search_fields = (
        'first_name',
        'last_name',
        'phone_number',
        )
    permissioned_fields = (
            ('classes.change_user', ('user',)),
        )

@admin.register(Instructor, site=admin_site)
class InstructorAdmin(PersonAdmin):
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    search_fields = (
        'first_name',
        'last_name',
        'bio',
        'phone_number',
        'user__username',
        'user__email'
        )
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

@admin.register(Room, site=admin_site)
class RoomAdmin(admin.ModelAdmin):
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }

class AbsCourseAdmin(ObjPermModelAdmin):
    list_display = ('name', 'instructor_names')
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    search_fields = (
        'name',
        'description',
        'instructors__first_name',
        'instructors__last_name',
        )

@admin.register(Session, site=admin_site)
class SessionAdmin(AbsCourseAdmin):
    readonly_fields = ('event',)
    list_display = (
        'name',
        'instructor_names',
        'eb_id',
        )

@admin.register(Course, site=admin_site)
class CourseAdmin(DjangoObjectActions, AbsCourseAdmin):
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
try:
    admin.site.unregister(django_eventbrite.models.Event)
except admin.sites.NotRegistered:
    pass # that's OK

try:
    admin_site.unregister(django_eventbrite.models.Event)
except admin.sites.NotRegistered:
    pass # that's OK

@admin.register(django_eventbrite.models.Event, site=admin_site)
class EventAdmin(eb_admin.EventAdmin):
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    actions=[make_course]
