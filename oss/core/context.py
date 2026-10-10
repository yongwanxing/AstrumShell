"""Context class for plugin execution environment."""

from typing import Any, Dict, Optional


class Context:
    """Execution context for plugins.
    
    Provides access to configuration, state, and utilities during plugin execution.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the context.
        
        Args:
            config: Optional configuration dictionary.
        """
        self.config = config or {}
        self._state: Dict[str, Any] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.
        
        Args:
            key: Configuration key.
            default: Default value if key not found.
            
        Returns:
            The configuration value or default.
        """
        return self.config.get(key, default)
    
    def set_state(self, key: str, value: Any) -> None:
        """Set a state value.
        
        Args:
            key: State key.
            value: State value.
        """
        self._state[key] = value
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value.
        
        Args:
            key: State key.
            default: Default value if key not found.
            
        Returns:
            The state value or default.
        """
        return self._state.get(key, default)
    
    def __repr__(self) -> str:
        return f"Context(config={self.config})"


__all__ = ['Context']
