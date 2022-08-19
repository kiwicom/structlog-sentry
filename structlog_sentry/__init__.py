from __future__ import annotations

import logging
import sys
from fnmatch import fnmatch
from typing import Any, Iterable, Optional

from sentry_sdk import Hub
from sentry_sdk.integrations.logging import _IGNORED_LOGGERS
from sentry_sdk.utils import capture_internal_exceptions, event_from_exception
from structlog.types import EventDict, ExcInfo, WrappedLogger


def _figure_out_exc_info(v: Any) -> ExcInfo:
    """
    Depending on the Python version will try to do the smartest thing possible
    to transform *v* into an ``exc_info`` tuple.
    """
    if isinstance(v, BaseException):
        return (v.__class__, v, v.__traceback__)
    elif isinstance(v, tuple):
        return v  # type: ignore
    elif v:
        return sys.exc_info()  # type: ignore

    return v


class SentryProcessor:
    """Sentry processor for structlog.

    Uses Sentry SDK to capture events in Sentry.
    """

    def __init__(
        self,
        level: int = logging.WARNING,
        breadcrumb_level: int = logging.INFO,
        active: bool = True,
        as_context: bool = True,
        tag_keys: list[str] | str | None = None,
        ignore_loggers: Iterable[str] | None = None,
        verbose: bool = False,
        hub: Hub | None = None,
    ) -> None:
        """
        :param level: events of this or higher levels will be reported to Sentry.
        :param breadcrumb_level: events of this or higher levels will be reported as
            Sentry breadcrumbs.
        :param active: a flag to make this processor enabled/disabled.
        :param as_context: send `event_dict` as extra info to Sentry.
        :param tag_keys: a list of keys. If any if these keys appear in `event_dict`,
            the key and its corresponding value in `event_dict` will be used as Sentry
            event tags. use `"__all__"` to report all key/value pairs of event as tags.
        :param ignore_loggers: a list of logger names to ignore any events from.
        :param verbose: report the action taken by the logger in the `event_dict`.
        """
        self.level = level
        self.breadcrumb_level = breadcrumb_level
        self.active = active
        self.tag_keys = tag_keys
        self.verbose = verbose

        self._hub = hub
        self._as_context = as_context
        self._original_event_dict: dict = None

        self._ignored_loggers: set[str] = set()
        if ignore_loggers is not None:
            self._ignored_loggers.update(set(ignore_loggers))

    @staticmethod
    def _get_logger_name(logger: WrappedLogger, event_dict: dict) -> Optional[str]:
        """Get logger name from event_dict with a fallbacks to logger.name and
        record.name

        :param logger: logger instance
        :param event_dict: structlog event_dict
        """
        record = event_dict.get("_record")
        l_name = event_dict.get("logger")
        logger_name = None

        if l_name:
            logger_name = l_name
        elif record and hasattr(record, "name"):
            logger_name = record.name

        if not logger_name and logger and hasattr(logger, "name"):
            logger_name = logger.name

        return logger_name

    def _get_hub(self) -> Hub:
        return self._hub or Hub.current

    def _get_event_and_hint(self, event_dict: EventDict) -> tuple[dict, dict]:
        """Create a sentry event and hint from structlog `event_dict` and sys.exc_info.

        :param event_dict: structlog event_dict
        """
        exc_info = _figure_out_exc_info(event_dict.get("exc_info", None))
        has_exc_info = exc_info and exc_info != (None, None, None)

        if has_exc_info:
            event, hint = event_from_exception(exc_info)
        else:
            event, hint = {}, {}

        event["message"] = event_dict.get("event")
        event["level"] = event_dict.get("level")
        if "logger" in event_dict:
            event["logger"] = event_dict["logger"]

        if self._as_context:
            event["contexts"] = {"structlog": self._original_event_dict.copy()}
        if self.tag_keys == "__all__":
            event["tags"] = self._original_event_dict.copy()
        if isinstance(self.tag_keys, list):
            event["tags"] = {
                key: event_dict[key] for key in self.tag_keys if key in event_dict
            }

        return event, hint

    def _get_breadcrumb_and_hint(self, event_dict: EventDict) -> tuple[dict, dict]:
        event = {
            "type": "log",
            "level": event_dict.get("level"),  # type: ignore
            "category": event_dict.get("logger"),
            "message": event_dict["event"],
            "timestamp": event_dict.get("timestamp"),
            "data": {},
        }

        return event, {"log_record": event_dict}

    def _can_record(self, logger: WrappedLogger, event_dict: EventDict) -> bool:
        logger_name = self._get_logger_name(logger=logger, event_dict=event_dict)
        if logger_name:
            for ignored_logger in _IGNORED_LOGGERS | self._ignored_loggers:
                if fnmatch(logger_name, ignored_logger):  # type: ignore
                    if self.verbose:
                        event_dict["sentry"] = "ignored"
                    return False
        return True

    def _handle_event(self, event_dict: EventDict) -> None:
        with capture_internal_exceptions():
            event, hint = self._get_event_and_hint(event_dict)
            sid = self._get_hub().capture_event(event, hint=hint)
            if sid:
                event_dict["sentry_id"] = sid
            if self.verbose:
                event_dict["sentry"] = "sent"

    def _handle_breadcrumb(self, event_dict: EventDict) -> None:
        with capture_internal_exceptions():
            event, hint = self._get_breadcrumb_and_hint(event_dict)
            self._get_hub().add_breadcrumb(event, hint=hint)

    def __call__(
        self, logger: WrappedLogger, name: str, event_dict: EventDict
    ) -> EventDict:
        """A middleware to process structlog `event_dict` and send it to Sentry."""
        self._original_event_dict = event_dict.copy()
        sentry_skip = event_dict.pop("sentry_skip", False)

        if self.active and not sentry_skip and self._can_record(logger, event_dict):
            level = getattr(logging, event_dict["level"].upper())

            if level >= self.level:
                self._handle_event(event_dict)

            if level >= self.breadcrumb_level:
                self._handle_breadcrumb(event_dict)

        if self.verbose:
            event_dict.setdefault("sentry", "skipped")

        return event_dict
