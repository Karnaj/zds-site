# -*- coding: utf-8 -*-

from datetime import timedelta
import time

from django import template
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.template.defaultfilters import date
from django.utils.datetime_safe import datetime
from django.utils.tzinfo import LocalTimezone

register = template.Library()

"""
Define a filter to format date.
"""

# Date formatting constants

__DATE_FMT_FUTUR = "Dans le futur"
__ABS_DATE_FMT_SMALL = 'd/m/y à H\hi'       # Small format
__ABS_DATE_FMT_NORMAL = 'l d F Y à H\hi'    # Normal format
__ABS_HUMAN_TIME_FMT = "%d %b %Y, %H:%M:%S"


def date_formatter(value, tooltip, small):
    """
    Format a date to an human readable string.

    :param value: Date to format.
    :param bool tooltip: if `True`, format date to a tooltip label.
    :param bool small: if `True`, create a shorter string.
    :return:
    """
    try:
        value = datetime(value.year, value.month, value.day,
                         value.hour, value.minute, value.second)
    except (AttributeError, ValueError):
        # Check why not raise template.TemplateSyntaxError()
        return value

    if getattr(value, 'tzinfo', None):
        now = datetime.now(LocalTimezone(value))
    else:
        now = datetime.now()
    now = now - timedelta(0, 0, now.microsecond)

    if value > now:
        return __DATE_FMT_FUTUR
    else:
        delta = now - value
        # Natural time for today, absolute date after.
        # Reverse if in tooltip
        if (delta.days == 0) != tooltip:
            return naturaltime(value)
        else:
            return date(value, __ABS_DATE_FMT_SMALL if small else __ABS_DATE_FMT_NORMAL)


@register.filter
def format_date(value, small=False):
    """Format a date to an human readable string."""
    return date_formatter(value, tooltip=False, small=small)


@register.filter
def tooltip_date(value):
    """Format a date to an human readable string. To be used in tooltip."""
    return date_formatter(value, tooltip=True, small=False)


@register.filter('humane_time')
def humane_time(t):
    """Render time to an human readable string"""
    tp = time.localtime(t)
    return time.strftime(__ABS_HUMAN_TIME_FMT, tp)

