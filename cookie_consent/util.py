# -*- coding: utf-8 -*-
import datetime
from typing import Union

from .cache import all_cookie_groups, get_cookie, get_cookie_group
from .conf import settings
from .models import ACTION_ACCEPTED, ACTION_DECLINED, LogItem


def parse_cookie_str(cookie):
    dic = {}
    if not cookie:
        return dic
    for c in cookie.split("|"):
        key, value = c.split("=")
        dic[key] = value
    return dic


def dict_to_cookie_str(dic):
    return "|".join(["%s=%s" % (k, v) for k, v in dic.items() if v])


def get_cookie_dict_from_request(request):
    cookie_str = request.COOKIES.get(settings.COOKIE_CONSENT_NAME)
    return parse_cookie_str(cookie_str)


def set_cookie_dict_to_response(response, dic):
    response.set_cookie(
        settings.COOKIE_CONSENT_NAME,
        dict_to_cookie_str(dic),
        max_age=settings.COOKIE_CONSENT_MAX_AGE,
        domain=settings.COOKIE_CONSENT_DOMAIN,
        secure=settings.COOKIE_CONSENT_SECURE or None,
        httponly=settings.COOKIE_CONSENT_HTTPONLY or None,
        samesite=settings.COOKIE_CONSENT_SAMESITE,
    )


def get_cookie_value_from_request(request, varname, cookie=None):
    """
    Returns if cookie group or its specific cookie has been accepted.

    Returns True or False when cookie is accepted or declined or None
    if cookie is not set.
    """
    cookie_dic = get_cookie_dict_from_request(request)
    if not cookie_dic:
        return None

    cookie_group = get_cookie_group(varname=varname)
    if not cookie_group:
        return None
    if cookie:
        name, domain = cookie.split(":")
        cookie = get_cookie(cookie_group, name, domain)
    else:
        cookie = None

    version = cookie_dic.get(varname, None)

    if version == settings.COOKIE_CONSENT_DECLINE:
        return False
    if version is None:
        return None
    if not cookie:
        v = cookie_group.get_version()
    else:
        v = cookie.get_version()
    if version >= v:
        return True
    return None


def get_cookie_groups(varname=None):
    if not varname:
        return all_cookie_groups().values()
    keys = varname.split(",")
    return [g for k, g in all_cookie_groups().items() if k in keys]


def anonymize_ip(ip):
    """Anonymize IP by replacing last octet with zeros"""
    if not ip:
        return None
    try:
        # Handle IPv4
        if '.' in ip:
            return '.'.join(ip.split('.')[:3] + ['0'])
        # Handle IPv6
        if ':' in ip:
            return ':'.join(ip.split(':')[:-1] + ['0000'])
        return None
    except:
        return None


def accept_cookies(request, response, varname=None):
    """
    Accept cookies in Cookie Group specified by ``varname``.
    """
    cookie_dic = get_cookie_dict_from_request(request)
    for cookie_group in get_cookie_groups(varname):
        cookie_dic[cookie_group.varname] = cookie_group.get_version()
        if settings.COOKIE_CONSENT_LOG_ENABLED:
            LogItem.objects.create(
                action=ACTION_ACCEPTED,
                cookiegroup=cookie_group,
                version=cookie_group.get_version(),
                ip_address=anonymize_ip(request.META.get('REMOTE_ADDR')),
                country=request.META.get('HTTP_CF_IPCOUNTRY', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
    set_cookie_dict_to_response(response, cookie_dic)


def delete_cookies(response, cookie_group):
    if cookie_group.is_deletable:
        for cookie in cookie_group.cookie_set.all():
            response.delete_cookie(cookie.name, cookie.path, cookie.domain)


def decline_cookies(request, response, varname=None):
    """
    Decline and delete cookies in CookieGroup specified by ``varname``.
    """
    cookie_dic = get_cookie_dict_from_request(request)
    for cookie_group in get_cookie_groups(varname):
        cookie_dic[cookie_group.varname] = settings.COOKIE_CONSENT_DECLINE
        delete_cookies(response, cookie_group)
        if settings.COOKIE_CONSENT_LOG_ENABLED:
            LogItem.objects.create(
                action=ACTION_DECLINED,
                cookiegroup=cookie_group,
                version=cookie_group.get_version(),
                ip_address=anonymize_ip(request.META.get('REMOTE_ADDR')),
                country=request.META.get('HTTP_CF_IPCOUNTRY', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
    set_cookie_dict_to_response(response, cookie_dic)


def are_all_cookies_accepted(request):
    """
    Returns if all cookies are accepted.
    """
    return all(
        [
            get_cookie_value_from_request(request, cookie_group.varname)
            for cookie_group in get_cookie_groups()
        ]
    )


def _get_cookie_groups_by_state(request, state: Union[bool, None]):
    return [
        cookie_group
        for cookie_group in get_cookie_groups()
        if get_cookie_value_from_request(request, cookie_group.varname) is state
    ]


def get_not_accepted_or_declined_cookie_groups(request):
    """
    Returns all cookie groups that are neither accepted or declined.
    """
    return _get_cookie_groups_by_state(request, state=None)


def get_accepted_cookie_groups(request):
    """
    Returns all cookie groups that are accepted.
    """
    return _get_cookie_groups_by_state(request, state=True)


def get_declined_cookie_groups(request):
    """
    Returns all cookie groups that are declined.
    """
    return _get_cookie_groups_by_state(request, state=False)


def is_cookie_consent_enabled(request):
    """
    Returns if django-cookie-consent is enabled for given request.
    """
    enabled = settings.COOKIE_CONSENT_ENABLED
    if callable(enabled):
        return enabled(request)
    else:
        return enabled


def get_cookie_string(cookie_dic):
    """
    Returns cookie in format suitable for use in javascript.
    """
    expires = datetime.datetime.now() + datetime.timedelta(
        seconds=settings.COOKIE_CONSENT_MAX_AGE
    )
    cookie_str = "%s=%s; expires=%s; path=/" % (
        settings.COOKIE_CONSENT_NAME,
        dict_to_cookie_str(cookie_dic),
        expires.strftime("%a, %d %b %Y %H:%M:%S GMT"),
    )
    return cookie_str


def get_accepted_cookies(request):
    """
    Returns all accepted cookies.
    """
    cookie_dic = get_cookie_dict_from_request(request)
    accepted_cookies = []
    for cookie_group in all_cookie_groups().values():
        version = cookie_dic.get(cookie_group.varname, None)
        if not version or version == settings.COOKIE_CONSENT_DECLINE:
            continue
        for cookie in cookie_group.cookie_set.all():
            if version >= cookie.get_version():
                accepted_cookies.append(cookie)
    return accepted_cookies
