import logging
from dataclasses import dataclass

import pytest
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from structlog_sentry import SentryProcessor

INTEGRATIONS = [
    LoggingIntegration(event_level=None, level=None),
]

# Register custom log level
CUSTOM_LOG_LEVEL_NAME = "CUSTOM_LEVEL"
CUSTOM_LOG_LEVEL_VALUE = logging.DEBUG
logging.addLevelName(CUSTOM_LOG_LEVEL_VALUE, CUSTOM_LOG_LEVEL_NAME)


@dataclass
class ClientParams:
    include_local_variables: bool = True

    @classmethod
    def from_request(cls, request):
        if not hasattr(request, "param"):
            return cls()

        if isinstance(request.param, dict):
            return cls(**request.param)

        if isinstance(request.param, cls):
            return request.param

        return cls()


class CaptureTransport(sentry_sdk.Transport):
    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


@pytest.fixture
def sentry_events(request):
    params = ClientParams.from_request(request)
    transport = CaptureTransport()
    client = sentry_sdk.Client(
        transport=transport,
        integrations=INTEGRATIONS,
        auto_enabling_integrations=False,
        include_local_variables=params.include_local_variables,
    )

    with sentry_sdk.isolation_scope() as scope:
        scope.set_client(client)
        yield transport.events


def assert_event_dict(event_data, sentry_events, number_of_events=1, error=None):
    assert len(sentry_events) == number_of_events
    assert event_data["level"] == sentry_events[0]["level"]
    assert event_data["event"] == sentry_events[0]["message"]

    if error is not None:
        assert sentry_events[0]["exception"]["values"][0]["type"] == error.__name__


class MockLogger:
    def __init__(self, name):
        self.name = name


def test_sentry_disabled():
    processor = SentryProcessor(active=False, verbose=True)
    event_dict = processor(None, None, {"level": "error"})
    assert event_dict.get("sentry") != "sent"


def test_sentry_skip():
    processor = SentryProcessor(verbose=True)
    event_dict = processor(None, None, {"sentry_skip": True, "level": "error"})
    assert event_dict.get("sentry") == "skipped"


def test_sentry_sent():
    processor = SentryProcessor(verbose=True)
    event_dict = processor(None, None, {"level": "error"})
    assert event_dict.get("sentry") == "sent"


@pytest.mark.parametrize(
    "level, level_value",
    [
        (CUSTOM_LOG_LEVEL_NAME, CUSTOM_LOG_LEVEL_VALUE),
        ("debug", logging.DEBUG),
        ("info", logging.INFO),
        ("warning", logging.WARNING),
    ],
)
def test_sentry_log(sentry_events, level, level_value):
    event_data = {"level": level, "event": level + " message"}

    processor = SentryProcessor(event_level=level_value)
    processor(None, None, event_data)

    assert_event_dict(event_data, sentry_events)


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_sentry_log_only_errors(sentry_events, level):
    processor_only_errors = SentryProcessor(event_level=logging.ERROR, verbose=True)
    event_dict = processor_only_errors(
        None, None, {"level": level, "event": level + " message"}
    )
    assert not sentry_events
    assert event_dict["sentry"] == "skipped"


@pytest.mark.parametrize("level", ["error", "critical"])
def test_sentry_log_failure(sentry_events, level):
    """Make sure that events without exc_info=True will have no
    'exception' information after processing
    """
    event_data = {"level": level, "event": level + " message"}
    processor = SentryProcessor(event_level=getattr(logging, level.upper()))
    try:
        1 / 0
    except ZeroDivisionError:
        processor(None, None, event_data)

    assert_event_dict(event_data, sentry_events)


@pytest.mark.parametrize("level", ["error", "critical"])
def test_sentry_log_failure_exc_info_true(sentry_events, level):
    """Make sure sentry_sdk.utils.exc_info_from_error doesn't raise ValueError
    Because it can't introspect exc_info.
    Bug triggered when logger.error(..., exc_info=True) or logger.exception(...)
    are used.
    """
    event_data = {"level": level, "event": level + " message", "exc_info": True}
    processor = SentryProcessor(event_level=getattr(logging, level.upper()))
    try:
        1 / 0
    except ZeroDivisionError:
        processor(None, None, event_data)

    assert_event_dict(event_data, sentry_events, error=ZeroDivisionError)


absent = object()


@pytest.mark.parametrize("logger", ["some.logger.name", absent])
def test_sentry_add_logger_name(sentry_events, logger):
    event_data = {"level": "warning", "event": "some.event"}
    if logger is not absent:
        event_data["logger"] = logger

    processor = SentryProcessor(as_context=False)
    processor(None, None, event_data)

    assert_event_dict(event_data, sentry_events)

    if logger is not absent:
        assert event_data["logger"] == sentry_events[0]["logger"]


def test_sentry_log_leave_exc_info_untouched(sentry_events):
    """Make sure exc_info remains in event_data at the end of the processor.

    The structlog built-in format_exc_info processor pops the key and formats
    it. Using SentryProcessor, and format_exc_info wasn't possible before,
    because the latter one didn't have an exc_info to work with.

    https://github.com/kiwicom/structlog-sentry/issues/16
    """
    event_data = {"level": "warning", "event": "some.event", "exc_info": True}
    processor = SentryProcessor(as_context=True)
    try:
        1 / 0
    except ZeroDivisionError:
        processor(None, None, event_data)

    assert "exc_info" in event_data


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_sentry_log_all_as_tags(sentry_events, level):
    event_data = {"level": level, "event": level + " message"}
    processor = SentryProcessor(
        event_level=getattr(logging, level.upper()), tag_keys="__all__"
    )
    processor(None, None, event_data)

    assert_event_dict(event_data, sentry_events)
    assert event_data["level"] == sentry_events[0]["tags"]["level"]
    assert event_data["event"] == sentry_events[0]["tags"]["event"]
    assert event_data["level"] == sentry_events[0]["contexts"]["structlog"]["level"]
    assert event_data["event"] == sentry_events[0]["contexts"]["structlog"]["event"]


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_sentry_log_specific_keys_as_tags(sentry_events, level):
    event_data = {
        "level": level,
        "event": level + " message",
        "info1": "info1",
        "required": True,
    }
    tag_keys = ["info1", "required", "some non existing key"]
    processor = SentryProcessor(
        event_level=getattr(logging, level.upper()), tag_keys=tag_keys
    )
    processor(None, None, event_data)

    assert_event_dict(event_data, sentry_events)
    assert sentry_events[0]["tags"] == {
        k: event_data[k] for k in tag_keys if k in event_data
    }


def test_sentry_get_logger_name():
    event_data = {
        "level": "info",
        "event": "message",
        "logger": "EventLogger",
        "_record": MockLogger("RecordLogger"),
    }
    assert (
        SentryProcessor._get_logger_name(logger=None, event_dict=event_data)
        == "EventLogger"
    )

    event_data = {
        "level": "info",
        "event": "message",
        "_record": MockLogger("RecordLogger"),
    }
    assert (
        SentryProcessor._get_logger_name(logger=None, event_dict=event_data)
        == "RecordLogger"
    )

    event_data = {
        "level": "info",
        "event": "message",
    }
    assert (
        SentryProcessor._get_logger_name(
            logger=MockLogger("EventLogger"), event_dict=event_data
        )
        == "EventLogger"
    )


@pytest.mark.parametrize("level", ["debug", "info", "warning", "error", "critical"])
def test_sentry_ignore_logger(sentry_events, level):
    blacklisted_logger = MockLogger("test.blacklisted")
    whitelisted_logger = MockLogger("test.whitelisted")
    processor = SentryProcessor(
        event_level=getattr(logging, level.upper()),
        ignore_loggers=["test.blacklisted"],
        verbose=True,
    )

    event_data = {"level": level, "event": level + " message"}

    blacklisted_logger_event_dict = processor(
        blacklisted_logger, None, event_data.copy()
    )
    whitelisted_logger_event_dict = processor(
        whitelisted_logger, None, event_data.copy()
    )

    assert_event_dict(event_data, sentry_events)
    assert blacklisted_logger_event_dict.get("sentry") == "ignored"
    assert whitelisted_logger_event_dict.get("sentry") != "ignored"


@pytest.mark.parametrize(
    "sentry_events", [{"include_local_variables": False}], indirect=True
)
def test_sentry_json_respects_global_with_locals_option_no_locals(sentry_events):
    processor = SentryProcessor()
    try:
        1 / 0
    except ZeroDivisionError:
        processor(None, None, {"level": "error", "exc_info": True})

    for event in sentry_events:
        for frame in event["exception"]["values"][0]["stacktrace"]["frames"]:
            assert "vars" not in frame  # No local variables were captured


@pytest.mark.parametrize(
    "sentry_events", [{"include_local_variables": True}], indirect=True
)
def test_sentry_json_respects_global_with_locals_option_with_locals(sentry_events):
    processor = SentryProcessor()
    try:
        1 / 0
    except ZeroDivisionError:
        processor(None, None, {"level": "error", "exc_info": True})

    for event in sentry_events:
        for frame in event["exception"]["values"][0]["stacktrace"]["frames"]:
            assert "vars" in frame  # Local variables were captured


base_info_log = {
    "level": "info",
    "event": "Info message",
    "logger": "EventLogger",
    "timestamp": "2024-01-01T00:00:00Z",
}
base_error_log = {
    "level": "error",
    "event": "Error message",
}


def test_breadcrumbs_with_additional_data(sentry_events):
    processor = SentryProcessor(verbose=True)
    processor(None, None, {**base_info_log, **{"foo": "bar"}})
    processor(None, None, base_error_log)
    print({**base_info_log, **{"foo": "bar"}})
    breadcrumbs = sentry_events[0]["breadcrumbs"]["values"]
    del breadcrumbs[0]["timestamp"]
    assert breadcrumbs[0] == {
        "type": "log",
        "level": "info",
        "category": "EventLogger",
        "message": "Info message",
        "data": {"foo": "bar"},
    }


def test_breadcrumbs_with_custom_exclusions(sentry_events):
    processor = SentryProcessor(verbose=True, ignore_breadcrumb_data=["foo"])
    processor(None, None, {**base_info_log, **{"foo": "bar"}})
    processor(None, None, base_error_log)

    breadcrumbs = sentry_events[0]["breadcrumbs"]["values"]

    del breadcrumbs[0]["timestamp"]
    assert breadcrumbs[0] == {
        "type": "log",
        "level": "info",
        "category": "EventLogger",
        "message": "Info message",
        "data": {
            "level": "info",
            "event": "Info message",
            "logger": "EventLogger",
            "timestamp": "2024-01-01T00:00:00Z",
        },
    }


def test_breadcrumbs_with_no_additional_data(sentry_events):
    processor = SentryProcessor(verbose=True)
    processor(None, None, base_info_log)
    processor(None, None, base_error_log)

    breadcrumbs = sentry_events[0]["breadcrumbs"]["values"]

    assert len(breadcrumbs) == 1
    assert isinstance(breadcrumbs[0]["timestamp"], str)
    del breadcrumbs[0]["timestamp"]
    assert breadcrumbs[0] == {
        "type": "log",
        "level": "info",
        "category": "EventLogger",
        "message": "Info message",
        "data": {},
    }
