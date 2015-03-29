from django.core import validators
from django.db import models
from django_eventbrite.models import Event
from djcourses import models as courses
from djmoney.models.fields import MoneyField
from permission import add_permission_logic
from permission.logics import AuthorPermissionLogic
from permission.logics import CollaboratorsPermissionLogic
from phonenumber_field.modelfields import PhoneNumberField

class Person(courses.Person):
    emergency_contact = models.ForeignKey('Person', null=True, blank=True)
    class Meta:
        verbose_name_plural='People'

class Instructor(Person):
    PAYMENT_TYPES = (
            ('check', 'check'),
            ('deposit', 'direct deposit'),
            ('bitcoin', 'bitcoin'),
    )

    EMPLOYMENT_TYPES = (
            ('w2', 'W2'),
            ('1099', '1099'),
    )

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

    bio = models.TextField(blank=True)
    #class Meta:
    #    permissions = (
    #        ('edit_own_profile', 'Can edit own user profile'),
    #    )

class Course(courses.Course):
    ticket_price = MoneyField(max_digits=6, decimal_places=2, default_currency='USD')
    instructors = models.ManyToManyField(Instructor)

    def __str__(self):
        return self.name

class Session(courses.Session):
    course = models.ForeignKey(Course)
    ticket_price = MoneyField(max_digits=6, decimal_places=2, default_currency='USD')
    event = models.OneToOneField(Event, null=True)

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

