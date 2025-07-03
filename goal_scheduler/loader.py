"""Goal YAML loader and validator."""

import os
import logging
from pathlib import Path
from typing import Dict, List
import yaml

from goal_scheduler.models import GoalConfig

logger = logging.getLogger(__name__)


class GoalLoader:
    """Load and manage goal configurations from YAML files."""
    
    def __init__(self, goals_dir: str):
        self.goals_dir = Path(goals_dir)
        self.goals: Dict[str, GoalConfig] = {}
        
    def load_all(self) -> Dict[str, GoalConfig]:
        """Load all goal configurations from directory."""
        if not self.goals_dir.exists():
            logger.warning(f"Goals directory {self.goals_dir} does not exist")
            return {}
            
        self.goals.clear()
        
        for file_path in self.goals_dir.glob("*.yaml"):
            try:
                goal = self.load_goal(file_path)
                if goal.enabled:
                    self.goals[goal.id] = goal
                    logger.info(f"Loaded goal: {goal.id} from {file_path}")
                else:
                    logger.info(f"Skipped disabled goal: {goal.id}")
            except Exception as e:
                logger.error(f"Failed to load goal from {file_path}: {e}")
                
        logger.info(f"Loaded {len(self.goals)} enabled goals")
        return self.goals
        
    def load_goal(self, file_path: Path) -> GoalConfig:
        """Load a single goal configuration."""
        with open(file_path, 'r') as f:
            content = f.read()
            
        try:
            goal = GoalConfig.from_yaml(content)
            
            # Validate goal ID matches filename (optional)
            expected_id = file_path.stem
            if goal.id != expected_id:
                logger.warning(
                    f"Goal ID '{goal.id}' doesn't match filename '{expected_id}'"
                )
                
            return goal
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}")
        except Exception as e:
            raise ValueError(f"Invalid goal configuration in {file_path}: {e}")
            
    def get_goal(self, goal_id: str) -> GoalConfig:
        """Get a specific goal configuration."""
        if goal_id not in self.goals:
            # Try to reload
            file_path = self.goals_dir / f"{goal_id}.yaml"
            if file_path.exists():
                goal = self.load_goal(file_path)
                if goal.enabled:
                    self.goals[goal_id] = goal
                    
        return self.goals.get(goal_id)
        
    def reload(self) -> Dict[str, GoalConfig]:
        """Reload all goal configurations."""
        logger.info("Reloading goal configurations...")
        return self.load_all()
