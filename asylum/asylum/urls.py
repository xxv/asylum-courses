from asylum.classes.admin import admin_site
from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'asylum.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
     url(r'^schedule/', include('schedule.urls')),
     url(r'^$', 'asylum.classes.views.session_list', name='home'),
     url(r'^courses/', include('asylum.classes.urls')),

    url(r'^admin/', include(admin_site.urls)),
)
