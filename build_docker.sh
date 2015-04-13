#!/bin/sh

mkdir -p dev

rsync --exclude '*~' --delete --exclude .git -avu ../eventbrite-sdk-python/ dev/eventbrite-sdk-python/
rsync --exclude '*~' --delete --exclude .git -avu ../dj_eventbrite/ dev/dj_eventbrite/
rsync --exclude '*~' --delete --exclude .git -avu ../django-scheduler/ dev/django-scheduler/

docker build -t asylum .
