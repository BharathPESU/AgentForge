"""Tests for AgentForge Round-Robin Gemini API Key Manager."""

import os
import pytest
from backend.roundRobin import (
    get_all_gemini_api_keys,
    get_next_gemini_api_key,
    reset_round_robin,
    set_gemini_api_key_env,
)


def test_load_all_keys():
    """Verify loading of Gemini API keys from environment."""
    reset_round_robin()
    keys = get_all_gemini_api_keys()
    assert isinstance(keys, list)


def test_round_robin_rotation(monkeypatch):
    """Verify sequential round-robin rotation across keys."""
    monkeypatch.setenv("GEMINI_API_KEY1", "MOCK_KEY_ALPHA")
    monkeypatch.setenv("GEMINI_API_KEY2", "MOCK_KEY_BETA")
    reset_round_robin()
    keys = get_all_gemini_api_keys()
    assert len(keys) >= 2

    k1 = get_next_gemini_api_key()
    assert k1 == "MOCK_KEY_ALPHA"
    k2 = get_next_gemini_api_key()
    assert k2 == "MOCK_KEY_BETA"

    # Wraparound check
    k_wrap = get_next_gemini_api_key()
    assert k_wrap == "MOCK_KEY_ALPHA"


def test_set_gemini_api_key_env(monkeypatch):
    """Verify environment variable update during round-robin selection."""
    monkeypatch.setenv("GEMINI_API_KEY1", "MOCK_KEY_ALPHA")
    monkeypatch.setenv("GEMINI_API_KEY2", "MOCK_KEY_BETA")
    reset_round_robin()
    k1 = set_gemini_api_key_env()
    assert os.environ.get("GEMINI_API_KEY") == k1
    assert os.environ.get("GOOGLE_API_KEY") == k1

    k2 = set_gemini_api_key_env()
    assert os.environ.get("GEMINI_API_KEY") == k2
    assert k1 != k2
