import logging
from abc import ABC, abstractmethod


class Handler(ABC):
    """Abstract base class for handlers."""

    @abstractmethod
    def set_next(self, handler):
        """Set the next handler in the chain."""
        pass

    @abstractmethod
    def handle(self, request):
        """Handle the request."""
        pass


class BaseValidatorHandler(Handler):
    """Base class for validator handlers."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.__next: Handler = None

    def set_next(self, handler: Handler) -> Handler:
        """Set the next handler in the chain."""
        self.__next = handler
        return handler

    def handle(self, request):
        """Handle the request by passing it to the next handler in the chain."""
        if self.__next:
            return self.__next.handle(request)
        return True  # Fallback validator: always return True
