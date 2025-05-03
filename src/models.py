from datetime import datetime
from typing import Optional, Any, Literal, List, Dict
from pydantic import BaseModel, Field, validator, PositiveFloat
import logging # Added for validator logging

# Get a logger specific to this module
logger = logging.getLogger(__name__)

class NormalizedTransaction(BaseModel):
    """Standardized representation of a transaction from any source."""
    id: str | int # Source-specific ID
    time: Optional[datetime] = None
    amount: float # Positive for credit/income, negative for debit/expense
    currency: Optional[str] = None
    description: Optional[str] = ""
    balance_after: Optional[float] = None # Optional: Only if available from source
    type: Literal['privat_transaction', 'poster_payment'] # Source type
    raw: Optional[Any] = None # Store the original raw data for debugging

    class Config:
        # Allow storing raw data which might not be a standard Pydantic type
        arbitrary_types_allowed = True

# --- Poster Models ---

class PosterTransactionResponseItem(BaseModel):
    """Represents a single transaction item from Poster finance.getTransactions."""
    transaction_id: int
    date: Optional[str] = None # Added: Expect the date string from API
    date_create_timestamp: Optional[int] = None # Keep for potential future use or other endpoints
    amount: int # Changed from sum to amount
    comment: Optional[str] = ""
    # Add other relevant fields if needed, e.g., user_id, counter_agent_id

class PosterTransactionsResponse(BaseModel):
    """Overall structure for Poster finance.getTransactions response."""
    response: list[PosterTransactionResponseItem] = []

class PosterAccountResponseItem(BaseModel):
    """Represents a single account item from Poster finance.getAccounts."""
    account_id: int
    account_name: Optional[str] = Field(None, alias='name') # Map 'name' from JSON
    # Map the 'balance' field from JSON to 'account_balance' attribute
    # Pydantic will attempt to convert the string value to int
    account_balance: int = Field(..., alias='balance') # Balance in kopecks/cents
    account_currency: Optional[str] = Field(None, alias='currency_code') # Map 'currency_code' from JSON
    # Add other relevant fields if needed, using aliases if JSON names differ

class PosterAccountsResponse(BaseModel):
    """Overall structure for Poster finance.getAccounts response."""
    response: list[PosterAccountResponseItem] = []

class SyncReport(BaseModel):
    """Data structure holding the results of a synchronization comparison."""
    start_date: str
    end_date: str
    privat_transactions_count: int
    poster_transactions_count: int
    matched_pairs_count: int
    unmatched_privat: List[NormalizedTransaction] = []
    unmatched_poster: List[NormalizedTransaction] = []
    all_privat_transactions: List[NormalizedTransaction] = [] # Added
    all_poster_transactions: List[NormalizedTransaction] = [] # Added
    privat_balance: Optional[float] = None
    poster_balance: Optional[float] = None
    error_message: Optional[str] = None

    @property
    def has_discrepancies(self) -> bool:
        """Returns True if there are any unmatched transactions or a significant balance difference."""
        # Consider balance difference significant if > 0.01 (adjust tolerance as needed)
        balance_discrepancy = abs(self.balance_diff) > 0.01 if self.balance_diff is not None else False
        return bool(self.unmatched_privat or self.unmatched_poster or balance_discrepancy or self.error_message)

    @property
    def balance_diff(self) -> Optional[float]:
        """Calculates the difference between PrivatBank and Poster balances."""
        if self.privat_balance is not None and self.poster_balance is not None:
            return self.privat_balance - self.poster_balance
        return None
