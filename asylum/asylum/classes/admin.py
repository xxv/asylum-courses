from .models import Course, Instructor, Person, Session, Room, TemplateText
from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.db import models
from django.shortcuts import redirect
from django.utils.module_loading import autodiscover_modules
from django_eventbrite import admin as eb_admin
from django_object_actions import DjangoObjectActions
from pagedown.widgets import AdminPagedownWidget
import django_eventbrite
from django_eventbrite.utils import load_event_attendees

class AsylumAdminSite(admin.AdminSite):
    site_header = "Artisan's Asylum Courses"
    site_title = "Asylum Courses"
    index_title = "Course Administration"

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

    for k,v in admin.site._registry.copy().items():
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
        'name',
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
    list_display = (
        'name',
        'email',
        'phone_number',
    )
    search_fields = (
        'name',
        'bio',
        'phone_number',
        'user__username',
        'user__email'
        )
    admin_fields = (
                'employment_type',
                'payment_type',
                'instructor_percentage',
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
        'instructors__name',
        )

@admin.register(Session, site=admin_site)
class SessionAdmin(DjangoObjectActions, AbsCourseAdmin):
    readonly_fields = ('event',)
    permissioned_fields = (
        ('classes.change_session_state', ('state',)),
    )
    list_display = (
        'name',
        'instructor_names',
        'eb_id',
        'state',
    )
    objectactions = ('submit_for_approval', 'publish', 'cancel')
    def get_object_actions(self, request, context, **kwargs):
        objectactions = []
        if 'original' in context:
            obj = context['original']
            if obj.can_submit_for_approval(request):
                objectactions.append('submit_for_approval')
            if obj.can_publish(request):
                objectactions.append('publish')
            if obj.can_cancel(request):
                objectactions.append('cancel')
        return objectactions

    def submit_for_approval(self, request, obj):
        obj.submit_for_approval(request)
        return redirect('admin:classes_session_changelist')
    submit_for_approval.label='Submit for Approval'
    submit_for_approval.short_description = 'Submit this session to be approved by Asylum staff'

    def publish(self, request, obj):
        if request.user.has_perm('classes.change_session_state'):
            obj.publish(request)
            return redirect('admin:classes_session_changelist')
    publish.label = 'Publish'
    publish.short_description = 'Publish on site and create Eventbrite event'

    def cancel(self, request, obj):
        if request.user.has_perm('classes.change_session_state'):
            obj.cancel(request)
            return redirect('admin:classes_session_changelist')
    cancel.label = 'Cancel Session'
    cancel.short_description = 'Remove from site and cancel Eventbrite event'

@admin.register(Course, site=admin_site)
class CourseAdmin(DjangoObjectActions, AbsCourseAdmin):
    permissioned_fields = (
        ('classes.change_course_state', ('state',)),
    )
    def make_session(self, request, obj):
        session=obj.create_session()
        return redirect('admin:classes_session_change', session.id)
    make_session.label='Create Session'
    make_session.short_description='Create session of course'
    objectactions = ('make_session',)

def make_courses(modeladmin, request, queryset):
    for event in queryset:
        c=Course()
        c.set_from_event(event)
        c.save()

make_courses.description='Convert Event into a Course'

@admin.register(TemplateText, site=admin_site)
class TemplateTextAdmin(admin.ModelAdmin):
    list_display = (
        'keyword',
        'text_as_html',
    )
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }

# Override the django_eventbrite model to allow for course conversion.
try:
    admin.site.unregister(django_eventbrite.models.Event)
except admin.sites.NotRegistered:
    pass # that's OK

try:
    admin_site.unregister(django_eventbrite.models.Event)
except admin.sites.NotRegistered:
    pass # that's OK


from django.contrib import admin
from django.contrib.admin.util import flatten_fieldsets

class ReadonlyAdminMixin(object):
    def get_readonly_fields(self, request, obj=None):
        if self.declared_fieldsets:
            return flatten_fieldsets(self.declared_fieldsets)
        else:
            return list(set(
                [field.name for field in self.opts.local_fields] +
                [field.name for field in self.opts.local_many_to_many]
            ))


class AttendeeInline(ReadonlyAdminMixin, admin.StackedInline):
    model = django_eventbrite.models.Attendee
    readonly_fields = (
        'eb_id',
        'event',
    )
@admin.register(django_eventbrite.models.Event, site=admin_site)
class EventAdmin(ReadonlyAdminMixin, DjangoObjectActions, eb_admin.EventAdmin):
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    actions=[make_courses]
    inlines=[AttendeeInline]
    def make_course(self, request, obj):
        c=Course()
        c.set_from_event(obj)
        c.save()
        return redirect('admin:classes_course_change', c.id)
    make_course.label = "Create Course"
    make_course.short_description = "Convert this event into a new Course"

    def load_attendees(self, request, obj):
        load_event_attendees(obj.eb_id)
        return redirect('admin:django_eventbrite_event_change', obj.id)
    load_attendees.label = "Load Attendees"
    load_attendees.short_description = "Load the attendees from Eventbrite"

    objectactions = ('make_course','load_attendees')
