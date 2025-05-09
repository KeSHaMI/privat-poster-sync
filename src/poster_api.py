import requests
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import ValidationError

from models import (
    NormalizedTransaction, PosterTransactionsResponse, PosterTransactionResponseItem,
    PosterAccountsResponse, PosterAccountResponseItem
)

# Get a logger specific to this module
logger = logging.getLogger(__name__)

POSTER_API_URL: str = "https://joinposter.com/api"

class PosterClient:
    """
    Client for interacting with the Poster POS API.
    Handles fetching filtered financial transactions.
    """
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the client with configuration.

        Args:
            config: Poster configuration dictionary containing 'token' and 'account_id'.
        """
        self.api_token: Optional[str] = config.get('token')
        # Ensure account_id is treated as string for consistency if needed, Poster API might expect int/string
        self.account_id: Optional[str | int] = config.get('account_id')
        self.base_url: str = POSTER_API_URL

        if not self.api_token or self.account_id is None: # Check for None explicitly
            raise ValueError("Poster API token or account_id missing in configuration.")
        logger.info("PosterClient initialized.")

    def _normalize_transaction(self, tx_data: PosterTransactionResponseItem) -> Optional[NormalizedTransaction]:
        """Normalizes a validated Poster transaction model into a standard format."""
        try:
            # Poster amounts are usually in cents/kopecks
            amount: float = float(tx_data.amount) / 100.0 # Changed tx_data.sum to tx_data.amount
            transaction_time: Optional[datetime] = None
            # --- Use the 'date' string field first ---
            if tx_data.date:
                try:
                    # Poster API date format: 'YYYY-MM-DD HH:MM:SS'
                    transaction_time = datetime.strptime(tx_data.date, '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse Poster date string: '{tx_data.date}' for tx {tx_data.transaction_id}")
            # --- Fallback to timestamp if date string is missing or failed to parse ---
            elif tx_data.date_create_timestamp:
                try:
                    transaction_time = datetime.fromtimestamp(tx_data.date_create_timestamp)
                except (ValueError, TypeError):
                     logger.warning(f"Could not convert Poster timestamp: {tx_data.date_create_timestamp} for tx {tx_data.transaction_id}")

            return NormalizedTransaction(
                id=tx_data.transaction_id,
                time=transaction_time,
                amount=amount, # Assuming positive amount means income/payment received
                currency=None, # Poster transactions usually don't specify currency here
                description=tx_data.comment,
                balance_after=None, # Not available in this Poster response
                type='poster_payment',
                raw=tx_data # Store the original Pydantic model
            )
        except Exception as e:
            logger.warning(f"Could not normalize Poster transaction {tx_data.transaction_id}: {e}", exc_info=True)
            return None

    def get_transactions(self, start_date_str: str, end_date_str: str) -> List[NormalizedTransaction]:
        """
        Fetches transactions from the Poster API for the configured account and date range.

        Args:
            start_date_str: Start date in 'YYYY-MM-DD' format.
            end_date_str: End date in 'YYYY-MM-DD' format.

        Returns:
            A list of normalized transaction objects.
        """
        # Poster API expects dates in YYYYMMDD format
        try:
            start_date_poster_fmt: str = datetime.strptime(start_date_str, '%Y-%m-%d').strftime('%Y%m%d')
            end_date_poster_fmt: str = datetime.strptime(end_date_str, '%Y-%m-%d').strftime('%Y%m%d')
        except ValueError:
            logger.error(f"Invalid date format provided to get_transactions. Use YYYY-MM-DD.")
            return []

        endpoint: str = "finance.getTransactions"
        params: Dict[str, Any] = {
            "token": self.api_token,
            "dateFrom": start_date_poster_fmt, # Changed from date_from
            "dateTo": end_date_poster_fmt,   # Changed from date_to
            "type": 0, # Changed from 1 (income) to 0 (expense)
            "account_id": self.account_id
        }
        url: str = f"{self.base_url}/{endpoint}"
        normalized_transactions: List[NormalizedTransaction] = []
        filtered_count = 0  # Counter for filtered transactions

        try:
            logger.info(f"Requesting Poster API: {url} with params (token hidden)")
            response = requests.get(url, params=params)
            response.raise_for_status()
            logger.debug(f"Raw Poster API response status: {response.status_code}")
            try:
                raw_response_json = response.json()
                logger.debug(f"Raw Poster API response JSON: {raw_response_json}")
                # Validate the response structure
                validated_response = PosterTransactionsResponse.parse_obj(raw_response_json)
                raw_transactions = validated_response.response

                logger.info(f"Received and validated {len(raw_transactions)} transactions from Poster API for account {self.account_id}.")

                for tx_data in raw_transactions:
                    normalized = self._normalize_transaction(tx_data)
                    if normalized and normalized.amount < 0: # Only include expenses
                        # Filter out transactions with "Комісія" or "комісія" in description (case-insensitive)
                        if normalized.description and "комісія" in normalized.description.lower():
                            logger.debug(f"Filtered out Poster transaction with 'комісія' (case-insensitive) in description: {normalized.id}")
                            filtered_count += 1
                        else:
                            normalized_transactions.append(normalized)

            except ValidationError as e:
                logger.error(f"Poster API response validation failed: {e}")
                logger.error(f"Response text: {response.text[:500]}...")
                return []
            except ValueError as e: # Includes JSONDecodeError
                logger.error(f"Error decoding Poster API response: {e}")
                logger.error(f"Response text: {response.text[:500]}...")
                return []

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from Poster API: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred in PosterClient.get_transactions: {e}", exc_info=True)

        # --- Manual date filtering removed ---

        if filtered_count > 0:
            logger.info(f"Filtered out {filtered_count} Poster transactions with 'Комісія' in description")

        logger.info(f"Fetched {len(normalized_transactions)} expense transactions directly from Poster API.")
        return normalized_transactions # Return the transactions fetched (already filtered by API)

    def get_balance(self) -> Optional[float]:
        """
        Fetches the current balance for the configured Poster account_id.

        Returns:
            The current account balance as a float, or None if an error occurs.
        """
        endpoint: str = "finance.getAccounts"
        params: Dict[str, Any] = {"token": self.api_token}
        url: str = f"{self.base_url}/{endpoint}"
        balance: Optional[float] = None

        try:
            logger.info(f"Requesting Poster API: {url} for accounts")
            response = requests.get(url, params=params)
            response.raise_for_status()

            try:
                # Validate the response structure
                validated_response = PosterAccountsResponse.parse_obj(response.json())
                accounts = validated_response.response

                logger.info(f"Received {len(accounts)} accounts from Poster API.")

                # Find the account matching the configured account_id
                target_account_id = int(self.account_id) # Ensure comparison is int vs int
                found_account: Optional[PosterAccountResponseItem] = None
                for acc in accounts:
                    if acc.account_id == target_account_id:
                        found_account = acc
                        break

                if found_account:
                    # Convert balance from kopecks/cents
                    balance = float(found_account.account_balance) / 100.0
                    logger.info(f"Found Poster account {self.account_id} balance: {balance} {found_account.account_currency or ''}")
                else:
                    logger.error(f"Configured Poster account_id {self.account_id} not found in API response.")

            except ValidationError as e:
                logger.error(f"Poster Accounts API response validation failed: {e}")
                logger.error(f"Response text: {response.text[:500]}...")
                return None
            except ValueError as e: # Includes JSONDecodeError or int conversion error
                logger.error(f"Error decoding/processing Poster Accounts API response: {e}")
                logger.error(f"Response text: {response.text[:500]}...")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching accounts from Poster API: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred in PosterClient.get_balance: {e}", exc_info=True)

        return balance

# Example usage (optional, for testing)
# if __name__ == '__main__':
#     from utils import load_config, setup_logging
#     config = load_config()
#     setup_logging(config['settings']['log_file'])
#     client = PosterClient(config['poster'])
#     start = '2025-04-30'
#     end = '2025-05-01'
#     poster_trans = client.get_transactions(start, end)
#     print(f"Fetched {len(poster_trans)} normalized Poster transactions.")
