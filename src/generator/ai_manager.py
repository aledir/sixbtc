"""
AI Manager - Wrapper for AIClient

Provides interface expected by StrategyBuilder using the new unified AIClient.
"""

import asyncio
from typing import Optional
from dataclasses import dataclass
import logging

from src.ai import AIClient

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """Response from AI provider"""
    content: str
    provider: str
    tokens_used: int
    latency_ms: float


class AIManager:
    """
    AI Manager wrapper for StrategyBuilder

    Uses the unified AIClient for CLI/API abstraction.
    """

    def __init__(self, config: dict):
        """
        Initialize AI Manager

        Args:
            config: Full configuration dict (must contain 'ai' section)
        """
        self.config = config
        self.client = AIClient(config)
        self._provider_name = self.client.get_model_name()

        logger.info(f"AIManager initialized with {self._provider_name}")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate response using configured AI provider

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens (ignored for CLI mode)
            temperature: Sampling temperature (ignored for CLI mode)
            system_prompt: Optional system prompt

        Returns:
            Generated text content

        Raises:
            RuntimeError: If generation fails
        """
        try:
            # Use sync wrapper
            response = self.client.generate_response_sync(
                prompt=prompt,
                system_prompt=system_prompt,
                max_retries=3
            )

            if response is None:
                raise RuntimeError("AI generation returned empty response")

            logger.info(f"Generated with {self._provider_name} ({len(response)} chars)")
            return response

        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            raise RuntimeError(f"AI generation failed: {e}")

    def generate_with_retry(
        self,
        prompt: str,
        max_retries: int = 3,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate response with automatic retry

        Args:
            prompt: Input prompt
            max_retries: Number of retries
            max_tokens: Maximum tokens (ignored for CLI mode)
            temperature: Sampling temperature (ignored for CLI mode)
            system_prompt: Optional system prompt

        Returns:
            Generated text content

        Raises:
            RuntimeError: If all retries fail
        """
        try:
            response = self.client.generate_response_sync(
                prompt=prompt,
                system_prompt=system_prompt,
                max_retries=max_retries
            )

            if response is None:
                raise RuntimeError("AI generation returned empty response")

            return response

        except Exception as e:
            raise RuntimeError(f"AI generation failed after {max_retries} retries: {e}")

    def get_provider_name(self) -> str:
        """Get current provider name"""
        return self._provider_name

    def get_stats(self) -> dict:
        """Get usage statistics (placeholder)"""
        return {
            self._provider_name: {
                'calls': 0,
                'tokens': 0,
                'errors': 0
            }
        }
