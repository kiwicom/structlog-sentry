# structlog-sentry

[![Build Status](https://travis-ci.org/kiwicom/structlog-sentry.svg?branch=master)](https://travis-ci.org/kiwicom/structlog-sentry)

| What          | Where                                         |
| ------------- | --------------------------------------------- |
| Documentation | <https://github.com/kiwicom/structlog-sentry> |
| Maintainer    | [@paveldedik](https://github.com/paveldedik)  |

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
        structlog.stdlib.add_logger_name,  # optional, but before SentryProcessor()
        structlog.stdlib.add_log_level,  # required before SentryProcessor()
        SentryProcessor(level=logging.ERROR),
    ],
    logger_factory=...,
    wrapper_class=...,
)


log = structlog.get_logger()
```

Do not forget to add the `structlog.stdlib.add_log_level` and optionally the
`structlog.stdlib.add_logger_name` processors before `SentryProcessor`. The
`SentryProcessor` class takes the following arguments:

- `level` - events of this or higher levels will be reported to Sentry,
  default is `WARNING`
- `active` - default is `True`, setting to `False` disables the processor

Now exceptions are automatically captured by Sentry with `log.error()`:

```python
try:
    1/0
except ZeroDivisionError:
    log.error()

try:
    resp = requests.get(f"https://api.example.com/users/{user_id}/")
    resp.raise_for_status()
except RequestException:
    log.error("request error", user_id=user_id)
```

This will automatically collect `sys.exc_info()` along with the message, if you want
to turn this behavior off, just pass `exc_info=False`.

When you want to use structlog's built-in
[`format_exc_info`](http://www.structlog.org/en/stable/api.html#structlog.processors.format_exc_info)
processor, make that the `SentryProcessor` comes *before* `format_exc_info`!
Otherwise, the `SentryProcessor` won't have an `exc_info` to work with, because
it's removed from the event by `format_exc_info`.

Logging calls with no `sys.exc_info()` are also automatically captured by Sentry:

```python
log.info("info message", scope="accounts")
log.warning("warning message", scope="invoices")
log.error("error message", scope="products")
```

If you do not want to forward logs into Sentry, just pass the `sentry_skip=True`
optional argument to logger methods, like this:

```python
log.error(sentry_skip=True)
```

### Sentry Tags

You can set some or all of key/value pairs of structlog `event_dict` as sentry `tags`:

```python
structlog.configure(
    processors=[
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        SentryProcessor(level=logging.ERROR, tag_keys=["city", "timezone"]),
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
        SentryProcessor(level=logging.ERROR, tag_keys="__all__"),
    ],...
)
```

### Skip Extra

By default `SentryProcessor` will send `event_dict` key/value pairs as extra info to the sentry.
Sometimes you may want to skip this, specially when sending the `event_dict` as sentry tags:

```python
structlog.configure(
    processors=[
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        SentryProcessor(level=logging.ERROR, as_extra=False, tag_keys="__all__"),
    ],...
)
```

### Logging as JSON

If you want to configure `structlog` to format the output as **JSON**
(maybe for [elk-stack](https://www.elastic.co/elk-stack)) you have to use `SentryJsonProcessor` to prevent
duplication of an event reported to sentry.

```python
from structlog_sentry import SentryJsonProcessor

structlog.configure(
    processors=[
        structlog.stdlib.add_logger_name,  # required before SentryJsonProcessor()
        structlog.stdlib.add_log_level,
        SentryJsonProcessor(level=logging.ERROR, tag_keys="__all__"),
        structlog.processors.JSONRenderer()
    ],...
)
```

This processor tells sentry to *ignore* the logger and captures the events manually.

## Testing

To run all tests:

```
tox
```

Note that tox doesn't know when you change the `requirements.txt`
and won't automatically install new dependencies for test runs.
Run `pip install tox-battery` to install a plugin which fixes this silliness.

## Contributing

Create a merge request and assign it to @paveldedik for review.
