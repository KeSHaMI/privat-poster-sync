import logging
from datetime import timedelta, datetime
from typing import List, Dict, Any, Set, Tuple, Optional

from models import NormalizedTransaction, SyncReport # Added SyncReport import

# Get a logger specific to this module
logger = logging.getLogger(__name__)

class TransactionComparator:
    """
    Compares lists of transactions from two sources (e.g., PrivatBank and Poster)
    to find matches and discrepancies based on amount and time proximity.
    """
    def __init__(self, amount_tolerance: float = 2):
        """
        Initializes the comparator with matching tolerances.

        Args:
            amount_tolerance: Maximum allowed difference between amounts.
                              For transactions with "Метро" in description, a 10% tolerance is used.
        """
        self.amount_tolerance: float = amount_tolerance
        logger.info(f"TransactionComparator initialized with standard tolerance +/-{amount_tolerance} " +
                   f"and special 10% tolerance for transactions with 'Метро' in description")

    def compare(self, privat_transactions: List[NormalizedTransaction],
                poster_transactions: List[NormalizedTransaction],
                start_date_str: str, # Added
                end_date_str: str,   # Added
                privat_balance: Optional[float] = None,
                poster_balance: Optional[float] = None,
                error_message: Optional[str] = None) -> SyncReport: # Return type is SyncReport, added error_message param
        """
        Compares transactions and balances.

        Args:
            privat_transactions: List of normalized transactions from PrivatBank.
            poster_transactions: List of normalized transactions from Poster.
            start_date_str: Start date of the period being compared.
            end_date_str: End date of the period being compared.
            privat_balance: Current balance from PrivatBank (optional).
            poster_balance: Current balance from Poster (optional).
            error_message: Any critical error message encountered before comparison.

        Returns:
            A SyncReport object containing the comparison results.
        """
        logger.info(f"Starting comparison: {len(privat_transactions)} PrivatBank tx, {len(poster_transactions)} Poster tx.")

        # Log transaction details for debugging
        for i, tx in enumerate(privat_transactions):
            logger.debug(f"Privat tx {i}: id={tx.id}, amount={tx.amount:.2f}, time={tx.time}")
        for i, tx in enumerate(poster_transactions):
            logger.debug(f"Poster tx {i}: id={tx.id}, amount={tx.amount:.2f}, time={tx.time}")

        # Track indices of matched transactions
        privat_indices_matched: Set[int] = set()
        poster_indices_matched: Set[int] = set()
        matched_pairs: List[Dict[str, NormalizedTransaction]] = []

        # Iterate through PrivatBank transactions (match all transactions, not just credits)
        for i, p_tx in enumerate(privat_transactions):
            # Skip transactions without time or already matched ones
            if p_tx.time is None or i in privat_indices_matched:
                continue

            best_match_j: int = -1
            best_match_diff: float = float('inf')  # Track the smallest amount difference

            for j, s_tx in enumerate(poster_transactions):
                # Skip transactions without time or already matched ones
                if s_tx.time is None or j in poster_indices_matched:
                    continue

                # Check for sign consistency (both positive or both negative)
                same_sign = (p_tx.amount > 0 and s_tx.amount > 0) or (p_tx.amount < 0 and s_tx.amount < 0)

                # Check for special case: transactions with "Метро" in description get 10% tolerance
                is_metro_transaction = False
                if p_tx.description and "Метро" in p_tx.description:
                    is_metro_transaction = True
                    # Calculate 10% of the transaction amount as tolerance
                    metro_tolerance = abs(p_tx.amount) * 0.1
                    # Use the higher of the two tolerances
                    effective_tolerance = max(self.amount_tolerance, metro_tolerance)
                    logger.debug(f"Using special 10% tolerance for Метро transaction: {effective_tolerance:.2f}")
                else:
                    effective_tolerance = self.amount_tolerance

                # Check for amount match
                amount_diff = abs(p_tx.amount - s_tx.amount)
                amount_match: bool = same_sign and amount_diff <= effective_tolerance

                # Log potential near-matches that are just outside tolerance
                if not amount_match:
                    if not same_sign:
                        logger.debug(f"Sign mismatch: Privat tx {p_tx.id} ({p_tx.amount:.2f}) with Poster tx {s_tx.id} ({s_tx.amount:.2f})")
                    elif amount_diff <= effective_tolerance * 2:
                        tolerance_type = "10% Метро" if is_metro_transaction else "standard"
                        logger.debug(f"Near match skipped: Privat tx {p_tx.id} ({p_tx.amount:.2f}) with Poster tx {s_tx.id} ({s_tx.amount:.2f}), diff: {amount_diff:.2f} > {tolerance_type} tolerance {effective_tolerance:.2f}")

                if amount_match:
                    # Found a potential match. Prefer exact matches (amount_diff == 0) over close matches
                    if best_match_j == -1 or amount_diff < best_match_diff:
                        best_match_j = j
                        best_match_diff = amount_diff

            if best_match_j != -1:
                # Found a best match for this PrivatBank transaction
                matched_pairs.append({
                    'privat': p_tx,
                    'poster': poster_transactions[best_match_j]
                })
                privat_indices_matched.add(i)
                poster_indices_matched.add(best_match_j)

                # Determine if this was a Метро transaction match
                is_metro_match = p_tx.description and "Метро" in p_tx.description
                tolerance_type = "10% Метро" if is_metro_match else "standard"

                # Enhanced logging with amount difference and tolerance type information
                logger.debug(f"Matched Privat tx {p_tx.id} with Poster tx {poster_transactions[best_match_j].id} " +
                             f"(amount diff: {best_match_diff:.2f}, using {tolerance_type} tolerance)")
            else:
                # Log why this transaction wasn't matched
                logger.debug(f"No match found for Privat tx {p_tx.id} (amount: {p_tx.amount:.2f}, time: {p_tx.time})")

        # Filter out matched transactions
        final_unmatched_privat: List[NormalizedTransaction] = [
            tx for i, tx in enumerate(privat_transactions) if i not in privat_indices_matched
        ]
        final_unmatched_poster: List[NormalizedTransaction] = [
            tx for i, tx in enumerate(poster_transactions) if i not in poster_indices_matched
        ]

        logger.info(f"Comparison finished: {len(matched_pairs)} pairs matched.")
        logger.info(f"Unmatched PrivatBank transactions: {len(final_unmatched_privat)}")
        logger.info(f"Unmatched Poster transactions: {len(final_unmatched_poster)}")


        # --- Balance Comparison ---
        balance_diff: Optional[float] = None
        if privat_balance is not None and poster_balance is not None:
            balance_diff = privat_balance - poster_balance
            logger.info(f"Balance Comparison: Privat={privat_balance}, Poster={poster_balance}, Diff={balance_diff:.2f}")
            # Always use the standard tolerance for balance comparison, not the special "Метро" tolerance
            if abs(balance_diff) > self.amount_tolerance:
                 logger.warning(f"Significant balance difference detected: {balance_diff:.2f}")
            else:
                 logger.info(f"Balances match within standard tolerance (+/-{self.amount_tolerance}).")
        else:
            logger.warning("Balance comparison skipped: one or both balances not provided.")
        # ---

        # Return the comparison results
        report = SyncReport(
            start_date=start_date_str,
            end_date=end_date_str,
            privat_transactions_count=len(privat_transactions),
            poster_transactions_count=len(poster_transactions),
            matched_pairs_count=len(matched_pairs),
            unmatched_privat=final_unmatched_privat, # Use final list
            unmatched_poster=final_unmatched_poster, # Use final list
            all_privat_transactions=privat_transactions, # Added
            all_poster_transactions=poster_transactions, # Added
            privat_balance=privat_balance,
            poster_balance=poster_balance,
            error_message=error_message # Pass potential error message
        )

        log_message = (
            f"Comparison Report ({start_date_str} to {end_date_str}): "
            f"Privat={len(privat_transactions)}, Poster={len(poster_transactions)}, "
            f"Matched={len(matched_pairs)}, Unmatched Privat={len(final_unmatched_privat)}, "
            f"Unmatched Poster={len(final_unmatched_poster)}"
        )
        if report.balance_diff is not None:
            log_message += f", Balance Diff={report.balance_diff:.2f}"
        if report.error_message:
            log_message += f", ERROR={report.error_message}"
            logger.error(log_message)
        elif report.has_discrepancies:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        return report

# Example usage (optional, for testing)
# if __name__ == '__main__':
#     # ... (Create dummy NormalizedTransaction objects for testing) ...
#     from utils import setup_logging
#     setup_logging('logs/test_compare.log')
#     comparator = TransactionComparator()
#     # results = comparator.compare(privat_tx_list, poster_tx_list)
#     # ... (print results) ...
