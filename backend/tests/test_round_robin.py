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
    """Verify loading of 30 Gemini API keys from environment."""
    reset_round_robin()
    keys = get_all_gemini_api_keys()
    assert len(keys) >= 30
    assert keys[0] == "DUMMY_KEY_ROUND_ROBIN_TEST_1"
    assert keys[29] == "DUMMY_KEY_ROUND_ROBIN_TEST_2"


def test_round_robin_rotation():
    """Verify sequential round-robin rotation across 30 keys."""
    reset_round_robin()
    keys = get_all_gemini_api_keys()
    num_keys = len(keys)

    # First cycle
    for i in range(num_keys):
        k = get_next_gemini_api_key()
        assert k == keys[i]

    # Wraparound check
    k_wrap = get_next_gemini_api_key()
    assert k_wrap == keys[0]


def test_set_gemini_api_key_env():
    """Verify environment variable update during round-robin selection."""
    reset_round_robin()
    k1 = set_gemini_api_key_env()
    assert os.environ.get("GEMINI_API_KEY") == k1
    assert os.environ.get("GOOGLE_API_KEY") == k1

    k2 = set_gemini_api_key_env()
    assert os.environ.get("GEMINI_API_KEY") == k2
    assert k1 != k2 or len(get_all_gemini_api_keys()) == 1
