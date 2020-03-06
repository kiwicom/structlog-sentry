import logging
import sys
from typing import List, Optional, Tuple, Union

from sentry_sdk import capture_event
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.utils import event_from_exception


class SentryProcessor:
    """Sentry processor for structlog.

    Uses Sentry SDK to capture events in Sentry.
    """

    def __init__(
        self,
        level: int = logging.WARNING,
        active: bool = True,
        as_extra: bool = True,
        tag_keys: Union[List[str], str] = None,
    ) -> None:
        """
        :param level: events of this or higher levels will be reported to Sentry.
        :param active: a flag to make this processor enabled/disabled.
        :param as_extra: send `event_dict` as extra info to Sentry.
        :param tag_keys: a list of keys. If any if these keys appear in `event_dict`,
            the key and its corresponding value in `event_dict` will be used as Sentry
            event tags. use `"__all__"` to report all key/value pairs of event as tags.
        """
        self.level = level
        self.active = active
        self.tag_keys = tag_keys
        self._as_extra = as_extra
        self._original_event_dict = None

    def _get_event_and_hint(self, event_dict: dict) -> Tuple[dict, Optional[str]]:
        """Create a sentry event and hint from structlog `event_dict` and sys.exc_info.

        :param event_dict: structlog event_dict
        """
        exc_info = event_dict.get("exc_info", True)
        if exc_info is True:
            # logger.exeception() or logger.error(exc_info=True)
            exc_info = sys.exc_info()
        has_exc_info = exc_info and exc_info != (None, None, None)

        if has_exc_info:
            event, hint = event_from_exception(exc_info)
        else:
            event, hint = {}, None

        event["message"] = event_dict.get("event")
        event["level"] = event_dict.get("level")
        if "logger" in event_dict:
            event["logger"] = event_dict["logger"]

        if self._as_extra:
            event["extra"] = self._original_event_dict
        if self.tag_keys == "__all__":
            event["tags"] = self._original_event_dict
        elif isinstance(self.tag_keys, list):
            event["tags"] = {
                key: event_dict[key] for key in self.tag_keys if key in event_dict
            }

        return event, hint

    def _log(self, event_dict: dict) -> str:
        """Send an event to Sentry and return sentry event id.

        :param event_dict: structlog event_dict
        """
        event, hint = self._get_event_and_hint(event_dict)
        return capture_event(event, hint=hint)

    def __call__(self, logger, method, event_dict) -> dict:
        """A middleware to process structlog `event_dict` and send it to Sentry."""
        self._original_event_dict = event_dict.copy()
        sentry_skip = event_dict.pop("sentry_skip", False)
        do_log = getattr(logging, event_dict["level"].upper()) >= self.level

        if sentry_skip or not self.active or not do_log:
            event_dict["sentry"] = "skipped"
            return event_dict

        sid = self._log(event_dict)
        event_dict["sentry"] = "sent"
        event_dict["sentry_id"] = sid

        return event_dict


class SentryJsonProcessor(SentryProcessor):
    """Sentry processor for structlog which uses JSONRenderer.

    Uses Sentry SDK to capture events in Sentry.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # A set of all encountered structured logger names. If an application uses
        # multiple loggers with different names (eg. different qualnames), then each of
        # those loggers needs to be ignored in Sentry's logging integration so that this
        # processor will be the only thing reporting the events.
        self._ignored = set()

    def __call__(self, logger, method, event_dict) -> dict:
        self._ignore_logger(logger, event_dict)
        return super().__call__(logger, method, event_dict)

    def _ignore_logger(self, logger, event_dict: dict) -> None:
        """Tell Sentry to ignore logger, if we haven't already.

        This is temporary workaround to prevent duplication of a JSON event in Sentry.

        :param logger: logger instance
        :param event_dict: structlog event_dict
        """
        record = event_dict.get("_record")
        l_name = event_dict.get("logger")
        if l_name:
            logger_name = l_name
        elif record is None:
            logger_name = logger.name
        else:
            logger_name = record.name

        if not logger_name:
            raise Exception("Cannot ignore logger without a name.")

        if logger_name not in self._ignored:
            ignore_logger(logger_name)
            self._ignored.add(logger_name)
