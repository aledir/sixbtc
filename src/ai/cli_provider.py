"""
CLI Provider for SixBTC (provider-agnostic)
Supports multiple CLI tools: claude, gemini, codex
"""

import asyncio
import os
import shutil
import tempfile
import time
from typing import Optional

from src.utils import get_logger

logger = get_logger(__name__)


class CLIProvider:
    """
    Provider for AI via CLI (provider-agnostic)

    Supports multiple CLI tools:
    - claude: Claude Code CLI (subscription-based)
    - gemini: Google Gemini CLI
    - codex: OpenAI Codex CLI

    Default command: cat prompt.txt | claude --dangerously-skip-permissions --print
    """

    # CLI command flags mapping
    COMMAND_FLAGS = {
        "claude": "--dangerously-skip-permissions --print",
        # Add other CLIs when needed:
        # "gemini": "...",
        # "codex": "...",
    }

    def __init__(self, command: str = "claude", timeout: int = 300):
        """
        Initialize CLI provider

        Args:
            command: CLI command to use (claude, gemini, codex)
            timeout: Timeout for CLI commands in seconds (default: 5 minutes)
        """
        self.command = command
        self.timeout = timeout
        self.cli_version = None

        # Validate command is supported (Rule #3: Fast Fail)
        if command not in self.COMMAND_FLAGS:
            raise ValueError(
                f"CLI '{command}' not yet supported. "
                f"Supported: {list(self.COMMAND_FLAGS.keys())}. "
                f"Add flags to COMMAND_FLAGS dict to support new CLIs."
            )

        logger.info(f"CLI provider initialized: {command}")

    async def check_availability(self) -> bool:
        """
        Check if CLI tool is available

        Returns:
            True if configured CLI command is available
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                self.command,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)

            if proc.returncode == 0 and stdout:
                version_str = stdout.decode().strip()
                # Clean up version string (Claude-specific)
                if "(Claude Code)" in version_str:
                    version_str = version_str.replace("(Claude Code)", "").strip()
                self.cli_version = version_str
                logger.info(f"CLI available: {self.command} {self.cli_version}")
                return True

            return False

        except FileNotFoundError:
            logger.error(f"CLI '{self.command}' not found in PATH")
            return False
        except asyncio.TimeoutError:
            logger.warning(f"CLI '{self.command}' version check timed out")
            return False
        except Exception as e:
            logger.error(f"CLI '{self.command}' check failed: {e}")
            return False

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Generate response using CLI with workspace isolation

        Creates isolated temp directory to prevent AI from seeing project files.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt to prepend
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            Generated response or None if failed
        """
        start_time = time.time()
        temp_workspace = None

        try:
            # Create isolated workspace (prevents AI from seeing project files)
            temp_workspace = tempfile.mkdtemp(prefix=f'sixbtc_{self.command}_')

            # Write prompt in isolated workspace
            prompt_file = os.path.join(temp_workspace, 'prompt.txt')
            with open(prompt_file, 'w') as f:
                # Write system prompt if provided
                if system_prompt:
                    f.write(f"{system_prompt}\n\n")

                # Write user prompt
                f.write(prompt)

            # Build command: Execute from isolated workspace
            # AI will ONLY see temp_workspace contents (prompt.txt), NOT project files
            flags = self.COMMAND_FLAGS[self.command]
            shell_cmd = f"cd {temp_workspace} && cat prompt.txt | {self.command} {flags}"

            logger.debug(f"Executing {self.command} CLI in isolated workspace: {temp_workspace}")
            logger.debug(f"Timeout: {self.timeout}s, Prompt length: {len(prompt)} chars")

            # Build clean environment for CLI (exclude API keys that would override OAuth)
            # Claude CLI prioritizes ANTHROPIC_API_KEY over OAuth if present
            clean_env = {k: v for k, v in os.environ.items()
                        if k not in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY')}

            # Execute command
            process = await asyncio.create_subprocess_shell(
                shell_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=clean_env,
            )

            # Wait for response with timeout and retry logic
            stdout, stderr = None, None
            for attempt in range(max_retries):
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.timeout
                    )
                    break  # Success
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        backoff_delay = 5 * (attempt + 1)
                        logger.warning(
                            f"{self.command} CLI timeout (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {backoff_delay}s..."
                        )
                        # Kill current process
                        try:
                            process.terminate()
                            await asyncio.wait_for(process.wait(), timeout=5)
                        except:
                            process.kill()
                            await process.wait()

                        # Wait before retry
                        await asyncio.sleep(backoff_delay)

                        # Restart process for retry
                        process = await asyncio.create_subprocess_shell(
                            shell_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            env=clean_env,
                        )
                    else:
                        logger.error(
                            f"{self.command} CLI timed out after {max_retries} attempts "
                            f"({self.timeout}s each)"
                        )
                        # Kill process
                        try:
                            process.terminate()
                            await asyncio.wait_for(process.wait(), timeout=5)
                        except:
                            process.kill()
                            await process.wait()
                        return None

            # Parse stdout/stderr
            stdout_text = stdout.decode() if stdout else ""
            stderr_text = stderr.decode() if stderr else ""

            # Always log response details for debugging
            logger.debug(
                f"AI completed: returncode={process.returncode}, "
                f"stdout={len(stdout_text)} chars, stderr={len(stderr_text)} chars"
            )

            # Log stderr if present (even on success, for debugging)
            if stderr_text.strip():
                logger.warning(f"{self.command} CLI stderr: {stderr_text[:500]}")

            # Log if stdout is empty but returncode is 0 (suspicious)
            if process.returncode == 0 and len(stdout_text.strip()) == 0:
                logger.error(
                    f"{self.command} CLI returned success but empty stdout! "
                    f"stderr: {stderr_text[:500]}"
                )

            # Check exit code
            if process.returncode != 0:
                # Check for auth errors (Claude-specific, but generic enough)
                if "OAuth token has expired" in stderr_text or "not logged in" in stderr_text.lower():
                    logger.error(f"{self.command} CLI authentication error. Run: {self.command} login")
                    return None

                # Check for rate limit
                error_combined = (stdout_text + " " + stderr_text).lower()
                if any(msg in error_combined for msg in ["rate limit", "quota exceeded", "too many requests"]):
                    logger.error(f"{self.command} CLI rate limit exceeded")
                    return None

                logger.error(f"{self.command} CLI failed with code {process.returncode}")
                logger.error(f"Stderr: {stderr_text[:500]}")
                logger.error(f"Stdout preview: {stdout_text[:200]}")
                return None

            # Return response
            response = stdout_text.strip()

            elapsed = time.time() - start_time
            logger.info(f"AI response received in {elapsed:.1f}s ({len(response)} chars)")

            return response if response else None

        except Exception as e:
            logger.error(f"{self.command} CLI error: {e}", exc_info=True)
            return None

        finally:
            # Clean up isolated workspace (guaranteed cleanup even if crash)
            if temp_workspace:
                try:
                    shutil.rmtree(temp_workspace, ignore_errors=True)
                    logger.debug(f"Cleaned up workspace: {temp_workspace}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup workspace {temp_workspace}: {e}")

    def is_available_sync(self) -> bool:
        """
        Synchronous check for CLI availability

        Returns:
            True if configured CLI command exists
        """
        import subprocess
        try:
            result = subprocess.run(
                ["which", self.command],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
