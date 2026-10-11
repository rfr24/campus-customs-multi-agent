"""Model wiring for the Campus Customs agent team.

HW5 requires every agent to run on `gpt-6-luna` through Portkey. This module is
the only place that builds a model, so no agent can quietly use a different one.

The API key is read from the environment (or a local .env) and is never
hard-coded, printed, logged, or written into the audit trail.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# gpt-6-luna rejects function tools on /v1/chat/completions unless reasoning is
# disabled ("Function tools with reasoning_effort are not supported ... use
# /v1/responses"). Since every agent in this project is tool-driven, the model
# is built on the Responses API instead of giving up the model's reasoning.
USE_RESPONSES_API = True

# A Boss request fans out to several specialists, each making multiple tool
# calls on a reasoning model, so a single HTTP call can legitimately run for
# minutes. The SDK default is far too tight for that and surfaces as
# "Request timed out" mid-delegation.
REQUEST_TIMEOUT_SECONDS = 600.0
MAX_RETRIES = 2

# HW5 allows exactly one model. Not configurable by design: a silent
# substitution would invalidate the assignment.
REQUIRED_MODEL = "gpt-6-luna"


class CredentialsUnavailable(RuntimeError):
    """Raised when PORTKEY_API_KEY is not configured."""


def load_api_key() -> str:
    """Read PORTKEY_API_KEY from the environment, falling back to a local .env."""
    if not os.environ.get("PORTKEY_API_KEY"):
        for candidate in (PROJECT_ROOT / ".env", *(p / ".env" for p in PROJECT_ROOT.parents)):
            if candidate.is_file():
                load_dotenv(candidate)
                if os.environ.get("PORTKEY_API_KEY"):
                    break
    key = os.environ.get("PORTKEY_API_KEY")
    if not key:
        raise CredentialsUnavailable(
            "PORTKEY_API_KEY is not set. Export it or add it to a .env file at the "
            "project root; it must never be hard-coded."
        )
    return key


def credentials_available() -> bool:
    """True if a Portkey key can be found, without revealing anything about it."""
    try:
        load_api_key()
    except CredentialsUnavailable:
        return False
    return True


def build_model(model_name: str = REQUIRED_MODEL) -> OpenAIResponsesModel:
    """Build the Portkey-served model. Refuses anything but the required model."""
    if model_name != REQUIRED_MODEL:
        raise RuntimeError(
            f"HW5 requires {REQUIRED_MODEL!r}; refusing to build {model_name!r}."
        )
    key = load_api_key()
    client = AsyncOpenAI(
        base_url=PORTKEY_BASE_URL,
        api_key=key,
        default_headers={"x-portkey-api-key": key},
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )
    return OpenAIResponsesModel(model_name, provider=OpenAIProvider(openai_client=client))
