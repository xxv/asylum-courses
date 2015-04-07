from django.shortcuts import render

from asylum.classes.models import Session
# Create your views here.

def session_list(request):
    sessions = Session.objects.all()
    return render(request, 'session_list.html', { 'sessions': sessions })
