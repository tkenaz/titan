"""
Model Gateway Router - Main request handling logic
"""
import time
import uuid
from typing import Dict, Any, Optional, AsyncIterator
from pathlib import Path
import logging

from .config import GatewayConfig
from .providers import ProviderFactory, ProviderInterface
from .cost_tracker import CostTracker, BudgetGuard
from .security import HMACValidator
from .events import EventLogger
from .insights import ModelInsights

logger = logging.getLogger(__name__)


class ModelRouter:
    """Routes requests to appropriate model providers"""
    
    def __init__(
        self,
        config: GatewayConfig,
        cost_tracker: CostTracker,
        event_logger: EventLogger,
        hmac_secret: str,
        insights: Optional[ModelInsights] = None
    ):
        self.config = config
        self.cost_tracker = cost_tracker
        self.event_logger = event_logger
        self.hmac_validator = HMACValidator(hmac_secret)
        self.insights = insights
        
        # Initialize providers
        self.providers: Dict[str, ProviderInterface] = {}
        self._init_providers()
        
        # Budget guard
        self.budget_guard = BudgetGuard(
            cost_tracker=cost_tracker,
            hard_stop=config.budget.hard_stop,
            warning_threshold=config.budget.warning_threshold
        )
    
    def _init_providers(self):
        """Initialize provider instances"""
        provider_types = set()
        for model_config in self.config.models.values():
            provider_types.add(model_config.provider)
        
        for provider_type in provider_types:
            self.providers[provider_type] = ProviderFactory.create(provider_type)
    
    async def route_completion(
        self,
        model_name: str,
        messages: list,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        trace_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Route completion request to appropriate provider
        Returns response with usage stats and signature
        """
        # Generate trace ID if not provided
        trace_id = trace_id or str(uuid.uuid4())
        start_time = time.time()
        
        # Get model config
        model_config = self.config.get_model(model_name)
        if not model_config:
            return {
                "error": f"Unknown model: {model_name}",
                "status": 404
            }
        
        # Check budget
        allowed, reason, budget_stats = await self.budget_guard.check_request_allowed()
        if not allowed:
            await self.event_logger.log_budget_exceeded(
                daily_total=budget_stats["daily_total"],
                daily_limit=budget_stats["daily_limit"],
                blocked_model=model_name
            )
            return {
                "error": reason,
                "status": 429,
                "budget_stats": budget_stats
            }
        
        # Log request start
        request_text = " ".join(msg.get("content", "") for msg in messages)
        await self.event_logger.log_request(
            model=model_name,
            trace_id=trace_id,
            request_size=len(request_text),
            metadata={"temperature": temperature, "stream": stream}
        )
        
        # Get provider
        provider = self.providers.get(model_config.provider)
        if not provider:
            return {
                "error": f"Provider not initialized: {model_config.provider}",
                "status": 500
            }
        
        try:
            if stream:
                # Return streaming response info
                return {
                    "stream": True,
                    "trace_id": trace_id,
                    "model": model_name,
                    "provider": model_config.provider,
                    "engine": model_config.engine
                }
            else:
                # Make completion request
                response_text, usage = await provider.complete(
                    messages=messages,
                    model=model_config.engine,
                    temperature=temperature,
                    max_tokens=max_tokens or model_config.max_tokens,
                    **kwargs
                )
                
                # Calculate cost
                cost_stats = await self.cost_tracker.add_cost(
                    model=model_name,
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                    input_cost_per_token=model_config.input_cost,
                    output_cost_per_token=model_config.output_cost,
                    trace_id=trace_id
                )
                
                # Log completion
                latency_ms = (time.time() - start_time) * 1000
                await self.event_logger.log_response(
                    model=model_name,
                    trace_id=trace_id,
                    tokens_in=usage["prompt_tokens"],
                    tokens_out=usage["completion_tokens"],
                    cost_usd=cost_stats["total_cost"],
                    latency_ms=latency_ms
                )
                
                # Check for budget warning
                if "warning" in cost_stats:
                    await self.event_logger.log_budget_warning(
                        budget_used_percent=cost_stats["budget_used_percent"],
                        daily_total=cost_stats["daily_total"],
                        daily_limit=cost_stats["daily_limit"]
                    )
                
                # Generate signature
                signature = self.hmac_validator.sign(response_text)
                
                # Record insight if available
                if self.insights:
                    try:
                        await self.insights.record_insight(
                            trace_id=trace_id,
                            model=model_name,
                            messages=messages,
                            response_text=response_text,
                            usage=usage,
                            cost={
                                "input_cost": cost_stats["input_cost"],
                                "output_cost": cost_stats["output_cost"],
                                "total_cost": cost_stats["total_cost"]
                            },
                            latency_ms=latency_ms,
                            status="success",
                            temperature=temperature,
                            max_tokens=max_tokens,
                            metadata=kwargs
                        )
                    except Exception as e:
                        logger.error(f"Failed to record insight: {e}")
                
                return {
                    "content": response_text,
                    "usage": usage,
                    "cost": cost_stats,
                    "signature": signature,
                    "trace_id": trace_id,
                    "latency_ms": latency_ms,
                    "model": model_name
                }
                
        except Exception as e:
            logger.error(f"Model routing error: {e}")
            
            # Log error
            latency_ms = (time.time() - start_time) * 1000
            await self.event_logger.log_response(
                model=model_name,
                trace_id=trace_id,
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                status="error",
                error=str(e)
            )
            
            return {
                "error": f"Provider error: {str(e)}",
                "status": 500,
                "trace_id": trace_id
            }
    
    async def stream_completion(
        self,
        model_name: str,
        messages: list,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        trace_id: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream completion response with signatures
        Yields chunks with format: {"chunk": "text", "signature": "...", "seq": N}
        """
        trace_id = trace_id or str(uuid.uuid4())
        start_time = time.time()
        
        # Get model config
        model_config = self.config.get_model(model_name)
        if not model_config:
            yield {
                "error": f"Unknown model: {model_name}",
                "status": 404
            }
            return
        
        # Check budget
        allowed, reason, budget_stats = await self.budget_guard.check_request_allowed()
        if not allowed:
            yield {
                "error": reason,
                "status": 429,
                "budget_stats": budget_stats
            }
            return
        
        # Log streaming start
        await self.event_logger.log_streaming_start(
            model=model_name,
            trace_id=trace_id
        )
        
        # Get provider
        provider = self.providers.get(model_config.provider)
        if not provider:
            yield {
                "error": f"Provider not initialized: {model_config.provider}",
                "status": 500
            }
            return
        
        try:
            # Track tokens manually for streaming
            full_response = ""
            sequence = 0
            
            async for chunk in provider.stream(
                messages=messages,
                model=model_config.engine,
                temperature=temperature,
                max_tokens=max_tokens or model_config.max_tokens,
                **kwargs
            ):
                full_response += chunk
                signature = self.hmac_validator.sign_stream_chunk(chunk, sequence)
                
                yield {
                    "chunk": chunk,
                    "signature": signature,
                    "seq": sequence,
                    "trace_id": trace_id
                }
                sequence += 1
            
            # After streaming completes, calculate costs
            # Count tokens in full response
            prompt_text = " ".join(msg.get("content", "") for msg in messages)
            prompt_tokens = provider.count_tokens(prompt_text, model_config.engine)
            completion_tokens = provider.count_tokens(full_response, model_config.engine)
            
            # Add cost
            cost_stats = await self.cost_tracker.add_cost(
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                input_cost_per_token=model_config.input_cost,
                output_cost_per_token=model_config.output_cost,
                trace_id=trace_id
            )
            
            # Log completion
            latency_ms = (time.time() - start_time) * 1000
            await self.event_logger.log_response(
                model=model_name,
                trace_id=trace_id,
                tokens_in=prompt_tokens,
                tokens_out=completion_tokens,
                cost_usd=cost_stats["total_cost"],
                latency_ms=latency_ms
            )
            
            # Send final metadata
            yield {
                "done": True,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                },
                "cost": cost_stats,
                "latency_ms": latency_ms,
                "trace_id": trace_id
            }
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield {
                "error": f"Streaming error: {str(e)}",
                "status": 500,
                "trace_id": trace_id
            }
