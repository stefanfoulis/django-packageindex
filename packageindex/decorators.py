from django.contrib.auth import login, REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.utils.http import urlquote

try:
    from functools import wraps, WRAPPER_ASSIGNMENTS
except ImportError:
    from django.utils.functional import wraps, WRAPPER_ASSIGNMENTS

try:
    from django.utils.decorators import available_attrs
except ImportError:
    def available_attrs(fn):
        return tuple(a for a in WRAPPER_ASSIGNMENTS if hasattr(fn, a))

from packageindex.http import HttpResponseUnauthorized, login_basic_auth

# Find us a csrf exempt decorator that'll work with Django 1.0+
try:
    from django.views.decorators.csrf import csrf_exempt
except ImportError:
    try:
        from django.contrib.csrf.middleware import csrf_exempt
    except ImportError:
        def csrf_except(view_func): return view_func

def basic_auth(view_func):
    """ Decorator for views that need to handle basic authentication such as
    distutils views. """

    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated():
            return view_func(request, *args, **kwargs)
        user = login_basic_auth(request)

        if not user:
            return HttpResponseUnauthorized('pypi')

        login(request, user)
        if not request.user.is_authenticated():
            return HttpResponseForbidden("Not logged in, or invalid username/"
                                         "password.")
        return view_func(request, *args, **kwargs)
    return wraps(view_func, assigned=available_attrs(view_func))(_wrapped_view)

def user_owns_package(login_url=None, redirect_field_name=REDIRECT_FIELD_NAME):
    """
    Decorator for views that checks whether the user owns the currently requested
    package.
    """
    if not login_url:
        from django.conf import settings
        login_url = settings.LOGIN_URL
    
    def decorator(view_func):
        def _wrapped_view(request, package, *args, **kwargs):
            if request.user.packages_owned.filter(name=package).count() > 0:
                return view_func(request, package=package, *args, **kwargs)

            path = urlquote(request.get_full_path())
            tup = login_url, redirect_field_name, path
            return HttpResponseRedirect('%s?%s=%s' % tup)
        return wraps(view_func, assigned=available_attrs(view_func))(_wrapped_view)
    return decorator

def user_maintains_package(login_url=None, redirect_field_name=REDIRECT_FIELD_NAME):
    """
    Decorator for views that checks whether the user maintains (or owns) the
    currently requested package.
    """
    if not login_url:
        from django.conf import settings
        login_url = settings.LOGIN_URL

    def decorator(view_func):
        def _wrapped_view(request, package, *args, **kwargs):
            if (request.user.is_authenticated() and
                (request.user.packages_owned.filter(name=package).count() > 0 or
                 request.user.packages_maintained.filter(name=package).count() > 0)):
                return view_func(request, package=package, *args, **kwargs)

            path = urlquote(request.get_full_path())
            tup = login_url, redirect_field_name, path
            return HttpResponseRedirect('%s?%s=%s' % tup)
        return wraps(view_func, assigned=available_attrs(view_func))(_wrapped_view)
    return decorator
