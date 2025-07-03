"""Template engine for goal step parameters."""

import re
import logging
from typing import Dict, Any, Optional
from jinja2 import Template, Environment, meta

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Simple template engine for goal step parameters."""
    
    def __init__(self):
        self.env = Environment()
        
    def render(
        self, 
        template_str: str, 
        context: Dict[str, Any]
    ) -> Any:
        """Render a template string with context.
        
        Supports:
        - {{prev.result.field}} - Previous step result
        - {{trigger.event.field}} - Trigger event data
        - {{params.field}} - Goal parameters
        """
        if not isinstance(template_str, str):
            return template_str
            
        # Check if string contains template syntax
        if '{{' not in template_str:
            return template_str
            
        try:
            template = self.env.from_string(template_str)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return template_str
            
    def render_dict(
        self, 
        data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recursively render all string values in a dictionary."""
        result = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.render(value, context)
            elif isinstance(value, dict):
                result[key] = self.render_dict(value, context)
            elif isinstance(value, list):
                result[key] = [
                    self.render(item, context) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
                
        return result
        
    def extract_variables(self, template_str: str) -> set:
        """Extract variable names from template."""
        if not isinstance(template_str, str):
            return set()
            
        try:
            ast = self.env.parse(template_str)
            return meta.find_undeclared_variables(ast)
        except:
            return set()
            
    def validate_template(self, template_str: str) -> bool:
        """Validate template syntax."""
        try:
            self.env.from_string(template_str)
            return True
        except:
            return False
