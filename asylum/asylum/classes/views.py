from asylum.classes.models import Session, Category, TemplateText
from django.shortcuts import render
from django.http import Http404
from django.template import Template, Context

class TemplateTextContext(Context):
    def __init__(self):
        super(TemplateTextContext, self).__init__()
        self.load_text_templates()

    def load_text_templates(self):
        temps = {}
        for template in TemplateText.objects.all():
            temps[template.keyword] = template.text
        self.update(temps)

def session_list(request):
    categories = Category.objects.order_by('name')

    return render(request, 'session_list.html', { 'categories': categories })

def session_item(request, id):
    try:
        s = Session.objects.get(pk=id)
    except Session.DoesNotExist:
        raise Http404("Session doesn't exist")

    context = TemplateTextContext()
    description = Template(s.description).render(context)
    blurb = Template(s.blurb).render(context)

    return render(request, 'session_item.html', {
            'session': s,
            'description': description,
            'blurb': blurb,
            })
