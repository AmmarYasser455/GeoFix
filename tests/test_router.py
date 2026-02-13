"""Unit tests for the model router."""

from geofix.core.router import Complexity, classify_complexity, select_model


class TestClassifyComplexity:
    def test_greeting_is_simple(self):
        assert classify_complexity("hello") == Complexity.SIMPLE
        assert classify_complexity("Hi there") == Complexity.SIMPLE
        assert classify_complexity("hey") == Complexity.SIMPLE

    def test_short_question_is_simple(self):
        assert classify_complexity("what is GIS") == Complexity.SIMPLE
        assert classify_complexity("define topology") == Complexity.SIMPLE

    def test_yes_no_is_simple(self):
        assert classify_complexity("yes") == Complexity.SIMPLE
        assert classify_complexity("ok") == Complexity.SIMPLE

    def test_technical_is_medium(self):
        assert classify_complexity(
            "How does the overlap detection algorithm handle edge cases?"
        ) == Complexity.MEDIUM

    def test_code_generation_is_complex(self):
        assert classify_complexity(
            "Write a Python script to merge overlapping polygons using geopandas"
        ) == Complexity.COMPLEX

    def test_analysis_is_complex(self):
        assert classify_complexity(
            "Analyze the trade-offs between different topology correction strategies"
        ) == Complexity.COMPLEX

    def test_long_query_is_complex(self):
        long_query = " ".join(["word"] * 60)
        assert classify_complexity(long_query) == Complexity.COMPLEX

    def test_long_history_promotes_complexity(self):
        result = classify_complexity("Tell me more about that", history_len=15)
        assert result == Complexity.COMPLEX


class TestSelectModel:
    def test_auto_routing(self):
        assert select_model("hi") == "llama3.2"
        assert select_model("write a script to fix overlaps") == "deepseek-r1:14b"

    def test_user_override(self):
        assert select_model("hi", user_override="llama3.1:8b") == "llama3.1:8b"
        assert select_model(
            "complex question", user_override="llama3.2"
        ) == "llama3.2"
