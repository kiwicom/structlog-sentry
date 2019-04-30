# structlog-sentry

| What          | Where                                         |
| ------------- | --------------------------------------------- |
| Documentation | <https://github.com/kiwicom/structlog-sentry> |
| Maintainer    | @paveldedik                                   |

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
        structlog.stdlib.add_log_level,  # required before SentryProcessor()
        SentryProcessor(level=logging.ERROR),
    ],
    logger_factory=...,
    wrapper_class=...,
)


log = structlog.get_logger()
```

Do not forget to add the `structlog.stdlib.add_log_level` processor before
`SentryProcessor`. The `SentryProcessor` class takes the following arguments:

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

Logging calls with no `sys.exc_info()` are also automatically captured by Sentry:

```python
log.info("info message", scope="accounts")
log.warning("warning message", scope="invoices")
log.error("error message", scope="products")
```

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
