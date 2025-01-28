from django import template
from cookie_consent.util import get_cookie_groups
from cookie_consent.models import CookieGroup

register = template.Library()

@register.simple_tag
def load_cookie_groups():
    cookie_groups = get_cookie_groups()
    return [group.varname for group in cookie_groups]
