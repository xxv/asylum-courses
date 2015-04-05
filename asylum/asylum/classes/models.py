from django.contrib.auth.models import User
from django.core import validators
from django.db import models
from django_eventbrite.models import Event
from djmoney.models.fields import MoneyField
from permission import add_permission_logic
from permission.logics import AuthorPermissionLogic
from permission.logics import CollaboratorsPermissionLogic
from phonenumber_field.modelfields import PhoneNumberField
from html2text import HTML2Text
from markdown_deux import markdown

class Person(models.Model):
    CONTACT_METHOD_TYPES = (
        ('email', 'email'),
        ('phone', 'phone'),
        ('sms', 'text message'),
        )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    user = models.OneToOneField(User, null=True, blank=True)
    phone_number = PhoneNumberField(blank=True)
    prefered_contact_method = models.CharField(max_length=10, default='email', choices=CONTACT_METHOD_TYPES)
    emergency_contact = models.ForeignKey('Person', null=True, blank=True)

    def name(self):
        return ' '.join((self.first_name, self.last_name,)).strip()

    def __str__(self):
        return self.name()
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
    def email(self):
        if self.user:
            return self.user.email
        return None

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

class AbsCourse(models.Model):
    MATERIAL_COST_COLLECTION = (
        ('ticket', 'included in ticket price'),
        ('instructor', 'collected by instructor at first class'),
    )
    name = models.CharField(max_length=255)
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
    number_of_meetings = models.PositiveSmallIntegerField(default=1)
    min_enrollment = models.PositiveSmallIntegerField('Minimum enrollment', default=0)
    max_enrollment = models.PositiveSmallIntegerField('Maximum enrollment')
    ticket_price = MoneyField(max_digits=6, decimal_places=2, default_currency='USD')
    material_cost = MoneyField(max_digits=6, decimal_places=2, default_currency='USD')
    material_cost_collection = models.CharField(max_length=10, choices = MATERIAL_COST_COLLECTION, null=True, blank=True)

    def instructor_names(self):
        return ", ".join(map(lambda i: i.name(), self.instructors.all()))
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
        if event.tickets:
            self.ticket_price = event.tickets.all()[0].cost

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
    STATE_DRAFT = 'draft'
    STATE_UNAPPROVED = 'unapproved'
    STATE_PUBLIC = 'public'
    STATE_CANCELED = 'canceled'
    STATES = (
        (STATE_DRAFT, 'Draft'),
        (STATE_UNAPPROVED, 'Needs Approval'),
        (STATE_PUBLIC, 'Public'),
        (STATE_CANCELED, 'Canceled'),
    )
    course = models.ForeignKey(Course)
    event = models.OneToOneField(Event, null=True)
    state = models.CharField(max_length=10, default=STATE_DRAFT, choices=STATES)

    def eb_id(self):
        if not self.event:
            return None
        return self.event.eb_id
    eb_id.short_description = 'Eventbrite ID'

    def can_submit_for_approval(self, request):
        return (not request.user.has_perm('classes.change_session_state')) and self.state in (self.STATE_DRAFT,)

    def submit_for_approval(self, request):
        if self.can_submit_for_approval(request):
            self.state = self.STATE_UNAPPROVED
            self.save()

    def can_publish(self, request):
        has_perm = request.user.has_perm('classes.change_session_state')
        return has_perm and self.state in (self.STATE_DRAFT, self.STATE_UNAPPROVED)

    def publish(self, request):
        if self.can_publish(request):
            self.state = self.STATE_PUBLIC
            self.save()
            # publish to eventbrite here

    def can_cancel(self, request):
        has_perm = request.user.has_perm('classes.change_session_state')
        return has_perm and self.state in (self.STATE_DRAFT, self.STATE_UNAPPROVED, self.STATE_PUBLIC)

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

