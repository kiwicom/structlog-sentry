# structlog-sentry

| What          | Where                                         |
| ------------- | --------------------------------------------- |
| Documentation | <https://github.com/kiwicom/structlog-sentry> |
| Maintainer    | @kiwicom/platform                             |

Based on <https://gist.github.com/hynek/a1f3f92d57071ebc5b91>

## Installation

Install the package with [pip](https://pip.pypa.io/):

```
pip install structlog-sentry
```

## Usage

This module is intended to be used with `structlog` like this:

```python
import sentry_sdk
import structlog
from structlog_sentry import SentryProcessor


sentry_sdk.init()  # pass dsn in argument or via SENTRY_DSN env variable

structlog.configure(
    processors=[
        structlog.stdlib.add_logger_name,  # optional, must be placed before SentryProcessor()
        structlog.stdlib.add_log_level,  # required before SentryProcessor()
        SentryProcessor(event_level=logging.ERROR),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
)


log = structlog.get_logger()
```

Do not forget to add the `structlog.stdlib.add_log_level` and optionally the
`structlog.stdlib.add_logger_name` processors before `SentryProcessor`. The
`SentryProcessor` class takes the following arguments:

- `level` Events of this or higher levels will be reported as Sentry
  breadcrumbs. Default is `logging.INFO`.
- `event_level` Events of this or higher levels will be reported to Sentry
  as events. Default is `logging.WARNING`.
- `active` A flag to make this processor enabled/disabled.
- `as_context` Send `event_dict` as extra info to Sentry. Default is `True`.
- `ignore_breadcrumb_data` A list of data keys that will be excluded from
  [breadcrumb data](https://docs.sentry.io/platforms/python/enriching-events/breadcrumbs/#manual-breadcrumbs).
  Defaults to keys which are already sent separately, i.e. `level`, `logger`,
  `event` and `timestamp`. All other data in `event_dict` will be sent as
  breadcrumb data.
- `tag_keys` A list of keys. If any if these keys appear in `event_dict`,
  the key and its corresponding value in `event_dict` will be used as Sentry
  event tags. use `"__all__"` to report all key/value pairs of event as tags.
- `ignore_loggers` A list of logger names to ignore any events from.
- `verbose` Report the action taken by the logger in the `event_dict`.
  Default is `False`.
- `scope` Optionally specify `sentry_sdk.Client` (in `structlog-sentry<2.2`
  this corresponds to `hub: sentry_sdk.Hub`).

Now events are automatically captured by Sentry with `log.error()`:

```python
try:
    1/0
except ZeroDivisionError:
    log.error("zero divsiion")

try:
    resp = requests.get(f"https://api.example.com/users/{user_id}/")
    resp.raise_for_status()
except RequestException:
    log.error("request error", user_id=user_id)
```

This won't automatically collect `sys.exc_info()` along with the message, if you want
to enable this behavior, just pass `exc_info=True`.

When you want to use structlog's built-in
[`format_exc_info`](http://www.structlog.org/en/stable/api.html#structlog.processors.format_exc_info)
processor, make that the `SentryProcessor` comes _before_ `format_exc_info`!
Otherwise, the `SentryProcessor` won't have an `exc_info` to work with, because
it's removed from the event by `format_exc_info`.

Logging calls with no `sys.exc_info()` are also automatically captured by Sentry
either as breadcrumbs (if configured by the `level` argument) or as events:

```python
log.info("info message", scope="accounts")
log.warning("warning message", scope="invoices")
log.error("error message", scope="products")
```

If you do not want to forward a specific logs into Sentry, you can pass the
`sentry_skip=True` optional argument to logger methods, like this:

```python
log.error("error message", sentry_skip=True)
```

### Sentry Tags

You can set some or all of key/value pairs of structlog `event_dict` as sentry `tags`:

```python
structlog.configure(
    processors=[
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        SentryProcessor(event_level=logging.ERROR, tag_keys=["city", "timezone"]),
    ],...
)

log.error("error message", city="Tehran", timezone="UTC+3:30", movie_title="Some title")
```

this will report the error and the sentry event will have **city** and **timezone** tags.
If you want to have all event data as tags, create the `SentryProcessor` with `tag_keys="__all__"`.

```python
structlog.configure(
    processors=[
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        SentryProcessor(event_level=logging.ERROR, tag_keys="__all__"),
    ],...
)
```

### Skip Context

By default `SentryProcessor` will send `event_dict` key/value pairs as contextual info to sentry.
Sometimes you may want to skip this, specially when sending the `event_dict` as sentry tags:

```python
structlog.configure(
    processors=[
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        SentryProcessor(event_level=logging.ERROR, as_context=False, tag_keys="__all__"),
    ],...
)
```

### Ignore specific loggers

If you want to ignore specific loggers from being processed by the `SentryProcessor` just pass
a list of loggers when instantiating the processor:

```python
structlog.configure(
    processors=[
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        SentryProcessor(event_level=logging.ERROR, ignore_loggers=["some.logger"]),
    ],...
)
```

### Logging as JSON

If you want to configure `structlog` to format the output as **JSON** (maybe for
[elk-stack](https://www.elastic.co/elk-stack)) you have to disable standard logging
integration in Sentry SDK by passing the `LoggingIntegration(event_level=None, level=None)`
instance to `sentry_sdk.init` method. This prevents duplication of an event reported to sentry:

```python
from sentry_sdk.integrations.logging import LoggingIntegration


INTEGRATIONS = [
    # ... other integrations
    LoggingIntegration(event_level=None, level=None),
]

sentry_sdk.init(integrations=INTEGRATIONS)
```

This integration tells `sentry_sdk` to _ignore_ standard logging and captures the events manually.

## Testing

To run all tests:

```
tox
```

## Contributing

Create a merge request and tag @kiwicom/platform for review.
