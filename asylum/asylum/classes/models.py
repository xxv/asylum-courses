from datetime import timedelta
from django.contrib.auth.models import User
from django.core import validators
from django.db import models
from django_eventbrite.models import Event as EBEvent
from djmoney.models.fields import MoneyField
from html2text import HTML2Text
from markdown_deux import markdown
from permission import add_permission_logic
from permission.logics import AuthorPermissionLogic
from permission.logics import CollaboratorsPermissionLogic
from phonenumber_field.modelfields import PhoneNumberField
from schedule.models import Event as CalEvent

class Person(models.Model):
    CONTACT_METHOD_TYPES = (
        ('email', 'email'),
        ('phone', 'phone'),
        ('sms', 'text message'),
    )
    name = models.CharField(max_length=200)
    asylum_name = models.CharField(max_length=200, help_text='their handle, if any. How the person wishes to be publicly addressed in association with the Asylum', blank=True, null=True)
    user = models.OneToOneField(User, null=True, blank=True)
    phone_number = PhoneNumberField(blank=True)
    prefered_contact_method = models.CharField(max_length=10, default='email', choices=CONTACT_METHOD_TYPES)
    emergency_contact = models.ForeignKey('Person', null=True, blank=True)

    @property
    def email(self):
        if self.user:
            return self.user.email
        return None

    @property
    def name_display(self):
        if self.asylum_name:
            return "{0} ({1})".format(self.asylum_name, self.name)
        return self.name

    def __str__(self):
        return self.name_display

    class Meta:
        verbose_name_plural='People'
        permissions = (
            ('change_user', 'Can change user association'),
        )

class Instructor(Person):
    PAYMENT_TYPES = (
        ('check', 'check'),
        ('deposit', 'direct deposit'),
    )

    EMPLOYMENT_TYPES = (
        ('w2', 'W2'),
        ('1099', '1099'),
    )
    bio = models.TextField(blank=True)
    photo = models.ImageField(blank=True)

    employment_type = models.CharField(max_length=10, choices=EMPLOYMENT_TYPES)
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPES)
    instructor_percentage = models.PositiveSmallIntegerField(default=50,
            help_text = 'The percentage of the ticket price paid to the instructor',
            validators = [
                validators.MaxValueValidator(100),
                ]
            )

    class Meta:
        permissions = (
            ('admin_instructor', 'Can change instructor administrative information'),
        )


class Room(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name
    class Meta:
        verbose_name_plural='Categories'

class AbsCourse(models.Model):
    MATERIAL_COST_INCLUDED_IN_TICKET = 'ticket'
    MATERIAL_COST_COLLECTED_BY_INSTRUCTOR = 'instructor'
    MATERIAL_COST_COLLECTION = (
        (MATERIAL_COST_INCLUDED_IN_TICKET, 'included in ticket price'),
        (MATERIAL_COST_COLLECTED_BY_INSTRUCTOR, 'collected by instructor at first class'),
    )
    name = models.CharField(max_length=255)
    blurb = models.TextField(help_text='This should be approximately one paragraph and will be displayed on the website.')
    description = models.TextField()
    instructors = models.ManyToManyField(Instructor)

    student_prerequisites = models.TextField('student prerequisites',
            default='Students must be at least 18 years of age.',
            null=True,
            blank=True,
            help_text='other courses, must be at least 18, specific tool training, etc.')

    requirements = models.TextField('classroom requirements',
            null=True,
            blank=True,
            help_text='a quiet room, a projector, the availability of certain tools, student-purchased consumables, etc.')
    room = models.ManyToManyField(Room, null=True)
    category = models.ManyToManyField(Category, null=True)
    number_of_meetings = models.PositiveSmallIntegerField('Meets',default=1, help_text='The number of times this course meets')
    instructor_hours = models.DecimalField('Instructor Hours', max_digits=4, decimal_places=2, default=0, help_text='The number of billed instructor hours')
    min_enrollment = models.PositiveSmallIntegerField('Minimum enrollment', default=0)
    max_enrollment = models.PositiveSmallIntegerField('Maximum enrollment')
    ticket_price = MoneyField(max_digits=6, decimal_places=2, default_currency='USD')
    material_cost = MoneyField(max_digits=6, decimal_places=2, default_currency='USD')
    material_cost_collection = models.CharField(max_length=10, choices = MATERIAL_COST_COLLECTION, null=True, blank=True)

    def instructor_names(self):
        return ", ".join(map(lambda i: i.name_display, self.instructors.all()))
    instructor_names.short_description='Instructors'

    def __str__(self):
        return self.name

    class Meta:
        abstract = True

class Course(AbsCourse):
    """A top-level, non-scheduled unit of instruction.

    This can be thought of as a template for a Session, which is an instance of
    a Course.
    """
    STATE_CURRENT = 'current'
    STATE_ARCHIVED = 'archived'
    STATES = (
        (STATE_CURRENT, 'Current'),
        (STATE_ARCHIVED, 'Archived'),
    )
    state = models.CharField(max_length=10, default=STATE_CURRENT, choices=STATES)
    def set_from_event(self, event):
        self.name = event.name
        h=HTML2Text()
        self.description = h.handle(event.description)
        self.max_enrollment = event.capacity
        if event.tickets.count() > 0:
            self.ticket_price = event.tickets.first().cost

    def create_session(self):
        session = Session()
        session.course = self
        for field in AbsCourse._meta.fields:
            setattr(session, field.name, getattr(self, field.name))
        session.save()
        for field in AbsCourse._meta.many_to_many:
            print(field)
            for obj in getattr(self, field.name).all():
                getattr(session, field.name).add(obj)

        session.save()
        return session

    def __str__(self):
        return self.name

    class Meta:
        permissions = (
            ('change_course_state', 'Change course approval state'),
        )

class Session(AbsCourse):
    STATE_CANCELED = 'canceled'
    STATE_DRAFT = 'draft'
    STATE_NEEDS_APPROVAL = 'needs_approval'
    STATE_PUBLIC = 'public'
    STATE_READY_TO_PUBLISH = 'ready'
    STATES = (
        (STATE_DRAFT, 'Draft'),
        (STATE_NEEDS_APPROVAL, 'Needs Approval'),
        (STATE_READY_TO_PUBLISH, 'Ready to Publish'),
        (STATE_PUBLIC, 'Public'),
        (STATE_CANCELED, 'Canceled'),
    )
    course = models.ForeignKey(Course, related_name='sessions')
    event = models.OneToOneField(EBEvent, null=True, blank=True)
    state = models.CharField(max_length=20, default=STATE_DRAFT, choices=STATES)
    calendar_event = models.OneToOneField(CalEvent, null=True)

    def eb_id(self):
        if not self.event:
            return None
        return self.event.eb_id
    eb_id.short_description = 'Eventbrite ID'

    def can_submit_for_approval(self, request):
        return (not request.user.has_perm('classes.change_session_state')) and self.state in (self.STATE_DRAFT,)

    def submit_for_approval(self, request):
        if self.can_submit_for_approval(request):
            self.state = self.STATE_NEEDS_APPROVAL
            self.save()

    def can_publish(self, request):
        has_perm = request.user.has_perm('classes.change_session_state')
        return has_perm and self.state in (self.STATE_DRAFT, self.STATE_NEEDS_APPROVAL, self.STATE_READY_TO_PUBLISH)

    def publish(self, request):
        # this needs to be imported here due to cyclic dependencies
        from asylum.classes.utils import publish_to_eb

        if self.can_publish(request):
            self.state = self.STATE_READY_TO_PUBLISH
            self.save()
            publish_to_eb(self)
            # publish to eventbrite here

    def can_cancel(self, request):
        has_perm = request.user.has_perm('classes.change_session_state')
        return has_perm and self.state in (self.STATE_DRAFT, self.STATE_NEEDS_APPROVAL, self.STATE_PUBLIC)

    def cancel(self, request):
        if self.can_cancel(request):
            self.state = self.STATE_CANCELED
            self.save()
            # unpublish from eventbrite here

    def set_from_event(self, event):
        self.name = event.name
        self.description = event.description
        if event.tickets:
            self.ticket_price = event.tickets[0].cost
        self.event = event

    def save(self):
        # twiddle the calendar here
        if self.calendar_event:
            self.calendar_event.title = self.name
            self.calendar_event.save()
        super(Session, self).save()

    def get_absolute_url(self):
        from django.core.urlresolvers import reverse
        return reverse('asylum.classes.views.session_item', args=[str(self.id)])

    def get_occurrences(self):
        cal = self.calendar_event
        if not cal:
            return None

        # We don't support infinite events for this
        if not cal.end_recurring_period and cal.rule:
            return None

        # the offsets here are to account for exact overlaps
        return cal.get_occurrences(cal.start - timedelta(1), (cal.end_recurring_period or cal.end) + timedelta(1))

    class Meta:
        permissions = (
            ('change_session_state', 'Change session approval state'),
        )

class TemplateText(models.Model):
    keyword = models.SlugField(unique=True, help_text='To use this, just place this keyword in curly braces (like so {{foo}}) in your text and it will be replaced when publishing.')
    text = models.TextField(help_text='This is the text that will be inserted')

    def text_as_html(self):
        return markdown(self.text)
    text_as_html.allow_tags=True
    text_as_html.short_description='Text'


# Instructors can edit their own profile
add_permission_logic(Instructor, AuthorPermissionLogic(field_name='user',
    any_permission=False,
    change_permission=True,
    delete_permission=False,
    ))

add_permission_logic(Course, CollaboratorsPermissionLogic(
    field_name='instructors__user',
    any_permission=False,
    change_permission=True,
    delete_permission=False,
    ))

add_permission_logic(Session, CollaboratorsPermissionLogic(
    field_name='instructors__user',
    any_permission=False,
    change_permission=True,
    delete_permission=True,
    ))

