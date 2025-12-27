"""
API Provider for SixBTC (LiteLLM-based)
Supports any LiteLLM-compatible model (Anthropic, OpenAI, Gemini, etc.)
"""

import os
from typing import Optional

from src.utils import get_logger

logger = get_logger(__name__)


class APIProvider:
    """
    Provider for AI via API using LiteLLM

    Supports any model available through LiteLLM:
    - Anthropic: claude-sonnet-4-20250514, claude-opus-4-20250514
    - OpenAI: gpt-4o, gpt-4-turbo
    - Google: gemini/gemini-pro
    - And many more...

    API keys are read from environment variables:
    - ANTHROPIC_API_KEY for Anthropic models
    - OPENAI_API_KEY for OpenAI models
    - GEMINI_API_KEY for Google models
    """

    def __init__(self, model: str, timeout: int = 120):
        """
        Initialize API provider

        Args:
            model: LiteLLM model identifier (e.g., 'claude-sonnet-4-20250514')
            timeout: Timeout for API calls in seconds (default: 2 minutes)
        """
        self.model = model
        self.timeout = timeout

        # Lazy import litellm to avoid import errors if not installed
        try:
            import litellm
            self._litellm = litellm
        except ImportError:
            raise ImportError(
                "litellm is required for API mode. "
                "Install with: pip install litellm"
            )

        logger.info(f"API provider initialized: {model}")

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Generate response using LiteLLM API

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_retries: Maximum number of retry attempts

        Returns:
            Generated response or None if failed
        """
        import asyncio
        import time
        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(max_retries):
            try:
                response = await self._litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    timeout=self.timeout,
                )

                content = response.choices[0].message.content

                if not content:
                    logger.warning(
                        f"Empty response from {self.model}, "
                        f"attempt {attempt + 1}/{max_retries}"
                    )
                    continue

                elapsed = time.time() - start_time
                logger.info(f"AI response received in {elapsed:.1f}s ({len(content)} chars)")

                return content

            except Exception as e:
                logger.error(
                    f"{self.model} API error (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    backoff = 5 * (attempt + 1)
                    logger.info(f"Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)

        logger.error(f"{self.model} API failed after {max_retries} attempts")
        return None

    def is_available_sync(self) -> bool:
        """
        Check if API is available (API key is set)

        Returns:
            True if appropriate API key is configured
        """
        # Determine which API key is needed based on model
        model_lower = self.model.lower()

        if "claude" in model_lower or "anthropic" in model_lower:
            key = os.environ.get("ANTHROPIC_API_KEY")
            if key:
                return True
            logger.warning("ANTHROPIC_API_KEY not set")
            return False

        elif "gpt" in model_lower or "openai" in model_lower:
            key = os.environ.get("OPENAI_API_KEY")
            if key:
                return True
            logger.warning("OPENAI_API_KEY not set")
            return False

        elif "gemini" in model_lower:
            key = os.environ.get("GEMINI_API_KEY")
            if key:
                return True
            logger.warning("GEMINI_API_KEY not set")
            return False

        # For other models, assume available (litellm will handle auth)
        logger.info(f"Unknown model provider for {self.model}, assuming available")
        return True

    async def check_availability(self) -> bool:
        """
        Async check for API availability

        Returns:
            True if API key is configured
        """
        return self.is_available_sync()
