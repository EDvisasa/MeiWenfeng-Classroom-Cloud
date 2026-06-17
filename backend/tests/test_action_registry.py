import unittest
from unittest.mock import MagicMock

from backend.services.response_pipeline import ResponsePipeline, TagStreamInterceptor
from backend.services.action_registry import ActionRegistry, SideEffectHandler

class MockHandler(SideEffectHandler):
    def __init__(self):
        self.called_with = []

    def handle(self, attrs: dict, content: str):
        self.called_with.append((attrs, content))

class TestActionRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = ActionRegistry()
        self.mock_handler = MockHandler()
        self.registry.register("mock_tag", self.mock_handler)

    def test_registry_registration(self):
        """Test that handlers can be registered and retrieved."""
        self.assertEqual(self.registry.get_handler("mock_tag"), self.mock_handler)
        self.assertIsNone(self.registry.get_handler("nonexistent"))

    def test_registry_get_all_tags(self):
        """Test getting all registered tags for the interceptor."""
        tags = self.registry.get_all_tags()
        self.assertIn("mock_tag", tags)

    def test_pipeline_integration(self):
        """Test that ResponsePipeline uses the registry to dispatch events."""
        pipeline = ResponsePipeline(registry=self.registry)

        # Simulate intercepted data
        pipeline.interceptor.intercepted_data = {
            "mock_tag": [{"attrs": {"key": "value"}, "content": "mock content"}]
        }

        # Execute side effects
        pipeline._execute_side_effects("")

        # Verify handler was called
        self.assertEqual(len(self.mock_handler.called_with), 1)
        self.assertEqual(self.mock_handler.called_with[0][0], {"key": "value"})
        self.assertEqual(self.mock_handler.called_with[0][1], "mock content")

if __name__ == '__main__':
    unittest.main()