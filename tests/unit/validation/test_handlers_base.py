import pytest

from rubem.validation.handlers.base import BaseValidatorHandler, Handler


class RecordingHandler(BaseValidatorHandler):
    """A concrete handler that records the request it received and appends an error."""

    def __init__(self):
        super().__init__()
        self.received_request = None

    def handle(self, request, errors):
        self.received_request = request
        errors.append("recorded")
        return "recorded-result"


class TestHandler:
    @pytest.mark.unit
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            Handler()


class TestBaseValidatorHandler:
    @pytest.mark.unit
    def test_set_next_returns_given_handler(self):
        handler = BaseValidatorHandler()
        next_handler = BaseValidatorHandler()

        result = handler.set_next(next_handler)

        assert result is next_handler

    @pytest.mark.unit
    def test_set_next_allows_chaining(self):
        first = BaseValidatorHandler()
        second = BaseValidatorHandler()
        third = BaseValidatorHandler()

        result = first.set_next(second).set_next(third)

        assert result is third

    @pytest.mark.unit
    def test_handle_without_next_returns_true_and_leaves_errors_untouched(self):
        handler = BaseValidatorHandler()
        errors = []

        result = handler.handle("request", errors)

        assert result is True
        assert errors == []

    @pytest.mark.unit
    def test_handle_delegates_to_next_handler(self):
        handler = BaseValidatorHandler()
        next_handler = RecordingHandler()
        handler.set_next(next_handler)
        errors = []

        result = handler.handle("request", errors)

        assert result == "recorded-result"
        assert next_handler.received_request == "request"
        assert errors == ["recorded"]
