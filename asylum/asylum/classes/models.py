from django.contrib.auth.models import User
from django.core import validators
from django.db import models
from django_eventbrite.models import Event
from djmoney.models.fields import MoneyField
from permission import add_permission_logic
from permission.logics import AuthorPermissionLogic
from permission.logics import CollaboratorsPermissionLogic
from phonenumber_field.modelfields import PhoneNumberField

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
            validators = [
                validators.MaxValueValidator(100),
                ]
            )
    asylum_percentage = models.PositiveSmallIntegerField(default=50,
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

class AbsCourse(models.Model):
    MATERIAL_COST_COLLECTION = (
            ('ticket', 'included in ticket price'),
            ('instructor', 'collected by instructor at first class'),
    )
    name = models.CharField(max_length=255)
    description = models.TextField()

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
    ticket_price = MoneyField(max_digits=6, decimal_places=2, default_currency='USD')
    material_cost = MoneyField(max_digits=6, decimal_places=2, default_currency='USD')
    material_cost_collection = models.CharField(max_length=10, choices = MATERIAL_COST_COLLECTION, null=True)
    instructors = models.ManyToManyField(Instructor)

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
    def set_from_event(self, event):
        self.name = event.name
        self.description = event.description
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

class Session(AbsCourse):
    course = models.ForeignKey(Course)
    event = models.OneToOneField(Event, null=True)

    def eb_id(self):
        if not self.event:
            return None
        return self.event.eb_id
    eb_id.short_description = 'Eventbrite ID'

    def set_from_event(self, event):
        self.name = event.name
        self.description = event.description
        if event.tickets:
            self.ticket_price = event.tickets[0].cost
        self.event = event

# Instructors can edit their own profile
add_permission_logic(Instructor, AuthorPermissionLogic(field_name='user'))

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
    delete_permission=False,
    ))

