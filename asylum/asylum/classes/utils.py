from asylum.classes.models import Session, TemplateText
from django.template import Template, Context
#from django_eventbrite.utils import eb, e2l
from django_eventbrite.utils import eb, to_multipart, to_datetime, e2l, to_money
from django_eventbrite.models import Event, TicketType
from markdown_deux import markdown

class TemplateTextContext(Context):
    def __init__(self):
        super(TemplateTextContext, self).__init__()
        self.load_text_templates()

    def load_text_templates(self):
        temps = {}
        for template in TemplateText.objects.all():
            temps[template.keyword] = template.text
        self.update(temps)

def multipart_markdown(md_text, template_text=True):
    if template_text:
        md_text = Template(md_text).render(TemplateTextContext())

    return to_multipart(md_text, markdown(md_text))

def publish_to_eb(session):
    if session.state not in (Session.STATE_READY_TO_PUBLISH,):
        return
    event = {}
    event['name'] = to_multipart(session.name)
    event['description'] = multipart_markdown(session.description)
    event['start'] = to_datetime(session.calendar_event.start)
    event['end'] = to_datetime(session.get_occurrences()[-1].end)
    event['capacity'] = session.max_enrollment

    # TODO add some default somewhere
    event['currency'] = 'USD'

    result = eb.post_event({'event': event})

    session.event = e2l(Event, 'event', result)
    session.state = Session.STATE_PUBLIC
    session.save()

    eb_id = session.event.eb_id

    # once the event is created, the tickets can be created and loaded into the DB
    tc = {}
    tc['name'] = 'General Admission'
    if session.material_cost_collection == Session.MATERIAL_COST_INCLUDED_IN_TICKET:
        tc['name'] = "{0} + Materials".format(tc['name'])

    tc['description'] = ''
    tc['quantity_total'] = session.max_enrollment
    tc['cost'] = to_money(session.ticket_price)
    tc['donation'] = False
    tc['free'] = False
    tc['include_fee'] = False

    e2l(TicketType, 'ticket_class', eb.post_event_ticket_classes(eb_id, {'ticket_class': tc}))

