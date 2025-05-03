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
    def __init__(self, amount_tolerance: float = 0.01, time_window_minutes: int = 15):
        """
        Initializes the comparator with matching tolerances.

        Args:
            amount_tolerance: Maximum allowed difference between amounts.
            time_window_minutes: Maximum time difference (in minutes) allowed.
        """
        self.amount_tolerance: float = amount_tolerance
        self.time_window: timedelta = timedelta(minutes=time_window_minutes)
        logger.info(f"TransactionComparator initialized with tolerance +/-{amount_tolerance} and time window +/-{time_window_minutes} min.")

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

        # Track indices of matched transactions
        privat_indices_matched: Set[int] = set()
        poster_indices_matched: Set[int] = set()
        matched_pairs: List[Dict[str, NormalizedTransaction]] = []

        # Iterate through PrivatBank transactions (credits only for matching Poster payments)
        for i, p_tx in enumerate(privat_transactions):
            # Skip non-credits, transactions without time, or already matched ones
            if p_tx.amount <= 0 or p_tx.time is None or i in privat_indices_matched:
                continue

            best_match_j: int = -1
            min_time_diff: timedelta = self.time_window # Start with max allowed diff

            for j, s_tx in enumerate(poster_transactions):
                # Skip transactions without time or already matched ones
                if s_tx.time is None or j in poster_indices_matched:
                    continue

                # Check 1: Amount match
                amount_diff = abs(p_tx.amount - s_tx.amount)
                amount_match: bool = amount_diff <= self.amount_tolerance

                # Check 2: Time match
                time_diff: timedelta = abs(p_tx.time - s_tx.time)
                time_match: bool = time_diff <= self.time_window

                if amount_match and time_match:
                    # Found a potential match. Prefer the one closest in time if multiple exist.
                    if best_match_j == -1 or time_diff < min_time_diff:
                         min_time_diff = time_diff
                         best_match_j = j

            if best_match_j != -1:
                # Found a best match for this PrivatBank transaction
                matched_pairs.append({
                    'privat': p_tx,
                    'poster': poster_transactions[best_match_j]
                })
                privat_indices_matched.add(i)
                poster_indices_matched.add(best_match_j)
                # Corrected logging reference
                logger.debug(f"Matched Privat tx {p_tx.id} with Poster tx {poster_transactions[best_match_j].id}")
            else:
                pass

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
            if abs(balance_diff) > self.amount_tolerance: # Use tolerance for balance too
                 logger.warning(f"Significant balance difference detected: {balance_diff:.2f}")
            else:
                 logger.info("Balances match within tolerance.")
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
