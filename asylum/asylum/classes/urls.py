from asylum.classes.admin import admin_site
from django.conf.urls import patterns, include, url
from . import views

urlpatterns = patterns('',
    url('^session/(?P<id>\d+)/', views.session_item),
)
