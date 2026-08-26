"""Round-robin Gemini API key manager for AgentForge to prevent rate limits."""

import os
import threading
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

_lock = threading.Lock()
_current_index = 0
_cached_keys: Optional[List[str]] = None


def _load_keys() -> List[str]:
    """Discover and return all configured Gemini API keys from environment."""
    global _cached_keys
    load_dotenv()

    keys = []
    # Collect keys named GEMINI_API_KEY1 to GEMINI_API_KEY30
    for i in range(1, 31):
        key = os.getenv(f"GEMINI_API_KEY{i}")
        if key and key.strip():
            keys.append(key.strip())

    # Fallback to standard environment keys if GEMINI_API_KEY1..30 not found
    if not keys:
        for env_name in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
            val = os.getenv(env_name)
            if val and val.strip():
                keys.append(val.strip())

    _cached_keys = keys
    return keys


def get_all_gemini_api_keys() -> List[str]:
    """Get list of all loaded Gemini API keys."""
    global _cached_keys
    if _cached_keys is None:
        _load_keys()
    return _cached_keys or []


def get_next_gemini_api_key() -> str:
    """Return the next Gemini API key in round-robin order."""
    global _current_index, _cached_keys
    with _lock:
        keys = get_all_gemini_api_keys()
        if not keys:
            # Fallback placeholder if no keys are found
            return os.getenv("GEMINI_API_KEY", "")

        key = keys[_current_index % len(keys)]
        _current_index = (_current_index + 1) % len(keys)
        return key


def set_gemini_api_key_env() -> str:
    """Select the next round-robin key and update environment variables."""
    key = get_next_gemini_api_key()
    if key:
        os.environ["GEMINI_API_KEY"] = key
        os.environ["GOOGLE_API_KEY"] = key
    return key


def reset_round_robin():
    """Reset round-robin counter and force key reload."""
    global _current_index, _cached_keys
    with _lock:
        _current_index = 0
        _cached_keys = None
        _load_keys()
