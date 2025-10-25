"""
Centralized .env file loader for all scripts.
Ensures consistent environment variable loading across the project.
"""
import os


def load_env():
    """Load .env file into os.environ if it exists.
    
    This should be called at the very top of every script/module that needs
    environment variables (main.py, scripts/, tests/, etc.)
    """
    # Find project root by looking for .env file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)  # Go up from utils/ to project root
    
    env_file = os.path.join(project_root, '.env')
    
    if not os.path.exists(env_file):
        # Try alternative paths
        env_file = os.path.join(os.getcwd(), '.env')
    
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    # Only set if not already in environment (env vars take precedence)
                    if key not in os.environ:
                        os.environ[key] = value
    else:
        # Not critical - environment variables might be set externally
        pass
