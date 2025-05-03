import logging
import asyncio # Import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional

from utils import load_config, setup_logging
from privat_api import PrivatBankClient
from poster_api import PosterClient
from comparator import TransactionComparator
from models import NormalizedTransaction, SyncReport
from telegram_notifier import TelegramNotifier # Import the notifier

# Get a logger specific to this module
logger = logging.getLogger(__name__)

class SyncManager:
    """
    Orchestrates the synchronization process between PrivatBank and Poster.
    """
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the manager with configuration and sets up clients.
        """
        self.config: Dict[str, Any] = config
        self.settings: Dict[str, Any] = config.get('settings', {})
        self.privat_client: PrivatBankClient = PrivatBankClient(config['privatbank'], sync_days_lookback=int(self.settings.get('sync_days_lookback', 1)))
        self.poster_client: PosterClient = PosterClient(config['poster'])
        self.comparator: TransactionComparator = TransactionComparator(
            amount_tolerance=float(self.settings.get('amount_tolerance', 0.01)),
            time_window_minutes=int(self.settings.get('time_window_minutes', 15))
        )
        logger.info("SyncManager initialized.")

    def _get_date_range(self) -> Tuple[str, str]:
        """Calculates the start and end dates for synchronization."""
        lookback_days: int = int(self.settings.get('sync_days_lookback', 1))
        end_date: datetime.date = datetime.now().date()
        start_date: datetime.date = end_date - timedelta(days=lookback_days)
        date_format: str = self.settings.get('date_format', '%Y-%m-%d')
        start_date_str: str = start_date.strftime(date_format)
        end_date_str: str = end_date.strftime(date_format)
        return start_date_str, end_date_str

    def run_sync(self) -> SyncReport:
        """
        Executes the full synchronization process and returns a report object.
        """
        logger.info("Starting PrivatBank-Poster Sync Process")
        start_date_str, end_date_str = self._get_date_range()
        logger.info(f"Syncing data from {start_date_str} to {end_date_str}")

        privat_transactions: List[NormalizedTransaction] = []
        poster_transactions: List[NormalizedTransaction] = []
        privat_balance: Optional[float] = None
        poster_balance: Optional[float] = None
        report: Optional[SyncReport] = None # Initialize report
        sync_error_message: Optional[str] = None

        try:
            # --- Phase 1: Fetch Data ---
            # ... (fetching logic remains the same) ...
            privat_transactions = self.privat_client.get_transactions(start_date_str, end_date_str)
            logger.info(f"Fetched {len(privat_transactions)} transactions from PrivatBank.")
            privat_balance = self.privat_client.get_balance()

            poster_transactions = self.poster_client.get_transactions(start_date_str, end_date_str)
            logger.info(f"Fetched {len(poster_transactions)} relevant records from Poster.")
            poster_balance = self.poster_client.get_balance()

            # --- Phase 2: Compare Data & Generate Report ---
            logger.info("Comparing datasets and generating report...")
            # Comparator now returns the final report object
            report = self.comparator.compare(
                privat_transactions=privat_transactions,
                poster_transactions=poster_transactions,
                start_date_str=start_date_str,
                end_date_str=end_date_str,
                privat_balance=privat_balance,
                poster_balance=poster_balance,
                error_message=None # Pass None initially, error handled below
            )

        except Exception as e:
            logger.error(f"An critical error occurred during the sync process: {e}", exc_info=True)
            sync_error_message = f"Sync failed: {e}" # Capture error message
            # Create a basic error report if comparison couldn't happen
            report = SyncReport(
                start_date=start_date_str,
                end_date=end_date_str,
                privat_transactions_count=len(privat_transactions),
                poster_transactions_count=len(poster_transactions),
                matched_pairs_count=0,
                error_message=sync_error_message
            )

        logger.info("PrivatBank-Poster Sync Process Finished")

        # --- Phase 3: Finalize Report (Add error if sync failed after comparison) ---
        if report and sync_error_message and not report.error_message:
             # If an error happened *after* comparison but before this point
             # (less likely now, but good practice)
             report.error_message = sync_error_message
        elif not report: # Should not happen if try/except is structured correctly, but safety check
             report = SyncReport(
                start_date=start_date_str,
                end_date=end_date_str,
                privat_transactions_count=len(privat_transactions),
                poster_transactions_count=len(poster_transactions),
                matched_pairs_count=0,
                error_message="Sync failed to produce a report."
            )

        return report # Return the final report object

# Make main async
async def main() -> None:
    """Main entry point for the script."""
    config = {}
    report: Optional[SyncReport] = None
    notifier: Optional[TelegramNotifier] = None

    try:
        config = load_config()
        log_file = config.get('settings', {}).get('log_file', 'logs/sync.log')
        setup_logging(log_file)
        logger.debug("Logging setup complete in main. Debug messages should now appear.") # DEBUG ADDED

        # Initialize Notifier
        notifier = None # Initialize notifier to None
        if 'telegram' in config:
            notifier = TelegramNotifier(config['telegram'])
            logger.info("Telegram notifier initialized.")
        else:
            logger.warning("Telegram configuration not found, notifier disabled.")

        manager = SyncManager(config)
        report = manager.run_sync() # Capture the report

        # --- Handle the Report ---
        if report:
            log_message = f"Sync report generated for period {report.start_date} to {report.end_date}."
            if report.error_message:
                 log_message = f"Sync process completed with error: {report.error_message}"
                 logger.error(log_message)
            elif report.has_discrepancies:
                 log_message = f"Sync process completed with discrepancies."
                 logger.warning(log_message)
            else:
                 log_message = f"Sync process completed successfully with no discrepancies."
                 logger.info(log_message)

            # Send notification if notifier is configured and report exists
            if notifier:
                await notifier.send_notification(report) # Await the async call

    except FileNotFoundError:
        err_msg = "ERROR: Configuration file not found. Please ensure config/config.yaml exists."
        try: logger.error("Configuration file not found.")
        except: pass
        # Try sending error via Telegram if possible
        if notifier: await notifier.send_notification(SyncReport(
            start_date="N/A",
            end_date="N/A",
            privat_transactions_count=0, # Added default
            poster_transactions_count=0, # Added default
            matched_pairs_count=0,
            error_message=err_msg
            ))

    except (ValueError, TypeError, KeyError) as e:
        err_msg = f"ERROR: Configuration error - {e}"
        if config: logger.error(f"Configuration error: {e}", exc_info=True)
        if notifier: await notifier.send_notification(SyncReport(
            start_date="N/A",
            end_date="N/A",
            privat_transactions_count=0, # Added default
            poster_transactions_count=0, # Added default
            matched_pairs_count=0,
            error_message=err_msg
            ))

    except Exception as e:
        err_msg = f"An unexpected error occurred in main: {e}"
        if config: logger.error(f"An unexpected error occurred in main: {e}", exc_info=True)
        if notifier: await notifier.send_notification(SyncReport(
            start_date="N/A",
            end_date="N/A",
            privat_transactions_count=0, # Added default
            poster_transactions_count=0, # Added default
            matched_pairs_count=0,
            error_message=err_msg
            ))


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
