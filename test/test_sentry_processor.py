import logging

import pytest

from structlog_sentry import SentryJsonProcessor, SentryProcessor


class MockLogger:
    def __init__(self, name):
        self.name = name


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
    sentry_event_data = event_data.copy()
    processor = SentryProcessor(level=getattr(logging, level.upper()))
    processor(None, None, event_data)

    m_capture_event.assert_called_once_with(
        {"level": level, "message": event_data["event"], "extra": sentry_event_data},
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
    sentry_event_data = event_data.copy()
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
            "extra": sentry_event_data,
        },
        hint=mocker.sentinel.hint,
    )


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_sentry_log_no_extra(mocker, level):
    m_capture_event = mocker.patch("structlog_sentry.capture_event")

    event_data = {"level": level, "event": level + " message"}
    processor = SentryProcessor(level=getattr(logging, level.upper()), as_extra=False)
    processor(None, None, event_data)

    m_capture_event.assert_called_once_with(
        {"level": level, "message": event_data["event"]}, hint=None
    )

    processor_only_errors = SentryProcessor(level=logging.ERROR)
    event_dict = processor_only_errors(
        None, None, {"level": level, "event": level + " message"}
    )

    assert event_dict.get("sentry") != "sent"


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_sentry_log_all_as_tags(mocker, level):
    m_capture_event = mocker.patch("structlog_sentry.capture_event")

    event_data = {"level": level, "event": level + " message"}
    sentry_event_data = event_data.copy()
    processor = SentryProcessor(
        level=getattr(logging, level.upper()), tag_keys="__all__"
    )
    processor(None, None, event_data)

    m_capture_event.assert_called_once_with(
        {
            "level": level,
            "message": event_data["event"],
            "extra": sentry_event_data,
            "tags": sentry_event_data,
        },
        hint=None,
    )

    processor_only_errors = SentryProcessor(level=logging.ERROR)
    event_dict = processor_only_errors(
        None, None, {"level": level, "event": level + " message"}
    )

    assert event_dict.get("sentry") != "sent"


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_sentry_log_specific_keys_as_tags(mocker, level):
    m_capture_event = mocker.patch("structlog_sentry.capture_event")

    event_data = {
        "level": level,
        "event": level + " message",
        "info1": "info1",
        "required": True,
    }
    tag_keys = ["info1", "required", "some non existing key"]
    sentry_event_data = event_data.copy()
    processor = SentryProcessor(
        level=getattr(logging, level.upper()), tag_keys=tag_keys
    )
    processor(None, None, event_data)

    m_capture_event.assert_called_once_with(
        {
            "level": level,
            "message": event_data["event"],
            "extra": sentry_event_data,
            "tags": {
                k: sentry_event_data[k] for k in tag_keys if k in sentry_event_data
            },
        },
        hint=None,
    )

    processor_only_errors = SentryProcessor(level=logging.ERROR)
    event_dict = processor_only_errors(
        None, None, {"level": level, "event": level + " message"}
    )

    assert event_dict.get("sentry") != "sent"


def test_sentry_json_ignore_logger_using_event_dict_logger_name(mocker):
    m_ignore_logger = mocker.patch("structlog_sentry.ignore_logger")
    m_logger = MockLogger("MockLogger")
    event_data = {
        "level": "info",
        "event": "message",
        "logger": "EventLogger",
        "_record": MockLogger("RecordLogger"),
    }
    processor = SentryJsonProcessor()

    assert not processor._ignored
    processor._ignore_logger(logger=m_logger, event_dict=event_data)
    m_ignore_logger.assert_called_once_with(event_data["logger"])
    assert event_data["logger"] in processor._ignored


def test_sentry_json_ignore_logger_using_event_dict_record(mocker):
    m_ignore_logger = mocker.patch("structlog_sentry.ignore_logger")
    m_logger = MockLogger("MockLogger")
    event_data = {
        "level": "info",
        "event": "message",
        "_record": MockLogger("RecordLogger"),
    }
    processor = SentryJsonProcessor()

    assert not processor._ignored
    processor._ignore_logger(logger=m_logger, event_dict=event_data)
    m_ignore_logger.assert_called_once_with(event_data["_record"].name)
    assert event_data["_record"].name in processor._ignored


def test_sentry_json_ignore_logger_using_logger_instance_name(mocker):
    m_ignore_logger = mocker.patch("structlog_sentry.ignore_logger")
    m_logger = MockLogger("MockLogger")
    event_data = {"level": "info", "event": "message"}
    processor = SentryJsonProcessor()

    assert not processor._ignored
    processor._ignore_logger(logger=m_logger, event_dict=event_data)
    m_ignore_logger.assert_called_once_with(m_logger.name)
    assert m_logger.name in processor._ignored


def test_sentry_json_call_ignores_logger_once(mocker):
    processor = SentryJsonProcessor()
    m_ignore_logger = mocker.patch("structlog_sentry.ignore_logger")
    event_data = {"level": "warning", "event": "message", "sentry_skip": True}
    logger = MockLogger("MockLogger")
    processor(logger, None, event_data)
    processor(logger, None, event_data)
    processor(logger, None, event_data)
    m_ignore_logger.assert_called_once_with(logger.name)


def test_sentry_json_ignores_multiple_loggers_once(mocker):
    processor = SentryJsonProcessor()
    m_ignore_logger = mocker.patch("structlog_sentry.ignore_logger")
    event_data = {"level": "warning", "event": "message", "sentry_skip": True}
    logger = MockLogger("MockLogger")
    logger2 = MockLogger("MockLogger2")
    processor(logger, None, event_data)
    processor(logger, None, event_data)
    processor(logger, None, event_data)
    m_ignore_logger.assert_called_once_with(logger.name)
    m_ignore_logger.reset_mock()
    processor(logger2, None, event_data)
    processor(logger2, None, event_data)
    processor(logger2, None, event_data)
    m_ignore_logger.assert_called_once_with(logger2.name)
