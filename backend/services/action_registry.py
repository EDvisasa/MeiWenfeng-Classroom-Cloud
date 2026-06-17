import logging
from typing import Dict, Any, Callable
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class SideEffectHandler(ABC):
    """Base class for all side-effect handlers."""

    @abstractmethod
    def handle(self, attrs: Dict[str, Any], content: str) -> None:
        """Process the intercepted XML tag."""
        pass

class ActionRegistry:
    """An application-level singleton registry for side-effect handlers."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ActionRegistry, cls).__new__(cls)
            cls._instance.handlers = {}
        return cls._instance

    def register(self, tag_name: str, handler: SideEffectHandler) -> None:
        """Register a handler for a specific tag name."""
        self.handlers[tag_name] = handler

    def get_handler(self, tag_name: str) -> SideEffectHandler:
        """Get the handler for a specific tag name."""
        return self.handlers.get(tag_name)

    def get_all_tags(self) -> list:
        """Get a list of all registered tag names."""
        return list(self.handlers.keys())

# Global singleton instance
action_registry = ActionRegistry()