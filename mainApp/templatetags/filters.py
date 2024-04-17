from django import template
from mainApp import visibleConstell

register = template.Library()

@register.filter
def replace(value, args):
    """Replaces spaces with underscores."""
    old, new = args.split(',')
    return value.replace(old, new)

@register.filter
def is_VisibleConstell(value):
    return isinstance(value,visibleConstell.VisibleConstell)