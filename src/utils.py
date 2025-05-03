import yaml
import logging
from pathlib import Path
from typing import Dict, Any

# Get a logger specific to this module
logger = logging.getLogger(__name__)

CONFIG_PATH: Path = Path(__file__).parent.parent / 'config' / 'config.yaml'

def load_config() -> Dict[str, Any]:
    """Loads configuration from the YAML file."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config: Dict[str, Any] = yaml.safe_load(f)
        if not isinstance(config, dict):
             raise TypeError("Configuration file did not parse as a dictionary.")
        logger.info(f"Configuration loaded from {CONFIG_PATH}")
        return config
    except FileNotFoundError:
        logger.error(f"Configuration file not found at {CONFIG_PATH}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading config: {e}")
        raise

def setup_logging(log_file_path: str | Path) -> None:
    """Sets up basic logging configuration."""
    log_path = Path(log_file_path)
    log_dir = log_path.parent
    log_dir.mkdir(parents=True, exist_ok=True) # Ensure log directory exists

    logging.basicConfig(
        level=logging.DEBUG, # Changed level to DEBUG
        format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler() # Also log to console
        ]
    )
    # Use the root logger here for initial setup message, or create a temp logger
    logging.info("Logging setup complete.") # Keep using root logger for this initial message

# Example usage (optional, for testing)
# if __name__ == '__main__':
#     setup_logging('logs/test.log')
#     config = load_config()
#     print(config)
