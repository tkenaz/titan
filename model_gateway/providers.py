"""
Provider interfaces for different LLM services
"""
import os
import json
import httpx
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncIterator, Optional, Tuple
import logging
from openai import AsyncOpenAI
import tiktoken

logger = logging.getLogger(__name__)


class ProviderInterface(ABC):
    """Base interface for LLM providers"""
    
    @abstractmethod
    async def complete(
        self, 
        messages: list,
        model: str,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Make a completion request
        Returns: (response_text, usage_stats)
        """
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: list,
        model: str,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion chunks"""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens for a given text"""
        pass


class OpenAIProvider(ProviderInterface):
    """OpenAI/Azure OpenAI provider"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Token encoders cache
        self._encoders = {}
    
    def _get_encoder(self, model: str):
        """Get tiktoken encoder for model"""
        if model not in self._encoders:
            try:
                # Try to get exact encoding
                self._encoders[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback to cl100k_base for newer models
                self._encoders[model] = tiktoken.get_encoding("cl100k_base")
        return self._encoders[model]
    
    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens using tiktoken"""
        encoder = self._get_encoder(model)
        return len(encoder.encode(text))
    
    async def complete(
        self,
        messages: list,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """Make a completion request to OpenAI"""
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Extract usage stats
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return response.choices[0].message.content, usage
            
        except Exception as e:
            logger.error(f"OpenAI completion error: {e}")
            raise
    
    async def stream(
        self,
        messages: list,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion from OpenAI"""
        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise


class ProviderFactory:
    """Factory for creating provider instances"""
    
    _providers = {
        "openai": OpenAIProvider,
        # Add more providers here as needed
        # "azure": AzureOpenAIProvider,
        # "anthropic": AnthropicProvider,
        # "google": GoogleProvider,
    }
    
    @classmethod
    def create(cls, provider_name: str, **kwargs) -> ProviderInterface:
        """Create a provider instance"""
        provider_class = cls._providers.get(provider_name)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        return provider_class(**kwargs)
