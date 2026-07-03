"""Load API credentials and model settings from the environment.

The detective and suspect use separate settings so they can point at different
models or OpenAI-compatible endpoints when needed.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Detective (asks questions, parses testimony, writes case file) ──────────
DETECTIVE = {
    "base_url":   os.getenv("DETECTIVE_BASE_URL", "https://api.groq.com/openai/v1"),
    "api_key":    os.getenv("DETECTIVE_API_KEY") or os.getenv("OPENROUTER_API_KEY") or "missing-key",
    "model_name": os.getenv("DETECTIVE_MODEL", "openai/gpt-oss-120b"),
}

# ── Suspect (role-plays the character being interrogated) ───────────────────
SUSPECT = {
    "base_url":   os.getenv("SUSPECT_BASE_URL", "https://api.groq.com/openai/v1"),
    "api_key":    os.getenv("SUSPECT_API_KEY") or os.getenv("OPENROUTER_API_KEY") or "missing-key",
    "model_name": os.getenv("SUSPECT_MODEL", "openai/gpt-oss-120b"),
}