import functools
import time
import socket

from contextlib import contextmanager

import statsd

try:
    from django.conf import settings
except ImportError:
    # On some projects, where django isn't used,
    # settings are usually a separate module in the project
    import settings

_hostname = 'unknown'
try:
    _hostname = socket.gethostname().replace('.', '-')
except Exception:
    pass

_telegraf_client = None

def silent_fail(fn):
    def inner(*args, **kwargs):
        if not settings.STATSD_INFLUX_HOST:
            return
        return fn(*args, **kwargs)
    return inner

def _get_client():
    global _telegraf_client

    if _telegraf_client is None:
        _telegraf_client = statsd.StatsClient(settings.STATSD_INFLUX_HOST, settings.STATSD_INFLUX_PORT)

    return _telegraf_client


def _get_default_tags():
    return [('host', _hostname)]


def _escape_tags(tag):
    return tag.replace(':', '_')


def _get_tags(custom_tags):
    tags = sorted(custom_tags.items(), key=lambda x: x[0]) + _get_default_tags()

    return ','.join('{0}={1}'.format(_escape_tags(k), _escape_tags(v)) for k, v in tags)


@silent_fail
@contextmanager
def block_timer(name, **tags):
    start = time.time()
    yield
    new_name = '{prefix}.{name},{tags}'.format(
        prefix=settings.PROJECT_NAME,
        source=_hostname,
        name=name,
        tags=_get_tags(tags),
    )
    _get_client().timing(new_name, int((time.time() - start) * 1000))

@silent_fail
def timer(name, **tags):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with block_timer(name, **tags):
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator

@silent_fail
def incr(name, count, **tags):
    _get_client().incr('{prefix}.{name},{tags}'.format(
        prefix=settings.PROJECT_NAME,
        name=name,
        tags=_get_tags(tags),
    ), count)

@silent_fail
def gauge(name, value, **tags):
    _get_client().gauge('{prefix}.{name},{tags}'.format(
        prefix=settings.PROJECT_NAME,
        name=name,
        tags=_get_tags(tags),
    ), value)
