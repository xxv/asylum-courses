# -*- coding: utf-8 -*-

from django import template
from django.conf import settings
from django.utils import formats
from django.utils.dateformat import format, time_format
from django.utils.timezone import template_localtime
register = template.Library()

WEEKDAYS = set((0, 1, 2, 3, 4))
WEEKENDDAYS = set((5, 6))

ALL_DAYS = WEEKDAYS.union(WEEKENDDAYS)

@register.filter
def daynames(occurrences, arg=None):
    fmt = arg or 'l'

    dates = list(map(lambda occurrence: occurrence.start, occurrences))
    days = list(map(lambda date: format(date, fmt), dates))
    days_num = list(map(lambda date: date.weekday(), dates))

    first_day = days[0]
    last_day = days[-1]

    try:
        if len(days) == 0:
            return ''

        if len(days) == 1:
            return first_day

        # By doing it this way, we're guaranteed that the output represents the
        # data regardless of the complexities of the repeating cycles.
        unique_days = set(days_num)

        if unique_days == WEEKDAYS:
            return "Weekdays"

        if unique_days == WEEKENDDAYS:
            if len(days) == 2:
                return "Weekend"
            return "Weekends"

        if unique_days == ALL_DAYS:
            return "Daily"

        if len(unique_days) == 1:
            # e.g. "Wednesdays"
            return "{0}s".format(first_day)
        else:
            if len(dates) == len(unique_days):
                # e.g. "Wednesday & Friday"
                # e.g. "Wednesday, Thursday & Friday"
                return oxford_comma(days)
            else:
                # e.g. "Wednesdays & Fridays"
                return oxford_comma(list(map(lambda d: "{0}s".format(d),
                    days[:len(unique_days)])))

        return ''

    except AttributeError:
        return ''

def oxford_comma(items):
    if len(items) == 0:
        return ''
    if len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return "{0} & {1}".format(*items)
    else:
        joinme = items[:-1]
        joinme.append("& {0}".format(items[-1]))
        return ", ".join(joinme)

@register.filter
def daterange(occurrences, arg=None):
    default_fmt = arg or settings.DATE_FORMAT
    df = format
    first = template_localtime(occurrences[0].start)
    last = template_localtime(occurrences[-1].start)

    try:
        if len(occurrences) == 1:
            return df(first, default_fmt)
        else:
            first_month = df(first, 'F')
            last_month = df(last, 'F')
            if len(occurrences) > 2:
                delim = "–"
            else:
                delim = " & "
            if first_month == last_month:
                return "{0}{1}{2}".format(df(first, default_fmt), delim, df(last, 'j'))
            else:
                return "{0}{1}{2}".format(df(first, default_fmt), delim, df(last, default_fmt))
    except AttributeError:
        return ''

@register.filter(expects_localtime=True, is_safe=False)
def timerange(occurrence, arg=None):
    default_fmt = settings.TIME_FORMAT
    tf = formats.time_format
    try:
        tf(occurrence.start, 'a')
    except AttributeError:
        tf = time_format
    start = template_localtime(occurrence.start)
    end = template_localtime(occurrence.end)
    try:
        start_ampm = tf(start, 'a')
        end_ampm = tf(end, 'a')
        if start_ampm == end_ampm:
            return "{0}–{1}".format(tf(start, 'g'), tf(end, default_fmt))
        else:
            return "{0}–{1}".format(tf(start, default_fmt), tf(end, default_fmt))
    except AttributeError:
        return ''

