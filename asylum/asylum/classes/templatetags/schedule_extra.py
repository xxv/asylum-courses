# -*- coding: utf-8 -*-

from django import template
from django.conf import settings
from django.utils import formats
from django.utils.dateformat import format, time_format
from django.utils.timezone import template_localtime
register = template.Library()

@register.filter
def daynames(occurrences, arg=None):
    fmt = arg or 'l'
    df = format
    first = template_localtime(occurrences[0].start)
    last = template_localtime(occurrences[-1].start)

    try:
        if len(occurrences) == 1:
            return df(first, fmt)
        else:
            frequency = occurrences[0].event.rule.frequency
            if frequency == 'WEEKLY':
                # "Wednesdays"
                return "{0}s".format(df(first, fmt))
            elif frequency == 'DAILY':
                if len(occurrences) == 2:
                    return "{0} & {1}".format(df(first, fmt), df(last, fmt))
                elif len(occurrences) > 7:
                    return "Daily"
                else:
                    return "{0}–{1}".format(df(first, fmt), df(last, fmt))
            elif frequency == 'MONTHLY':
                return "Monthly"
    except AttributeError:
        return ''

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

