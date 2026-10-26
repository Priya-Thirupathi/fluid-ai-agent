import logging
import os
from functools import cache
from typing import TypeVar

from dotenv import load_dotenv
from groq import APIError, AsyncGroq
from pydantic import BaseModel, ValidationError

load_dotenv()

logger = logging.getLogger(__name__)

PRIMARY_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when every model failed to return a valid response."""


@cache
def get_client() -> AsyncGroq:
    # Created on first use, so tests can swap in a fake without an API key.
    return AsyncGroq(timeout=LLM_TIMEOUT_SECONDS)


async def ask_json(system: str, user: str, schema: type[T]) -> T:
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            response = await get_client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )
            return schema.model_validate_json(response.choices[0].message.content)
        except (APIError, ValidationError) as error:
            logger.warning("Model %s failed: %s", model, error)
    raise LLMError("All models failed to return a valid response")
