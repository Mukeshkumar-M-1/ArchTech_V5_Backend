"""
llm_api_handler.py — CCB-style LLM API Handler for ArchTech.

Mimics the CCB (claude-code-best) architecture for API calls:
1. Provider-based model resolution — Haiku/Sonnet/Opus mapped per provider
2. Lazy client initialization — singleton pattern with env-based routing
3. Retry with exponential backoff — like CCB's withRetry()
4. Non-streaming fallback — on empty/timeout responses
5. Model fallback — Haiku → Sonnet → Opus if one fails
6. Timeout handling — configurable per-call timeout
7. Reasoning loop-back — when content=None, send reasoning back as assistant message
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

log = logging.getLogger(__name__)

# ─── Provider-based model config  ───────────────
PROVIDER_MODEL_MAP = {
    "haiku45": {
        "openai": "qwen2.5-1.5b-instruct-q4_k_m",
    },
    "sonnet46": {
        "openai": "qwen2.5-1.5b-instruct-q4_k_m",
    },
    "opus46": {
        "openai": "qwen2.5-1.5b-instruct-q4_k_m",
    },
}

# Default model fallback chain — like CCB's model fallback on overloaded models
MODEL_FALLBACK_CHAIN = {
    "haiku": ["qwen2.5-1.5b-instruct-q4_k_m"],
    "sonnet": ["qwen2.5-1.5b-instruct-q4_k_m"],
    "opus": ["qwen2.5-1.5b-instruct-q4_k_m"],
}

# ─── Default Settings ─────────────────────────────────────
API_PROVIDER         = "openai"     # API Provider
API_DEFAULT_RETRY_LIMIT    = 0      # SDK Retry calls

DEFAULT_TIMEOUT      = 300          # 5 minutes — your proxy may need this for large requests
DEFAULT_TOKENS       = 4096         # Tokens to generate the context
DEFAULT_TEMPERATURE  = 0.1          # Creativity level
DEFAULT_TOP_P        = 0.9          # Word choosing level

MAX_RETRIES          = 5            # Max Retry
MAX_RETRIES_ON_EMPTY = 5            # additional retries specifically for empty content
MAX_REASONING_LOOPBACK = 5          # max loop-back attempts when content=None, reasoning_content exists

MIN_ATTEMPT = 1
MAX_ATTEMPT = MAX_RETRIES + MAX_RETRIES_ON_EMPTY + 1

# ─── ERROR Retry Control ─────────────────────────────────────
API_RETRY_FLOAT_0_5 = 0.5
API_RETRY_FLOAT_1_0 = 1.0
API_RETRY_FLOAT_2_0 = 2.0
API_2X_INIT         = 2

API_ERROR_EMPTY_SLEEP_TIME_LIMIT = 10.0
API_ERROR_RATE_LIMIT_SLEEP_TIME_LIMIT  = 30.0
API_ERROR_API_TIME_OUT_SLEEP_TIME_LIMIT = 60.0
API_ERROR_SLEEP_TIME_LIMIT = 30.0
API_ERROR_EXCEPTION_SLEEP_TIME_LIMIT = 30.0

# ─── Token Bucket Rate Limiter ────────────────────────────────────
RPM_LIMIT = 30                 # Max requests per minute
RPM_BURST = 5                  # Max burst size (instant calls before pacing)
RPM_REFILL_RATE = RPM_LIMIT / 60  # 0.5 tokens/sec


class _RateLimiter:
    """Token bucket rate limiter for the LLM API.

    Maintains a pool of tokens that refill at a steady rate. Each API call
    consumes one token. When the bucket is empty, callers wait until the
    next refill. The optional *retry_after* parameter lets you inject a 429
    ``Retry-After`` header to force an immediate sleep.
    """

    def __init__(self, rate: float = RPM_REFILL_RATE, burst: int = RPM_BURST):
        self._lock = asyncio.Lock()
        self._tokens: float = burst
        self._max_tokens: float = burst
        self._rate: float = rate
        self._last_refill: float = time.monotonic()
        self._total_calls: int = 0
        self._total_waits: int = 0
        self._total_wait_time: float = 0.0
        self._log_calls: int = 0
        self._log_waits: int = 0
        self._log_wait_time: float = 0.0
        self._last_log: float = time.monotonic()

    def _refill(self, now: float) -> None:
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def _maybe_log(self) -> None:
        now = time.monotonic()
        if now - self._last_log < 30:
            return
        elapsed = now - self._last_log
        self._last_log = now
        rpm = (self._log_calls / max(elapsed, 0.001)) * 60
        log.info(
            f"[RateLimiter] {self._total_calls} total calls, {self._log_calls} in last 30s, "
            f"{self._total_waits} total waits ({self._total_wait_time:.1f}s), "
            f"{self._log_waits} window waits ({self._log_wait_time:.1f}s), "
            f"~{rpm:.0f} RPM, {self._tokens:.1f} tokens"
        )
        self._log_calls = 0
        self._log_waits = 0
        self._log_wait_time = 0.0

    async def acquire(self, retry_after: Optional[float] = None) -> None:
        if retry_after and retry_after > 0:
            await asyncio.sleep(retry_after)

        waited = False
        wait_start = None
        while True:
            async with self._lock:
                now = time.monotonic()
                self._refill(now)
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    self._total_calls += 1
                    self._log_calls += 1
                    if waited:
                        wait_dur = time.monotonic() - wait_start
                        self._total_waits += 1
                        self._total_wait_time += wait_dur
                        self._log_waits += 1
                        self._log_wait_time += wait_dur
                    self._maybe_log()
                    return
                wait = (1.0 - self._tokens) / self._rate
            if not waited:
                wait_start = time.monotonic()
                waited = True
            await asyncio.sleep(wait)

    def reset_stats(self) -> None:
        self._total_calls = 0
        self._total_waits = 0
        self._total_wait_time = 0.0
        self._log_calls = 0
        self._log_waits = 0
        self._log_wait_time = 0.0


# Module-level singleton — shared across all llm_request calls
_rate_limiter = _RateLimiter()


def _resolve_model_name(model: str) -> str:
    """
    Resolve a shorthand model key to the full model name used by the API proxy.

    Callers pass model identifiers like 'sonnet46' or 'haiku45'. This function
    translates them to the actual model string the proxy understands, e.g.
    'sonnet46' → 'claude-sonnet-4-6'. If the model is already a raw name,
    it is returned unchanged.

    Examples:
        >>> _resolve_model_name('sonnet46')
        'claude-sonnet-4-6'
        >>> _resolve_model_name('claude-opus-4-6')
        'claude-opus-4-6'  # passed through as-is
    """
    if model in PROVIDER_MODEL_MAP:
        return PROVIDER_MODEL_MAP[model]["openai"]
    # Already a raw model string — return as-is
    return model


def _get_client() -> AsyncOpenAI:
    """
    Create and return the AsyncOpenAI API client.

    Reads API credentials and base URL from system_config:
      - API_KEY:  Bearer token for authentication (hardcoded in system_config)
      - API_URL:  Proxy endpoint, e.g. 'https://llmapi.datapatterns.co.in/v1'
      - API_TIME_OUT: Default timeout per request (120.0 seconds)

    SDK-level retries are disabled (max_retries=0) because this module
    implements its own retry logic with exponential backoff in _retry_with_backoff().

    Returns:
        AsyncOpenAI client instance — note: currently instantiated per-call
        rather than cached as a true singleton.
    """
    try:
        from .system_config import API_URL, API_KEY, API_TIME_OUT
    except ImportError:
        from system_config import API_URL, API_KEY, API_TIME_OUT

    return AsyncOpenAI(
        api_key=str(API_KEY),
        base_url=str(API_URL),
        timeout=API_TIME_OUT,
        max_retries=API_DEFAULT_RETRY_LIMIT,
    )


# ─── Retry with exponential backoff ─────────────────────────────────────
async def _retry_with_backoff(
    api_call,
    model: str,
    max_retries: int = MAX_RETRIES,
    max_retries_on_empty: int = MAX_RETRIES_ON_EMPTY,
    messages: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[str], bool]:
    """
    Retry an LLM API call with exponential backoff and empty-content detection.

    Mirrors CCB's withRetry():
    - Retries on RateLimitError, APITimeoutError with exponential backoff
    - Retries on empty content response
    - When content is None but reasoning_content exists: loop back to LLM
      by appending an assistant message with the thinking, plus a user
      continuation prompt, and calling again. This lets the model "complete"
      its output instead of discarding the reasoning.
    - Stops after max_retries + max_retries_on_empty total attempts

    Args:
        api_call: Function(client) -> response
        model: Model name for logging
        max_retries: Error retries
        max_retries_on_empty: Additional empty-content retries
        messages: Mutable message list for loop-back continuation

    Returns:
        (content_string or response_object, success_bool)
    """
    client = _get_client()

    total_attempts = max_retries + max_retries_on_empty + 1
    attempt = 1

    while attempt <= total_attempts:
        # Acquire rate limiter token for this attempt
        await _rate_limiter.acquire()

        try:
            response = await api_call(client)
            message = response.choices[0].message
            content = message.content
            tool_calls = message.tool_calls

            if tool_calls:
                return response, True

            if content:
                return content, True

        except RateLimitError as exception:
            retry_after = getattr(exception, "retry_after", None)
            if retry_after is not None and isinstance(retry_after, (int, float)):
                wait_seconds = float(retry_after)
            else:
                wait_seconds = min(API_RETRY_FLOAT_1_0 * (API_2X_INIT ** attempt), API_ERROR_RATE_LIMIT_SLEEP_TIME_LIMIT)
            log.info(
                f"[API_Handler] [{model}] attempt {attempt}/{total_attempts}: "
                f"Rate limit (429), retrying in {wait_seconds:.1f}s... ({exception})"
            )
            await asyncio.sleep(wait_seconds)

        except APITimeoutError as exception:
            wait_seconds = min(API_RETRY_FLOAT_2_0 * (API_2X_INIT ** attempt), API_ERROR_API_TIME_OUT_SLEEP_TIME_LIMIT)
            log.info(
                f"[API_Handler] [{model}] attempt {attempt}/{total_attempts}: "
                f"timeout, retrying in {wait_seconds:.1f}s... ({exception})"
            )
            await asyncio.sleep(wait_seconds)

        except APIError as exception:
            status = getattr(exception, "status", None)
            if status in (429, 408) or (status and status >= 500):
                wait_seconds = min(API_RETRY_FLOAT_1_0 * (API_2X_INIT ** attempt), API_ERROR_SLEEP_TIME_LIMIT)
                log.warning(
                    f"[API_Handler] [{model}] attempt {attempt}/{total_attempts}: "
                    f"retryable API error (status={status}), retrying in {wait_seconds:.1f}s... ({exception})"
                )
                await asyncio.sleep(wait_seconds)

            elif status in (400, 401, 403, 404):
                log.error(f"[API_Handler] [{model}] attempt {attempt}: API error (not retrying, status={status}): {exception}")

            else:
                wait_seconds = min(API_RETRY_FLOAT_1_0 * (API_2X_INIT ** attempt), API_ERROR_SLEEP_TIME_LIMIT)
                log.warning(
                    f"[API_Handler] [{model}] attempt {attempt}/{total_attempts}: "
                    f"API error (status={status}), retrying in {wait_seconds:.1f}s... ({exception})"
                )
                await asyncio.sleep(wait_seconds)

        except Exception as exception:
            wait_seconds = min(API_RETRY_FLOAT_1_0 * (API_2X_INIT ** attempt), API_ERROR_EXCEPTION_SLEEP_TIME_LIMIT)
            log.info(
                f"[API_Handler] [{model}] attempt {attempt}/{total_attempts}: "
                f"{type(exception).__name__}, retrying in {wait_seconds:.1f}s... ({exception})"
            )
            await asyncio.sleep(wait_seconds)

        attempt += 1

    log.error(f"[API_Handler] [{model}]: exhausted all {total_attempts} retries")
    return None, False


# ─── Model Fallback Chain ─────────────────────────────────────
async def _call_with_model_fallback(
    fallback_models: List[str],
    messages: List[Dict[str, str]],
    max_tokens: int = DEFAULT_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    tools: list = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    max_retries_on_empty: int = MAX_RETRIES_ON_EMPTY,
    response_format: Optional[Any] = None,
) -> Optional[str]:
    """
    Try each model in the fallback list until one succeeds.

    Mirrors CCB's retry with fallbackModel — if the primary model fails
    (rate limited, overloaded, or empty response), try the next one.

    fallback_models: list of model keys/names to try in order
    messages: full message list (including any prepended system message)
    """
    for model in fallback_models:
        resolved_model = _resolve_model_name(model)
        log.info(f"[API_Handler] Trying model: {resolved_model}")

        def api_call(active_client: AsyncOpenAI):
            kwargs: Dict[str, Any] = {
                "model": resolved_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": DEFAULT_TOP_P,
                "timeout": timeout,
                "stream": False,
                "tools": tools,
                "reasoning_effort": None,
                "extra_body":{
                    "chat_template_kwargs": {
                        "enable_thinking": False
                    }
                }
            }
            if response_format == "json":
                kwargs["response_format"] = {"type": "json_object"}
            return active_client.chat.completions.create(**kwargs)

        content, success = await _retry_with_backoff(
            api_call, resolved_model,
            max_retries=max_retries,
            max_retries_on_empty=max_retries_on_empty,
            messages=list(messages),
        )

        if success and content:
            log.info(f"[API_Handler] Success with model: {resolved_model}")
            return content
        log.info(f"[API_Handler] Failed with model: {resolved_model}, trying next in chain...")

    return None


# ─── Main Request Function ────────────────────────────────────────────────────
async def llm_request(
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int = DEFAULT_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    tools: Optional[List[Dict]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    system_prompt: Optional[str] = None,
    fallback_chain: Optional[List[str]] = None,
    correction_retry: Optional[Tuple[str, str]] = None,
    response_format: Optional[Any] = None,
) -> Optional[str]:
    """
    Main entry point for LLM API calls. CCB-style with retry + fallback.

    When the model returns content=None with reasoning_content:
    - An assistant message with the reasoning is appended to the conversation
    - A continuation prompt asks the model to produce the actual output
    - The API is called again with the extended conversation

    Args:
        model: Model key (e.g., "haiku45") or raw model name
        messages: List of {role, content} dicts
        max_tokens: Maximum output tokens
        temperature: Sampling temperature
        timeout: Request timeout in seconds
        system_prompt: Optional system message prepended to messages
        fallback_chain: List of model names to try if primary fails
        correction_retry: Tuple of (original_prompt, error_message).
            If provided and the initial call succeeds but produces malformed output,
            a second call is made with the error details appended so the LLM can self-correct.
        response_format: Optional response format parameter (e.g., {"type": "json_object"}).
            Passed directly to the API's response_format argument.

    Returns:
        Content string or None on complete failure
    """
    resolved_model = _resolve_model_name(model)

    llm_message = list(messages)
    if system_prompt:
        llm_message.insert(0, {"role": "system", "content": system_prompt})

    def api_call(active_client: AsyncOpenAI):
        kwargs: Dict[str, Any] = {
            "model": resolved_model,
            "messages": llm_message,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": DEFAULT_TOP_P,
            "timeout": timeout,
            "stream": False,
            "tools": tools,
            "reasoning_effort": None,
            "extra_body":{
                "chat_template_kwargs": {
                    "enable_thinking": False
                }
            }
        }
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        return active_client.chat.completions.create(**kwargs)

    content, success = await _retry_with_backoff(
        api_call, resolved_model,
        max_retries=MAX_RETRIES,
        max_retries_on_empty=MAX_RETRIES_ON_EMPTY,
        messages=llm_message,
    )

    if success and content:
        return content

    # Try fallback chain
    if fallback_chain:
        log.info(f"[API_Handler] Primary model failed, trying fallback chain: {fallback_chain}")
        content = await _call_with_model_fallback(
            fallback_models=fallback_chain,
            messages=llm_message,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            timeout=timeout,
            max_retries=MAX_RETRIES,
            max_retries_on_empty=MAX_RETRIES_ON_EMPTY,
            response_format=response_format,
        )
        if content:
            return content

    return None


# ─── Streaming Handler (for FastAPI SSE endpoints) ────────────────────────────
class StreamingLLMHandler:
    """
    Streaming LLM handler for SSE endpoints.

    Mirrors CCB's beta.messages.stream() → async generator pattern.
    Used by generate_document_sections() for real-time token streaming.
    """

    def __init__(self, model: str):
        self.resolved_model = _resolve_model_name(model)
        self.client = _get_client()

    async def stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = DEFAULT_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        system_prompt: Optional[str] = None,
        tools: list[Any] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yield streaming events (CCB pattern from generate_document_sections).

        Each yield: {"token": str} | {"done": bool} | {"error": str}
        """
        llm_message = list(messages)
        if system_prompt:
            llm_message.insert(0, {"role": "system", "content": system_prompt})

        await _rate_limiter.acquire()

        try:
            response = await self.client.chat.completions.create(
                model=self.resolved_model,
                messages=llm_message,
                max_tokens=max_tokens,
                tools=tools,
                temperature=temperature,
                top_p=DEFAULT_TOP_P,
                timeout=DEFAULT_TIMEOUT,
                stream=True,
                reasoning_effort= None,
            )

            async for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield {"token": delta.content}

            yield {"done": True}

        except Exception as exception:
            log.error(f"[API_Handler] Streaming error: {exception}")
            yield {"error": str(exception)}
