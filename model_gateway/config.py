"""
Configuration models for Model Gateway
"""
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
import yaml
from pathlib import Path


class ModelConfig(BaseModel):
    """Configuration for a single model"""
    provider: str
    engine: str
    input_cost: float  # USD per token
    output_cost: float  # USD per token
    max_tokens: int
    timeout: int = 300  # seconds
    supports_streaming: bool = True
    

class DefaultRouting(BaseModel):
    """Default model assignments for different tasks"""
    self_reflection: str = "o3-pro"
    self_reflection_frequent: str = "gpt-4o"
    vitals: str = "gpt-4o"
    experiment: str = "o3-pro"
    

class BudgetConfig(BaseModel):
    """Budget configuration"""
    daily_limit_usd: float = 20.0
    hard_stop: bool = True
    warning_threshold: float = 0.8  # Warn at 80% of budget
    

class GatewayConfig(BaseModel):
    """Complete gateway configuration"""
    models: Dict[str, ModelConfig]
    defaults: DefaultRouting = Field(default_factory=DefaultRouting)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    
    @classmethod
    def from_yaml(cls, path: Path) -> "GatewayConfig":
        """Load configuration from YAML file"""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Convert models dict
        models = {}
        for name, config in data.get('models', {}).items():
            models[name] = ModelConfig(**config)
        
        # Build config
        return cls(
            models=models,
            defaults=DefaultRouting(**data.get('defaults', {})),
            budget=BudgetConfig(**data.get('budget', {}))
        )
    
    def get_model(self, name: str) -> Optional[ModelConfig]:
        """Get model configuration by name"""
        return self.models.get(name)
    
    def list_models(self) -> List[str]:
        """List all available model names"""
        return list(self.models.keys())
