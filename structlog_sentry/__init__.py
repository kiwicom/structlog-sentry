import logging
import os
import sys

from sentry_sdk import capture_event
from sentry_sdk.utils import event_from_exception


class SentryProcessor:
    """Sentry processor for structlog. Uses Sentry SDK to capture events in Sentry."""

    def __init__(self, level=logging.WARNING, active=True):
        self.level = level
        self.active = active

    def _log(self, event_dict, level):
        exc_info = event_dict.pop("exc_info", sys.exc_info())
        has_exc_info = exc_info and exc_info != (None, None, None)

        if has_exc_info:
            event, hint = event_from_exception(exc_info)
        else:
            event, hint = {}, None

        event["message"] = event_dict.get("event")
        event["level"] = level
        event["extra"] = event_dict

        return capture_event(event, hint=hint)

    def __call__(self, logger, method, event_dict):
        event_dict["sentry"] = "skipped"
        sentry_skip = event_dict.pop("sentry_skip", False)

        level = event_dict["level"]
        do_log = getattr(logging, level.upper()) >= self.level

        if sentry_skip or not self.active or not do_log:
            return event_dict

        sid = self._log(event_dict, level=level)

        event_dict["sentry_id"] = sid
        event_dict["sentry"] = "sent"

        return event_dict
