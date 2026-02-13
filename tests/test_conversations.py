"""Unit tests for conversation storage."""

import json

import pytest
from pathlib import Path

from geofix.storage.conversations import ConversationStore


@pytest.fixture
def store(tmp_dir):
    s = ConversationStore(tmp_dir / "test_conv.db")
    yield s
    s.close()


class TestConversationStore:
    def test_create_conversation(self, store):
        conv_id = store.create_conversation("Test Chat")
        assert conv_id is not None
        assert len(conv_id) > 0

    def test_add_and_get_messages(self, store):
        conv_id = store.create_conversation()
        store.add_message(conv_id, "user", "Hello")
        store.add_message(conv_id, "assistant", "Hi there!")

        messages = store.get_messages(conv_id)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_auto_title_from_first_message(self, store):
        conv_id = store.create_conversation()
        store.add_message(conv_id, "user", "What is topology?")

        convs = store.list_conversations()
        assert convs[0]["title"] == "What is topology?"

    def test_list_conversations(self, store):
        store.create_conversation("Chat 1")
        store.create_conversation("Chat 2")

        convs = store.list_conversations()
        assert len(convs) == 2

    def test_search_conversations(self, store):
        conv_id = store.create_conversation()
        store.add_message(conv_id, "user", "How do I fix overlapping polygons?")

        results = store.search_conversations("overlapping")
        assert len(results) == 1

    def test_search_no_results(self, store):
        conv_id = store.create_conversation()
        store.add_message(conv_id, "user", "Hello world")

        results = store.search_conversations("nonexistent_term")
        assert len(results) == 0

    def test_export_markdown(self, store):
        conv_id = store.create_conversation("Export Test")
        store.add_message(conv_id, "user", "Question")
        store.add_message(conv_id, "assistant", "Answer")

        md = store.export_conversation(conv_id, fmt="markdown")
        # Auto-title overwrites with first user message
        assert "Question" in md
        assert "### User" in md
        assert "### GeoFix" in md
        assert "Answer" in md

    def test_export_json(self, store):
        conv_id = store.create_conversation("JSON Test")
        store.add_message(conv_id, "user", "Hello")

        output = store.export_conversation(conv_id, fmt="json")
        data = json.loads(output)
        # Auto-title overwrites initial title with first user message
        assert data["conversation"]["title"] == "Hello"
        assert any(m["content"] == "Hello" for m in data["messages"])

    def test_delete_conversation(self, store):
        conv_id = store.create_conversation()
        store.add_message(conv_id, "user", "temp message")

        store.delete_conversation(conv_id)
        convs = store.list_conversations()
        assert len(convs) == 0

    def test_get_stats(self, store):
        conv_id = store.create_conversation()
        store.add_message(conv_id, "user", "Hello", tokens_used=10, processing_time=0.5)
        store.add_message(conv_id, "assistant", "Hi!", tokens_used=5, processing_time=0.3)

        stats = store.get_stats(conv_id)
        assert stats["message_count"] == 2
        assert stats["total_tokens"] == 15
