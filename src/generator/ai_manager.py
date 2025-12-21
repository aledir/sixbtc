"""
AI Manager - Multi-Provider LLM Rotation

Manages multiple AI providers with automatic failover and rotation.
Ported from fivebtc with enhancements for SixBTC.
"""

import os
import time
from typing import Optional, Literal
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Provider type
AIProvider = Literal['claude', 'gemini', 'openai', 'anthropic']


@dataclass
class AIResponse:
    """Response from AI provider"""
    content: str
    provider: AIProvider
    tokens_used: int
    latency_ms: float


class AIManager:
    """
    Manages multiple AI providers with rotation and failover

    Features:
    - Round-robin rotation across providers
    - Automatic failover on errors
    - Rate limit handling
    - Token usage tracking
    """

    def __init__(self, config: dict):
        """
        Initialize AI Manager

        Args:
            config: Configuration dict with provider settings
        """
        self.config = config
        # NO defaults - config must be complete (Fast Fail principle)
        self.rotation_strategy = config['rotation_strategy']
        self.max_retries = config['max_retries']
        self.timeout = config['timeout']

        # Parse provider configurations
        self.providers = []
        self.current_provider_idx = 0

        # Providers list is required
        for provider_config in config['providers']:
            # Only add if explicitly enabled (defaults to True if key missing)
            if provider_config.get('enabled', True):
                self.providers.append(provider_config)

        if not self.providers:
            raise RuntimeError("No AI providers configured")

        # Track usage
        self.usage_stats = {}
        for provider_config in self.providers:
            provider_name = provider_config['name']
            self.usage_stats[provider_name] = {'calls': 0, 'tokens': 0, 'errors': 0}

        # Initialize clients
        self.clients = {}
        self._init_clients()

    def _init_clients(self):
        """Initialize AI provider clients"""
        for provider_config in self.providers:
            provider_name = provider_config['name']
            api_key = provider_config.get('api_key')

            if not api_key:
                logger.warning(f"No API key configured for {provider_name}")
                continue

            try:
                if provider_name in ['claude', 'anthropic']:
                    import anthropic
                    self.clients[provider_name] = anthropic.Anthropic(api_key=api_key)
                    logger.info(f"Anthropic/Claude client initialized")

                elif provider_name == 'openai':
                    import openai
                    self.clients[provider_name] = openai.OpenAI(api_key=api_key)
                    logger.info(f"OpenAI client initialized")

                elif provider_name == 'gemini':
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    self.clients[provider_name] = genai.GenerativeModel('gemini-pro')
                    logger.info(f"Gemini client initialized")

            except ImportError as e:
                logger.warning(f"Failed to import {provider_name}: {e}")
            except Exception as e:
                logger.warning(f"Failed to initialize {provider_name}: {e}")

    def generate(
        self,
        prompt: str,
        provider: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> str:
        """
        Generate response using specified or next available provider

        Args:
            prompt: Input prompt
            provider: Specific provider to use (None for rotation)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Returns:
            Generated text content

        Raises:
            RuntimeError: If generation fails
        """
        if provider:
            # Use specific provider
            provider_config = next((p for p in self.providers if p['name'] == provider), None)
            if not provider_config:
                raise ValueError(f"Provider {provider} not configured")
            provider_name = provider
        else:
            # Use rotation
            provider_name = self._get_next_provider()

        try:
            start_time = time.time()

            if provider_name in ['claude', 'anthropic']:
                response = self._generate_claude(prompt, max_tokens, temperature, provider_name)
            elif provider_name == 'gemini':
                response = self._generate_gemini(prompt, max_tokens, temperature)
            elif provider_name == 'openai':
                response = self._generate_openai(prompt, max_tokens, temperature)
            else:
                raise ValueError(f"Unknown provider: {provider_name}")

            latency = (time.time() - start_time) * 1000

            # Update stats
            self.usage_stats[provider_name]['calls'] += 1
            self.usage_stats[provider_name]['tokens'] += response.tokens_used

            logger.info(
                f"Generated with {provider_name} "
                f"({response.tokens_used} tokens, {latency:.0f}ms)"
            )

            return response.content

        except Exception as e:
            self.usage_stats[provider_name]['errors'] += 1
            logger.error(f"Error with {provider_name}: {e}")
            raise

    def generate_with_retry(
        self,
        prompt: str,
        max_retries: Optional[int] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> str:
        """
        Generate response with automatic retry and provider rotation

        Args:
            prompt: Input prompt
            max_retries: Number of retries (uses config default if None)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Returns:
            Generated text content

        Raises:
            RuntimeError: If all providers fail
        """
        retry_count = max_retries if max_retries is not None else self.max_retries

        for attempt in range(retry_count):
            provider_name = self._get_next_provider()

            try:
                start_time = time.time()

                if provider_name in ['claude', 'anthropic']:
                    response = self._generate_claude(prompt, max_tokens, temperature, provider_name)
                elif provider_name == 'gemini':
                    response = self._generate_gemini(prompt, max_tokens, temperature)
                elif provider_name == 'openai':
                    response = self._generate_openai(prompt, max_tokens, temperature)
                else:
                    raise ValueError(f"Unknown provider: {provider_name}")

                latency = (time.time() - start_time) * 1000

                # Update stats
                self.usage_stats[provider_name]['calls'] += 1
                self.usage_stats[provider_name]['tokens'] += response.tokens_used

                logger.info(
                    f"Generated with {provider_name} "
                    f"({response.tokens_used} tokens, {latency:.0f}ms)"
                )

                return response.content

            except Exception as e:
                self.usage_stats[provider_name]['errors'] += 1
                logger.warning(
                    f"Error with {provider_name} (attempt {attempt + 1}/{retry_count}): {e}"
                )

                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        raise RuntimeError(f"All providers failed after {retry_count} attempts")

    def _rotate_provider(self):
        """Rotate to next provider"""
        self.current_provider_idx = (self.current_provider_idx + 1) % len(self.providers)

    def _get_next_provider(self) -> str:
        """Get next provider in rotation"""
        if self.rotation_strategy == 'round_robin':
            provider_config = self.providers[self.current_provider_idx]
            self._rotate_provider()
            return provider_config['name']
        else:
            raise NotImplementedError(f"Rotation strategy {self.rotation_strategy} not implemented")

    def _generate_claude(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        provider_name: str
    ) -> AIResponse:
        """Generate with Claude/Anthropic"""
        client = self.clients[provider_name]

        # Get model from config (NO default, crash if missing)
        provider_config = next((p for p in self.providers if p['name'] == provider_name), None)
        if provider_config is None:
            raise ValueError(f"Provider {provider_name} not found in config")
        model = provider_config['model']

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens

        return AIResponse(
            content=content,
            provider=provider_name,
            tokens_used=tokens,
            latency_ms=0  # Filled by caller
        )

    def _generate_gemini(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> AIResponse:
        """Generate with Gemini"""
        client = self.clients['gemini']

        generation_config = {
            'max_output_tokens': max_tokens,
            'temperature': temperature,
        }

        response = client.generate_content(
            prompt,
            generation_config=generation_config
        )

        content = response.text
        tokens = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0

        return AIResponse(
            content=content,
            provider='gemini',
            tokens_used=tokens,
            latency_ms=0
        )

    def _generate_openai(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> AIResponse:
        """Generate with OpenAI"""
        client = self.clients['openai']

        # Get model from config (NO default, crash if missing)
        provider_config = next((p for p in self.providers if p['name'] == 'openai'), None)
        if provider_config is None:
            raise ValueError("OpenAI provider not found in config")
        model = provider_config['model']

        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.choices[0].message.content
        tokens = response.usage.total_tokens

        return AIResponse(
            content=content,
            provider='openai',
            tokens_used=tokens,
            latency_ms=0
        )

    def get_stats(self) -> dict:
        """Get usage statistics"""
        return self.usage_stats.copy()
