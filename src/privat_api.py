import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import the library client and its potential error class
from sync_privat.manager import SyncPrivatManager
# Assuming the error class is here - VERIFY THIS IMPORT PATH

from models import NormalizedTransaction

# Get a logger specific to this module
logger = logging.getLogger(__name__)

class PrivatBankClient:
    """
    Client for interacting with the PrivatBank API using the sync_privat library.
    Handles fetching transactions and balance for a specific IBAN.
    """
    def __init__(self, config: Dict[str, Any], sync_days_lookback: int):
        """
        Initializes the client with configuration.

        Args:
            config: PrivatBank configuration dictionary containing 'token' and 'iban'.
            sync_days_lookback: Number of days ago to fetch statements for (used as 'period').
        """
        # Use correct config keys: token and iban
        self.token: Optional[str] = config.get('token')
        self.iban: Optional[str] = config.get('iban')
        self.sync_days_lookback: int = sync_days_lookback # Store lookback period

        if not self.token:
            logger.error("PrivatBank token missing in config.")
            raise ValueError("Missing PrivatBank token in configuration")
        if not self.iban:
             logger.error("PrivatBank iban missing in config.")
             raise ValueError("Missing PrivatBank IBAN in configuration")

        # Initialize the library client with token and iban
        try:
            logger.debug(f"Attempting to initialize SyncPrivatManager with token: {'***' if self.token else 'None'} and IBAN: {self.iban[:6]}...") # DEBUG ADDED
            self.client = SyncPrivatManager(
              token=self.token,
              iban=self.iban
            )
            logger.info(f"PrivatBankClient initialized using SyncPrivatManager for IBAN: {self.iban[:6]}...") # Log partial IBAN for privacy
        except Exception as e:
            logger.error(f"Failed to initialize SyncPrivatManager: {e}", exc_info=True)
            raise

    def _normalize_transaction(self, tx_data: Dict[str, Any]) -> Optional[NormalizedTransaction]:
        """
        Normalizes a transaction dictionary from the library into a standard format.
        NOTE: Field names depend on the structure returned by privatbank-api-client.
              Inspect the library's response for accuracy.
        """
        try:
            # --- Field Name Verification COMPLETE ---
            # Keys updated based on debug output from sync_privat library
            tx_id = tx_data.get('ID') # Use 'ID' (uppercase)
            # Removed 'appcode' fallback as it wasn't seen in logs
            if not tx_id:
                 logger.warning(f"Skipping transaction due to missing ID: {tx_data}")
                 return None

            date_str = tx_data.get('DAT_OD') # Use 'DAT_OD' (date operation)
            time_str = tx_data.get('TIM_P')  # Use 'TIM_P' (time operation)
            transaction_time: Optional[datetime] = None
            if date_str and time_str:
                try:
                    # Adjust format to DD.MM.YYYY HH:MM
                    transaction_time = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse PrivatBank datetime: {date_str} {time_str} for tx {tx_id}")

            # Amount parsing: Use 'SUM'
            # Removed 'cardamount' logic
            amount_str = tx_data.get('SUM', '0') # Use 'SUM'
            amount_val: float = 0.0
            currency: Optional[str] = tx_data.get('CCY') # Get currency directly from 'CCY'
            try:
                # Amount seems to be just a number string now
                amount_val = float(amount_str)
                # Determine sign based on TRANTYPE ('C' = Credit, 'D' = Debit)
                if tx_data.get('TRANTYPE') == 'D':
                    amount_val = -abs(amount_val) # Ensure debits are negative
                else:
                    amount_val = abs(amount_val) # Ensure credits are positive

            except (ValueError, TypeError):
                 logger.warning(f"Could not parse PrivatBank amount string: '{amount_str}' for tx {tx_id}")
                 return None # Skip if amount is unparseable

            # Balance ('balance', 'rest') not found in logs, setting to None
            balance_val: Optional[float] = None
            # Removed balance parsing logic


            return NormalizedTransaction(
                id=str(tx_id), # Ensure ID is string
                time=transaction_time,
                amount=amount_val, # Amount now has correct sign
                currency=currency, # Use 'CCY'
                description=tx_data.get('OSND', ''), # Use 'OSND'
                balance_after=balance_val, # Set to None
                type='privat_transaction',
                raw=tx_data # Store the original dictionary
            )
            # --- End Field Name Verification ---
        except Exception as e:
            # Corrected lowercase 'id' to 'ID' here
            logger.warning(f"Could not normalize PrivatBank transaction (ID: {tx_data.get('ID', 'N/A')}): {e}", exc_info=True)
            return None


    def get_transactions(self, start_date_str: str, end_date_str: str) -> List[NormalizedTransaction]:
        """
        Fetches transactions using the sync_privat library for the configured lookback period.

        Args:
            start_date_str: Start date (YYYY-MM-DD) - Used for logging/context, not direct API call.
            end_date_str: End date (YYYY-MM-DD) - Used for logging/context, not direct API call.

        Returns:
            A list of normalized transaction objects for the period defined by sync_days_lookback.
        """
        normalized_transactions: List[NormalizedTransaction] = []
        if not self.client:
            logger.error("PrivatBank client not initialized.")
            return []
        try:
            # Use the stored lookback period for the API call
            period_days = self.sync_days_lookback
            # Set a reasonable limit for transactions per day (max 500, recommended 100)
            transaction_limit = 100 # Changed from 1000

            logger.info(f"Requesting PrivatBank statements via library for IBAN {self.iban[:6]}... for {period_days} days ago (limit: {transaction_limit}). Target range: {start_date_str} to {end_date_str}")
            logger.debug("Calling self.client.get_statement...")

            # Call the library's get_statement method with 'period' and 'limit'
            response_payload = self.client.get_statement(period=period_days, limit=transaction_limit)
            logger.debug(f"Raw PrivatBank library response payload (get_statement): {response_payload}")

            # Check response structure based on library's sync_request method
            if response_payload and isinstance(response_payload, dict) and response_payload.get('code') == 200:
                response_data = response_payload.get('detail')
                # --- !!! Response Structure Verification Needed !!! ---
                # Assuming the actual statement list is nested, e.g., within response_data['statements']
                # Adjust the key ('statements') based on the actual API response structure!
                # Corrected key based on debug output:
                statement_list = response_data.get('transactions') if isinstance(response_data, dict) else response_data

                if isinstance(statement_list, list):
                    logger.info(f"Received {len(statement_list)} raw records from PrivatBank library.")
                    for tx_data in statement_list:
                        if isinstance(tx_data, dict):
                            normalized = self._normalize_transaction(tx_data)
                            if normalized:
                                # --- FILTER ADDED: Only include expenses (negative amounts) ---
                                if normalized.amount < 0:
                                    # Optional: Add explicit date filtering here if library returns more than the target day(s)
                                    # if start_datetime <= normalized.time <= end_datetime:
                                    normalized_transactions.append(normalized)
                                else:
                                    pass # Keep the pass statement or remove the else block
                                # --- END FILTER ---
                        else:
                            logger.warning(f"Unexpected item type in PrivatBank statements list: {type(tx_data)}")
                elif statement_list:
                     logger.warning(f"Expected list in PrivatBank statements response detail, got: {type(statement_list)}")
                else:
                     logger.info("No transactions list found in PrivatBank library response for the period.")
            elif response_payload and isinstance(response_payload, dict):
                 logger.error(f"PrivatBank library returned error code {response_payload.get('code')}: {response_payload.get('detail')}")
            else:
                 logger.error(f"Unexpected or empty response from PrivatBank library get_statement: {response_payload}")

        except Exception as e:
            logger.error(f"An unexpected error occurred in PrivatBankClient.get_transactions: {e}", exc_info=True)

        return normalized_transactions

    def get_balance(self) -> Optional[float]:
        """
        Fetches the current balance using the privatbank-api-client library.

        Returns:
            The current account balance as a float, or None if an error occurs.
        """
        balance: Optional[float] = None
        if not self.client:
            logger.error("PrivatBank client not initialized.")
            return None
        try:
            logger.info(f"Requesting PrivatBank balance via library for IBAN {self.iban[:6]}...")
            logger.debug("Calling self.client.get_balance...")
            # Use the library's balance method - IBAN is likely implicit from initialization
            # VERIFY if get_balance takes any parameters
            response_payload = self.client.get_balance()
            logger.debug(f"Raw PrivatBank library response payload (get_balance): {response_payload}")

            # Check response structure based on library's sync_request method
            if response_payload and isinstance(response_payload, dict) and response_payload.get('code') == 200:
                response_data = response_payload.get('detail')
                # Assuming response_data is a dictionary like {'balance': '123.45'}
                if isinstance(response_data, dict):
                    balance_str = response_data.get('balance') # Key confirmed in library's get_balance
                    currency = None # Currency info might not be in this specific call
                    if balance_str:
                        try:
                            # Balance seems to be returned as just a number string
                            balance = float(balance_str)
                            logger.info(f"Fetched PrivatBank balance via library: {balance}")
                        except (ValueError, TypeError):
                            logger.error(f"Could not parse balance string from PrivatBank library response: '{balance_str}'")
                            balance = None # Ensure balance is None if parsing fails
                    else:
                        logger.warning("Balance key ('balance') not found in PrivatBank library response detail.")
                else:
                    logger.warning(f"Unexpected type for balance response detail: {type(response_data)}")
            elif response_payload and isinstance(response_payload, dict):
                 logger.error(f"PrivatBank library returned error code {response_payload.get('code')} fetching balance: {response_payload.get('detail')}")
            else:
                 logger.error(f"Unexpected or empty response from PrivatBank library get_balance: {response_payload}")

        except Exception as e:
            logger.error(f"An unexpected error occurred in PrivatBankClient.get_balance: {e}", exc_info=True)

        return balance

# Example usage remains commented out
# if __name__ == '__main__':
#     # ... (Update config loading for merchant_id/password) ...
