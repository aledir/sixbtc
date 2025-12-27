"""
Unified AI Client for SixBTC (provider-agnostic)
Abstracts CLI vs API provider selection based on config
"""

from typing import Dict, Optional

from src.utils import get_logger

logger = get_logger(__name__)


class AIClient:
    """
    Unified AI client that abstracts CLI vs API providers

    Usage:
        client = AIClient(config)
        response = await client.generate_response(prompt, system_prompt)
        model_name = client.get_model_name()  # For logging/DB

    Config structure (config.yaml):
        ai:
          mode: "cli"  # "cli" | "api"
          cli:
            model: "claude"  # "claude" | "gemini" | "codex"
          api:
            model: "claude-sonnet-4-20250514"
            timeout: 120
    """

    def __init__(self, config: Dict):
        """
        Initialize AI client based on config

        Args:
            config: Full configuration dict (must contain 'ai' section)
        """
        self.config = config

        # Get AI config section (Rule #3: Fast Fail if missing)
        ai_config = config.get("ai")
        if not ai_config:
            raise ValueError(
                "CRITICAL CONFIG ERROR: 'ai' section not found in config.yaml! "
                "Add: ai: { mode: 'cli', cli: { model: 'claude' } }"
            )

        self.mode = ai_config.get("mode", "cli")

        if self.mode == "cli":
            self._init_cli_provider(ai_config)
        elif self.mode == "api":
            self._init_api_provider(ai_config)
        else:
            raise ValueError(
                f"CRITICAL CONFIG ERROR: Unknown ai.mode '{self.mode}'. "
                f"Supported: 'cli', 'api'"
            )

    def _init_cli_provider(self, ai_config: Dict):
        """Initialize CLI provider"""
        from src.ai.cli_provider import CLIProvider

        cli_config = ai_config.get("cli", {})
        cli_model = cli_config.get("model", "claude")
        timeout = cli_config.get("timeout", 300)

        self.provider = CLIProvider(command=cli_model, timeout=timeout)
        self._model_name = f"cli:{cli_model}"

        # Verify CLI is available (Rule #3: Fast Fail)
        if not self.provider.is_available_sync():
            raise ValueError(
                f"CLI '{cli_model}' not available. "
                f"Ensure it's installed and in PATH."
            )

        logger.info(f"AI client initialized: {self._model_name}")

    def _init_api_provider(self, ai_config: Dict):
        """Initialize API provider (LiteLLM)"""
        from src.ai.api_provider import APIProvider

        api_config = ai_config.get("api", {})

        model = api_config.get("model")
        if not model:
            raise ValueError(
                "CRITICAL CONFIG ERROR: ai.api.model not set! "
                "Example: 'claude-sonnet-4-20250514'"
            )

        timeout = api_config.get("timeout", 120)

        self.provider = APIProvider(model=model, timeout=timeout)
        self._model_name = model

        # Verify API is available (Rule #3: Fast Fail)
        if not self.provider.is_available_sync():
            raise ValueError(
                f"API key not configured for model '{model}'. "
                f"Set appropriate API key in .env file."
            )

        logger.info(f"AI client initialized: {self._model_name}")

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Generate response using configured provider

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_retries: Maximum retry attempts

        Returns:
            Generated response or None if failed
        """
        return await self.provider.generate_response(
            prompt=prompt,
            system_prompt=system_prompt,
            max_retries=max_retries
        )

    def generate_response_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Synchronous wrapper for generate_response

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_retries: Maximum retry attempts

        Returns:
            Generated response or None if failed
        """
        import asyncio
        return asyncio.run(self.generate_response(prompt, system_prompt, max_retries))

    def get_model_name(self) -> str:
        """
        Get model identifier for logging and DB tracking

        Returns:
            Model name (e.g., 'cli:claude', 'claude-sonnet-4-20250514')
        """
        return self._model_name

    def is_available_sync(self) -> bool:
        """
        Check if provider is available

        Returns:
            True if provider is ready to use
        """
        return self.provider.is_available_sync()
