import hashlib
import os
import time
from pathlib import Path
from typing import Type
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors
from pydantic import BaseModel

load_dotenv()

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
_MODEL = "gemini-3.5-flash-lite"

_CACHE_DIR = Path(".llm_cache")
_CACHE_DIR.mkdir(exist_ok=True)

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5


def _cache_key(prompt: str, schema_name: str) -> Path:
    h = hashlib.sha256(f"{_MODEL}|{schema_name}|{prompt}".encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{h}.json"


def _with_retry(fn):
    for attempt in range(_MAX_RETRIES):
        try:
            return fn()
        except errors.ClientError as e:
            if e.code not in _RETRY_STATUSES or attempt == _MAX_RETRIES - 1:
                raise
            wait = min(60, 2 ** (attempt + 2))
            time.sleep(wait)
        except errors.ServerError as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            wait = min(60, 2 ** (attempt + 2))
            time.sleep(wait)


def call_structured(prompt: str, schema: Type[BaseModel]) -> BaseModel:
    cache_path = _cache_key(prompt, schema.__name__)
    if cache_path.exists():
        return schema.model_validate_json(cache_path.read_text())

    def _call():
        return _client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

    response = _with_retry(_call)
    cache_path.write_text(response.text)
    return schema.model_validate_json(response.text)


def call_text(prompt: str) -> str:
    cache_path = _cache_key(prompt, "text")
    if cache_path.exists():
        return cache_path.read_text()

    def _call():
        return _client.models.generate_content(model=_MODEL, contents=prompt)

    response = _with_retry(_call)
    cache_path.write_text(response.text)
    return response.text