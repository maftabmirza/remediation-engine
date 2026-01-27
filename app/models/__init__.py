# Re-export from parent models.py for backward compatibility
import sys
from pathlib import Path

# Load parent models.py module
parent_models_path = Path(__file__).parent.parent / 'models.py'
if parent_models_path.exists():
    import importlib.util
    spec = importlib.util.spec_from_file_location("parent_models", parent_models_path)
    if spec and spec.loader:
        parent_models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parent_models)
        
        # Re-export all names from parent models
        for name in dir(parent_models):
            if not name.startswith('_'):
                globals()[name] = getattr(parent_models, name)
