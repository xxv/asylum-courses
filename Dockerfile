FROM        python:3
MAINTAINER Steve Pomeroy <steve@staticfree.info>

COPY dj_eventbrite /tmp/dj_eventbrite
RUN pip3 install /tmp/dj_eventbrite/
COPY requirements.txt /app/requirements.txt
RUN pip3 install -r /app/requirements.txt

ADD . /app

WORKDIR /app/asylum

