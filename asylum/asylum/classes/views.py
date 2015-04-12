from asylum.classes.models import Session, Category
from django.shortcuts import render

def session_list(request):
    categories = Category.objects.order_by('name')

    return render(request, 'session_list.html', { 'categories': categories })
