import logging

import pytest

from structlog_sentry import SentryProcessor


def test_sentry_disabled():
    processor = SentryProcessor(active=False)
    event_dict = processor(None, None, {"level": "error"})
    assert event_dict.get("sentry") != "sent"


def test_sentry_skip():
    processor = SentryProcessor()
    event_dict = processor(None, None, {"sentry_skip": True, "level": "error"})
    assert event_dict.get("sentry") != "sent"


def test_sentry_sent():
    processor = SentryProcessor()
    event_dict = processor(None, None, {"level": "error"})
    assert event_dict.get("sentry") == "sent"


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_sentry_log(mocker, level):
    m_capture_event = mocker.patch("structlog_sentry.capture_event")

    event_data = {"level": level, "event": level + " message"}
    processor = SentryProcessor(level=getattr(logging, level.upper()))
    processor(None, None, event_data)

    m_capture_event.assert_called_once_with(
        {
            "level": level,
            "message": event_data["event"],
            "extra": event_data,
        },
        hint=None,
    )

    processor_only_errors = SentryProcessor(level=logging.ERROR)
    event_dict = processor_only_errors(
        None, None, {"level": level, "event": level + " message"}
    )

    assert event_dict.get("sentry") != "sent"


@pytest.mark.parametrize("level", ["error", "critical"])
def test_sentry_log_failure(mocker, level):
    m_capture_event = mocker.patch("structlog_sentry.capture_event")
    mocker.patch(
        "structlog_sentry.event_from_exception",
        return_value=({"exception": mocker.sentinel.exception}, mocker.sentinel.hint),
    )

    event_data = {"level": level, "event": level + " message"}
    processor = SentryProcessor(level=getattr(logging, level.upper()))
    try:
        1 / 0
    except ZeroDivisionError:
        processor(None, None, event_data)

    m_capture_event.assert_called_once_with(
        {
            "level": level,
            "message": event_data["event"],
            "exception": mocker.sentinel.exception,
            "extra": event_data,
        },
        hint=mocker.sentinel.hint,
    )
