"""Base agent class."""
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from openai import OpenAI
import httpx
from loguru import logger

from src.config import settings


class BaseAgent(ABC):
    """Base class for all AI agents."""

    def __init__(self, name: str):
        """
        Initialize base agent.

        Args:
            name: Name of the agent
        """
        self.name = name
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        logger.info(f"Initialized {name} agent")

    @abstractmethod
    async def process(self, *args, **kwargs) -> Any:
        """Process the agent's task."""
        pass

    async def call_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Call OpenAI API.

        Args:
            system_prompt: System message
            user_prompt: User message
            model: Model to use
            temperature: Temperature for sampling
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            Assistant's response
        """
        logger.info(f"[{self.name}] Calling OpenAI ({model})")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }

        if response_format:
            kwargs["response_format"] = response_format

        # Run synchronous OpenAI call in thread pool to avoid blocking event loop
        response = await asyncio.to_thread(
            self.openai_client.chat.completions.create,
            **kwargs
        )

        result = response.choices[0].message.content
        logger.debug(f"[{self.name}] Received response (length: {len(result)})")

        return result

    async def call_perplexity(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "sonar"
    ) -> str:
        """
        Call Perplexity API for research.

        Args:
            system_prompt: System message
            user_prompt: User message
            model: Model to use

        Returns:
            Assistant's response
        """
        logger.info(f"[{self.name}] Calling Perplexity ({model})")

        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.perplexity_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=60.0)
            response.raise_for_status()
            result = response.json()

        content = result["choices"][0]["message"]["content"]
        logger.debug(f"[{self.name}] Received Perplexity response (length: {len(content)})")

        return content
