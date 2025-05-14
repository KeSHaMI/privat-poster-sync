import logging
from typing import Dict, Any, Optional, List
import telegram
from telegram.constants import ParseMode
from telegram.error import TelegramError

from models import SyncReport, NormalizedTransaction

# Get a logger specific to this module
logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Handles sending notifications via a Telegram bot."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the notifier with Telegram bot configuration.

        Args:
            config: Dictionary containing 'token' and 'chat_id'.
        """
        self.bot_token: Optional[str] = config.get('token')
        self.chat_id: Optional[str] = config.get('chat_id') # Can be a user ID or group chat ID (negative number)
        self.bot: Optional[telegram.Bot] = None

        if not self.bot_token:
            logger.warning("Telegram bot token not found in config. Notifications disabled.")
            return
        if not self.chat_id:
            logger.warning("Telegram chat_id not found in config. Notifications disabled.")
            return

        try:
            self.bot = telegram.Bot(token=self.bot_token)
            logger.info(f"TelegramNotifier initialized for chat ID: {self.chat_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Telegram Bot: {e}", exc_info=True)
            self.bot = None # Ensure bot is None if init fails

    def _format_transaction(self, tx: NormalizedTransaction, is_unmatched: bool) -> str:
        """Formats a single transaction for the message, indicating if unmatched."""
        marker = "❗" if is_unmatched else "✅"
        # Use shorter date format: YYYY-MM-DD HH:MM
        time_str = tx.time.strftime('%Y-%m-%d %H:%M') if tx.time else "Немає часу"
        # Use the full description, don't truncate
        desc = tx.description
        # Sanitize description: remove Markdown special characters
        if desc:
            desc = desc.replace('*', '').replace('_', '').replace('`', '')

        # Use monospace for amounts for better alignment
        amount_str = f"`{tx.amount:<8.2f}`"
        currency_str = tx.currency or ''
        # Removed ID from the output string
        desc_str = desc or 'Н/Д' # N/A -> Н/Д
        return f"  {marker} {time_str}, {amount_str} {currency_str}, Опис: {desc_str}" # Desc: -> Опис:

    def _format_report_message(self, report: SyncReport) -> str:
        """Formats the SyncReport into a string message for Telegram."""
        lines = []
        status_icon = "✅" if not report.has_discrepancies and not report.error_message else "⚠️"
        # Translate "Sync Report:" and "to"
        lines.append(f"{status_icon} *Звіт синхронізації: {report.start_date} до {report.end_date}*" )
        lines.append("-" * 20)

        if report.error_message:
            # Translate "ERROR:"
            lines.append(f"🚨 *ПОМИЛКА:* {report.error_message}")
            lines.append("-" * 20)
            return "\n".join(lines) # Stop here if there was a critical error

        # Summary Counts - Translate labels
        lines.append(f"Privat Отримано: {report.privat_transactions_count}")
        lines.append(f"Poster Отримано: {report.poster_transactions_count}")
        lines.append(f"Зіставлено пар: {report.matched_pairs_count}")
        lines.append(f"Незбігів Privat: {len(report.unmatched_privat)}")
        lines.append(f"Незбігів Poster: {len(report.unmatched_poster)}")

        # Balances - Translate labels
        if report.privat_balance is not None:
            lines.append(f"Баланс Privat: `{report.privat_balance:.2f}`")
        if report.poster_balance is not None:
            lines.append(f"Баланс Poster: `{report.poster_balance:.2f}`")
        if report.balance_diff is not None:
            diff_sign = "+" if report.balance_diff > 0 else ""
            balance_match_icon = "✅" if abs(report.balance_diff) <= 0.01 else "❗"
            # Translate "Balance Difference (Privat - Poster):"
            lines.append(f"Різниця балансів (Privat - Poster): {balance_match_icon} `{diff_sign}{report.balance_diff:.2f}`")
        lines.append("-" * 20)

        # Create sets of unmatched IDs for quick lookup
        unmatched_privat_ids = {tx.id for tx in report.unmatched_privat}
        unmatched_poster_ids = {tx.id for tx in report.unmatched_poster}

        # All Privat Transactions - Translate label
        lines.append(f"*Транзакції PrivatBank ({report.privat_transactions_count}):*")
        if report.all_privat_transactions:
            for tx in report.all_privat_transactions:
                is_unmatched = tx.id in unmatched_privat_ids
                lines.append(self._format_transaction(tx, is_unmatched))
        else:
            lines.append("  (Немає)") # Translate "(None)"
        lines.append("-" * 20)

        # All Poster Transactions - Translate label
        lines.append(f"*Транзакції Poster ({report.poster_transactions_count}):*")
        if report.all_poster_transactions:
            for tx in report.all_poster_transactions:
                is_unmatched = tx.id in unmatched_poster_ids
                lines.append(self._format_transaction(tx, is_unmatched))
        else:
            lines.append("  (Немає)") # Translate "(None)"
        lines.append("-" * 20)

        if not report.has_discrepancies:
             # Translate "Sync successful, no discrepancies found."
             lines.append("✅ Синхронізація успішна, розбіжностей не знайдено.")
        elif not report.unmatched_privat and not report.unmatched_poster:
             # Translate "Discrepancy found in balances only."
             lines.append("⚠️ Виявлено розбіжність лише в балансах.")

        # Limit total message length if necessary (Telegram limit is 4096 chars)
        message = "\n".join(lines)
        parse_mode = ParseMode.MARKDOWN # Default to Markdown
        # The old truncation logic is removed, splitting will be handled in send_notification

        return message, parse_mode # Return both message and parse_mode

    async def send_notification(self, report: SyncReport) -> None:
        """
        Sends the formatted report as a Telegram message.
        If the message is too long, it splits it into multiple messages.

        Args:
            report: The SyncReport object.
        """
        if not self.bot or not self.chat_id:
            logger.warning("Telegram bot not initialized or chat_id missing. Skipping notification.")
            return

        full_message, parse_mode = self._format_report_message(report) # Get message and parse_mode

        # Telegram's maximum message length is 4096 characters.
        # We use a slightly smaller limit to be safe, especially with Markdown.
        MAX_MESSAGE_LENGTH = 4000

        if len(full_message) <= MAX_MESSAGE_LENGTH:
            messages_to_send = [full_message]
        else:
            logger.info(f"Message length ({len(full_message)}) exceeds {MAX_MESSAGE_LENGTH}. Splitting into multiple messages.")
            messages_to_send = []
            current_chunk = ""
            for line in full_message.split('\n'):
                # Check if adding the next line (plus a newline character) would exceed the limit
                if len(current_chunk) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                    if current_chunk: # Send the current chunk if it's not empty
                        messages_to_send.append(current_chunk)
                    current_chunk = line # Start a new chunk with the current line
                else:
                    if current_chunk: # Add a newline if it's not the first line of the chunk
                        current_chunk += "\n"
                    current_chunk += line

            if current_chunk: # Add the last remaining chunk
                messages_to_send.append(current_chunk)

            if not messages_to_send: # Should not happen if full_message was not empty
                 messages_to_send = [full_message[:MAX_MESSAGE_LENGTH]]


        try:
            logger.info(f"Sending Telegram notification to chat ID: {self.chat_id} ({len(messages_to_send)} part(s))")
            for i, message_part in enumerate(messages_to_send):
                if not message_part.strip(): # Skip empty messages
                    continue
                logger.debug(f"Sending part {i+1}/{len(messages_to_send)}, length: {len(message_part)}")
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message_part,
                    parse_mode=parse_mode # Use the determined parse_mode for all parts
                )
            logger.info("Telegram notification sent successfully.")
        except TelegramError as e:
            logger.error(f"Failed to send Telegram notification: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during Telegram notification sending: {e}", exc_info=True)
