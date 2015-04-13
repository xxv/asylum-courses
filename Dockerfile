FROM        python:3
MAINTAINER Steve Pomeroy <steve@staticfree.info>

COPY dev/eventbrite-sdk-python /tmp/eventbrite-sdk-python
RUN pip3 install /tmp/eventbrite-sdk-python/

COPY dev/dj_eventbrite /tmp/dj_eventbrite
RUN pip3 install /tmp/dj_eventbrite/

COPY dev/django-scheduler /tmp/django-scheduler
RUN pip3 install /tmp/django-scheduler

COPY requirements.txt /app/requirements.txt
RUN pip3 install -r /app/requirements.txt

ADD . /app

WORKDIR /app/asylum

