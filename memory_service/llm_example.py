"""Example of using cost tracker with LLM calls."""

import logging
from typing import Dict, Any, Optional

from memory_service.cost import get_cost_tracker

logger = logging.getLogger(__name__)


async def llm_with_cost_tracking(
    prompt: str,
    openai_client: Any,
    model: str = "gpt-3.5-turbo"
) -> Optional[str]:
    """Example function showing how to track LLM costs.
    
    Args:
        prompt: The prompt to send to the LLM
        openai_client: OpenAI async client instance
        model: Model to use
        
    Returns:
        LLM response text or None if failed
    """
    try:
        # Make LLM call
        response = await openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        
        # Track cost
        if hasattr(response, 'usage') and response.usage:
            cost_tracker = await get_cost_tracker()
            await cost_tracker.add_cost(
                kind="llm",
                tokens=response.usage.total_tokens,
                service="memory"
            )
            
            logger.debug(f"LLM used {response.usage.total_tokens} tokens")
        
        # Return response
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


# Example usage in evaluator
async def evaluate_message_importance(
    message: str,
    openai_client: Any
) -> Dict[str, Any]:
    """Evaluate if a message is important enough to save.
    
    This is an example of how to integrate LLM-based evaluation
    with cost tracking.
    """
    prompt = f"""Evaluate the importance of this message for long-term memory storage.
Consider:
1. Is it personal information about the user?
2. Is it a task or plan?
3. Is it technical information worth remembering?
4. Does it contain time-sensitive information?

Message: {message}

Respond with a JSON object containing:
- important: boolean
- category: string (personal/technical/task/temporal/general)
- reason: string (brief explanation)
"""
    
    response = await llm_with_cost_tracking(
        prompt=prompt,
        openai_client=openai_client,
        model="gpt-3.5-turbo"
    )
    
    if response:
        try:
            import json
            return json.loads(response)
        except:
            return {
                "important": True,
                "category": "general",
                "reason": "Failed to parse LLM response"
            }
    
    return {
        "important": False,
        "category": "general", 
        "reason": "LLM evaluation failed"
    }
