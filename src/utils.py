import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Set
import json

# Get a logger specific to this module
logger = logging.getLogger(__name__)

CONFIG_PATH: Path = Path(__file__).parent.parent / 'config' / 'config.yaml'
DEFAULT_MATCHED_IDS_PATH: Path = Path(__file__).parent.parent / 'data' / 'matched_transaction_ids.json'

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

def load_matched_ids(filepath: Path) -> Set[str]:
    """Loads a set of matched transaction IDs from a JSON file."""
    try:
        if not filepath.parent.exists():
            filepath.parent.mkdir(parents=True, exist_ok=True)
        if filepath.exists():
            with open(filepath, 'r') as f:
                ids = json.load(f)
                if not isinstance(ids, list): # Store as list, convert to set
                    logger.warning(f"Matched IDs file {filepath} does not contain a list. Starting fresh.")
                    return set()
                return set(ids)
        return set()
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading matched IDs from {filepath}: {e}. Starting with an empty set.")
        return set()

def save_matched_ids(filepath: Path, ids: Set[str]) -> None:
    """Saves a set of matched transaction IDs to a JSON file."""
    try:
        if not filepath.parent.exists():
            filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(list(ids), f, indent=4) # Store as list
        logger.info(f"Saved {len(ids)} matched IDs to {filepath}")
    except IOError as e:
        logger.error(f"Error saving matched IDs to {filepath}: {e}")

# Example usage (optional, for testing)
# if __name__ == '__main__':
#     setup_logging('logs/test.log')
#     config = load_config()
#     print(config)
