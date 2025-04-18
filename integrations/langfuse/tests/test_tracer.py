# SPDX-FileCopyrightText: 2023-present deepset GmbH <info@deepset.ai>
#
# SPDX-License-Identifier: Apache-2.0

import datetime
import logging
import sys
from unittest.mock import MagicMock, Mock, patch

from haystack.dataclasses import ChatMessage
from haystack_integrations.tracing.langfuse.tracer import LangfuseTracer


class MockSpan:
    def __init__(self):
        self._data = {}
        self._span = self
        self.operation_name = "operation_name"

    def raw_span(self):
        return self

    def span(self, name=None):
        # assert correct operation name passed to the span
        assert name == "operation_name"
        return self

    def update(self, **kwargs):
        self._data.update(kwargs)

    def generation(self, name=None):
        return self

    def end(self):
        pass


class MockTracer:

    def trace(self, name, **kwargs):
        return MockSpan()

    def flush(self):
        pass


class TestLangfuseTracer:

    #  LangfuseTracer can be initialized with a Langfuse instance, a name and a boolean value for public.
    def test_initialization(self):
        langfuse_instance = Mock()
        tracer = LangfuseTracer(tracer=langfuse_instance, name="Haystack", public=True)
        assert tracer._tracer == langfuse_instance
        assert tracer._context == []
        assert tracer._name == "Haystack"
        assert tracer._public

    # check that the trace method is called on the tracer instance with the provided operation name and tags
    # check that the span is added to the context and removed after the context manager exits
    def test_create_new_span(self):
        mock_raw_span = MagicMock()
        mock_raw_span.operation_name = "operation_name"
        mock_raw_span.metadata = {"tag1": "value1", "tag2": "value2"}

        with patch("haystack_integrations.tracing.langfuse.tracer.LangfuseSpan") as MockLangfuseSpan:
            mock_span_instance = MockLangfuseSpan.return_value
            mock_span_instance.raw_span.return_value = mock_raw_span

            mock_context_manager = MagicMock()
            mock_context_manager.__enter__.return_value = mock_span_instance

            mock_tracer = MagicMock()
            mock_tracer.trace.return_value = mock_context_manager

            tracer = LangfuseTracer(tracer=mock_tracer, name="Haystack", public=False)

            with tracer.trace("operation_name", tags={"tag1": "value1", "tag2": "value2"}) as span:
                assert len(tracer._context) == 1, "The trace span should have been added to the the root context span"
                assert span.raw_span().operation_name == "operation_name"
                assert span.raw_span().metadata == {"tag1": "value1", "tag2": "value2"}

            assert (
                len(tracer._context) == 0
            ), "The trace span should have been popped, and the root span is closed as well"

    # check that update method is called on the span instance with the provided key value pairs
    def test_update_span_with_pipeline_input_output_data(self):
        tracer = LangfuseTracer(tracer=MockTracer(), name="Haystack", public=False)
        with tracer.trace(operation_name="operation_name", tags={"haystack.pipeline.input_data": "hello"}) as span:
            assert span.raw_span()._data["metadata"] == {"haystack.pipeline.input_data": "hello"}

        with tracer.trace(operation_name="operation_name", tags={"haystack.pipeline.output_data": "bye"}) as span:
            assert span.raw_span()._data["metadata"] == {"haystack.pipeline.output_data": "bye"}

    def test_trace_generation(self):
        tracer = LangfuseTracer(tracer=MockTracer(), name="Haystack", public=False)
        tags = {
            "haystack.component.type": "OpenAIChatGenerator",
            "haystack.component.output": {
                "replies": [
                    ChatMessage.from_assistant(
                        "", meta={"completion_start_time": "2021-07-27T16:02:08.012345", "model": "test_model"}
                    )
                ]
            },
        }
        with tracer.trace(operation_name="operation_name", tags=tags) as span:
            ...
        assert span.raw_span()._data["usage"] is None
        assert span.raw_span()._data["model"] == "test_model"
        assert span.raw_span()._data["completion_start_time"] == datetime.datetime(2021, 7, 27, 16, 2, 8, 12345)

    def test_trace_generation_invalid_start_time(self):
        tracer = LangfuseTracer(tracer=MockTracer(), name="Haystack", public=False)
        tags = {
            "haystack.component.type": "OpenAIChatGenerator",
            "haystack.component.output": {
                "replies": [
                    ChatMessage.from_assistant("", meta={"completion_start_time": "foobar", "model": "test_model"}),
                ]
            },
        }
        with tracer.trace(operation_name="operation_name", tags=tags) as span:
            ...
        assert span.raw_span()._data["usage"] is None
        assert span.raw_span()._data["model"] == "test_model"
        assert span.raw_span()._data["completion_start_time"] is None

    def test_update_span_gets_flushed_by_default(self):
        tracer_mock = Mock()

        tracer = LangfuseTracer(tracer=tracer_mock, name="Haystack", public=False)
        with tracer.trace(operation_name="operation_name", tags={"haystack.pipeline.input_data": "hello"}) as span:
            pass

        tracer_mock.flush.assert_called_once()

    def test_update_span_flush_disable(self, monkeypatch):
        monkeypatch.setenv("HAYSTACK_LANGFUSE_ENFORCE_FLUSH", "false")
        tracer_mock = Mock()

        from haystack_integrations.tracing.langfuse.tracer import LangfuseTracer

        tracer = LangfuseTracer(tracer=tracer_mock, name="Haystack", public=False)
        with tracer.trace(operation_name="operation_name", tags={"haystack.pipeline.input_data": "hello"}) as span:
            pass

        tracer_mock.flush.assert_not_called()

    def test_context_is_empty_after_tracing(self):
        tracer_mock = Mock()

        tracer = LangfuseTracer(tracer=tracer_mock, name="Haystack", public=False)
        with tracer.trace(operation_name="operation_name", tags={"haystack.pipeline.input_data": "hello"}) as span:
            pass

        assert tracer._context == []

    def test_init_with_tracing_disabled(self, monkeypatch, caplog):
        # Clear haystack modules because ProxyTracer is initialized whenever haystack is imported
        modules_to_clear = [name for name in sys.modules if name.startswith('haystack')]
        for name in modules_to_clear:
            sys.modules.pop(name, None)

        # Re-import LangfuseTracer and instantiate it with tracing disabled
        with caplog.at_level(logging.WARNING):
            monkeypatch.setenv("HAYSTACK_CONTENT_TRACING_ENABLED", "false")
            from haystack_integrations.tracing.langfuse import LangfuseTracer

            LangfuseTracer(tracer=MockTracer(), name="Haystack", public=False)
            assert "tracing is disabled" in caplog.text
