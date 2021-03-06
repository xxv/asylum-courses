from .models import Course, Instructor, Person, Session, Room, TemplateText, Category
from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.db import models
from django.shortcuts import redirect
from django.utils.module_loading import autodiscover_modules
from django_eventbrite import admin as eb_admin
from django_eventbrite.utils import load_event_attendees, load_event
from django_object_actions import DjangoObjectActions
from html2text import HTML2Text
from import_export import resources, fields
from import_export.admin import ExportMixin
from pagedown.widgets import AdminPagedownWidget
import django_eventbrite

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
        'asylum_name',
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
        '__str__',
        'email',
        'phone_number',
    )
    search_fields = (
        'name',
        'asylum_name',
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
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    def instructor_names(self, obj):
        return obj.instructor_names()
    instructor_names.short_description='Instructors'
    instructor_names.admin_order_field='instructors__name'

    def categories(self, obj):
        return ", ".join(map(lambda c: c.name, obj.category.all()))
    categories.admin_order_field='category__name'

    def rooms(self, obj):
        return ", ".join(map(lambda r: r.name, obj.room.all()))
    rooms.admin_order_field='room__name'


def load_session_attendees_queryset(modeladmin, request, sessions):
    for session in sessions:
        if not session.event:
            continue
        print("Loading event {0}".format(session.event.eb_id))
        load_event_attendees(session.event.eb_id)
load_session_attendees_queryset.short_description='Update Attendees'


@admin.register(Session, site=admin_site)
class SessionAdmin(DjangoObjectActions, AbsCourseAdmin):
    actions = (
        load_session_attendees_queryset,
    )
    permissioned_fields = (
        ('classes.change_session_state', ('state',)),
    )
    list_display = (
        'name',
        'instructor_names',
        'start_date',
        'end_date',
        'eb_id',
        'state',
        'ticket_sales',
        'eventbrite_fees',
        '_min_enrollment',
        '_max_enrollment',
        'quantity_sold',
        'quantity_refunded',
        'quantity_canceled',
    )
    search_fields = (
        'name',
        'description',
        'blurb',
        'instructors__name',
        'instructors__asylum_name',
        'category__name',
        'room__name',
    )
    list_filter = (
        'state',
        'calendar_event__start',
    )

    objectactions = ('submit_for_approval', 'publish', 'cancel')

    def end_date(self, obj):
        """The end time of the last meeting of this session.

        This is computed and could potentially be quite expensive for things
        that repeat many times. In reality, that should be pretty unusual.
        However the database-based sort can't use this info, so it filters on
        the end recurring period, which may be inaccurate. Still, it's better
        than not being able to sort at all.
        """
        occurrences = obj.get_occurrences()
        if not occurrences:
           return None
        return occurrences[-1].end
    end_date.admin_order_field='calendar_event__end_recurring_period'

    def _max_enrollment(self, obj):
        return obj.max_enrollment
    _max_enrollment.short_description='Cap'
    _max_enrollment.admin_order_field='max_enrollment'

    def _min_enrollment(self, obj):
        return obj.min_enrollment
    _min_enrollment.short_description='Min'
    _min_enrollment.admin_order_field='min_enrollment'

    def eventbrite_fees(self, obj):
        if not obj.event:
            return None
        return obj.event.eventbrite_fees()
    eventbrite_fees.short_description='EB fees'

    def ticket_sales(self, obj):
        if not obj.event:
            return None
        return obj.event.ticket_sales()
    ticket_sales.short_description='Sales'

    def quantity_sold(self, obj):
        if not obj.event:
            return 0
        return obj.event.quantity_sold()
    quantity_sold.short_description='Sold'

    def quantity_refunded(self, obj):
        if not obj.event:
            return 0
        return obj.event.quantity_refunded()
    quantity_refunded.short_description='Refunds'

    def quantity_canceled(self, obj):
        if not obj.event:
            return 0
        return obj.event.quantity_canceled()
    quantity_canceled.short_description='Cancels'

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

    def start_date(self, obj):
        if not obj.calendar_event:
            return None
        return obj.calendar_event.start
    start_date.admin_order_field='calendar_event__start'

    def number_of_sessions(self, obj):
        return len(obj.get_occurrences() or [])
    number_of_sessions.short_description='Scheduled sessions'

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
    list_filter = (
        'state',
    )
    list_display = (
        'name',
        'instructor_names',
        'categories',
        'rooms',
        'number_of_meetings',
        'instructor_hours',
        'ticket_price',
        'min_enrollment',
        'max_enrollment',
        )
    search_fields = (
        'name',
        'description',
        'blurb',
        'instructors__name',
        'instructors__asylum_name',
        'category__name',
        'room__name',
        )

    def make_session(self, request, obj):
        session=obj.create_session()
        return redirect('admin:classes_session_change', session.id)
    make_session.label='Create Session'
    make_session.short_description='Create session of course'
    objectactions = ('make_session',)

@admin.register(TemplateText, site=admin_site)
class TemplateTextAdmin(admin.ModelAdmin):
    list_display = (
        'keyword',
        'text_as_html',
    )
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }

@admin.register(Category, site=admin_site)
class CategoryAdmin(admin.ModelAdmin):
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

def make_courses(modeladmin, request, queryset):
    for event in queryset:
        modeladmin.make_course(request, event)
make_courses.short_description='Convert Event into a Course'

def load_attendees_queryset(modeladmin, request, events):
    for event in events:
        load_event_attendees(event.eb_id)
load_attendees_queryset.short_description='Load Attendees'

def load_events_queryset(modeladmin, request, events):
    for event in events:
        load_event(event.eb_id)
load_events_queryset.short_description='Reload Events'

import csv
from django.http import HttpResponse

def export_csv(modeladmin, request, queryset):
   response = HttpResponse(content_type='text/csv')
   response['Content-Disposition'] = 'attachment; filename="events-export.csv"'
   writer = csv.writer(response)
   for event in queryset:
       writer

class EventResource(resources.ModelResource):
    quantity_sold = fields.Field()
    quantity_refunded = fields.Field()
    quantity_canceled = fields.Field()
    ticket_sales = fields.Field()
    h=HTML2Text()
    def dehydrate_quantity_sold(self, event):
        return event.quantity_sold()
    def dehydrate_description(self, event):
        return self.h.handle(event.description)
    def dehydrate_quantity_refunded(self, event):
        return event.quantity_refunded()
    def dehydrate_quantity_canceled(self, event):
        return event.quantity_canceled()
    def dehydrate_ticket_sales(self, event):
        return event.ticket_sales()
    class Meta:
        model = django_eventbrite.models.Event

@admin.register(django_eventbrite.models.Event, site=admin_site)
class EventAdmin(ExportMixin, ReadonlyAdminMixin, DjangoObjectActions, eb_admin.EventAdmin):
    formfield_overrides = {
            models.TextField: {'widget': AdminPagedownWidget },
    }
    actions=[make_courses, load_attendees_queryset, load_events_queryset]
    inlines=[AttendeeInline]
    resource_class = EventResource
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
