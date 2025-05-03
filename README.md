# 100% vibe-coded with copilot and gemini 2.5 pro within 3 hours, use at own risk and/or pleasure

# PrivatBank-Poster Sync Tool

This script synchronizes financial transactions between a PrivatBank business account and a Poster POS account. It fetches transactions from both platforms for a specified lookback period, compares them based on amount and time proximity, and generates a report detailing matched pairs, unmatched transactions, and balance differences.

## Prerequisites

*   Python 3.10+
*   Access to a Linux or macOS environment (Windows might work but is untested)
*   Git

## Dependencies

This project uses the following key libraries:
*   `requests` (for Poster API)
*   `PyYAML` (for configuration)
*   `pydantic` (for data validation and models)
*   `privatbank-api-client` (for PrivatBank API interaction)
*   `python-telegram-bot` (for Telegram notifications)

## Setup

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd privat-poster-sync
    ```

2.  **Create a Virtual Environment:**
    It's highly recommended to use a virtual environment to manage dependencies.
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Linux/macOS
    # venv\Scripts\activate   # On Windows
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

The script uses a configuration file located at `config/config.yaml`. You need to create this file by copying `config/config.example.yaml` and populating it with your API credentials and settings.

**Example `config/config.example.yaml`:**
```yaml
# ... (contents of config.example.yaml) ...
```

**Steps:**

1.  Copy the example file:
    ```bash
    cp config/config.example.yaml config/config.yaml
    ```
2.  Edit `config/config.yaml` and replace the placeholder values with your actual credentials and settings.

**Obtaining Credentials:**

*   **PrivatBank:**
    *   **Token (`privatbank.token`):** You need an API token for the PrivatBank API (often referred to as Privat24 for Business API or similar). This usually involves registering your application or generating a token within your PrivatBank online banking interface (specifically for business clients). Refer to the official PrivatBank API documentation for the exact procedure for obtaining this token.
    *   **IBAN (`privatbank.iban`):** This is the International Bank Account Number of the specific account you want to fetch data for.

*   **Poster:**
    *   **Token (`poster.token`):** Generate an API access token in your Poster admin panel. Go to `Settings -> Integrations -> API Access`. Create a new token if needed. Ensure it has permissions to access `finance` methods (`finance.getTransactions`, `finance.getAccounts`).
    *   **Account ID (`poster.account_id`):** This is the internal ID Poster uses for the specific financial account you want to sync (e.g., your bank account registered within Poster). You can usually find this by making an API call to `finance.getAccounts` using your token.

*   **Telegram:**
    *   **Bot Token (`telegram.token`):**
        1.  Open Telegram and search for "BotFather".
        2.  Start a chat with BotFather and send the `/newbot` command.
        3.  Follow the instructions to choose a name and username for your bot.
        4.  BotFather will provide you with an **API token**. Copy this token and paste it into your `config.yaml`.
    *   **Chat ID (`telegram.chat_id`):** This is the ID of the user, group, or channel where the bot should send notifications.
        *   **For a private chat with the bot:** Send a message to your bot first. Then, you can find your user ID by talking to bots like `@userinfobot` or `@RawDataBot`.
        *   **For a group chat:**
            1.  Add your bot to the group.
            2.  Send any message in the group.
            3.  One way to get the group chat ID is to temporarily add `@RawDataBot` to the group, send a message, and look at the JSON output under `message.chat.id`. It will be a negative number (e.g., `-100123456789`). Remember to remove `@RawDataBot` afterwards if you don't need it.
            *Alternatively*, you can forward a message *from* the group to `@RawDataBot` and check the `forward_from_chat.id`.

**Important:** Keep your `config.yaml` file secure. It contains sensitive tokens. **Ensure `config/config.yaml` is listed in your `.gitignore` file (it is included in the provided `.gitignore`) and do not commit it to public repositories.** Consider using environment variables or a secrets management system for production deployments as a more robust alternative.

## Running the Script

Ensure your virtual environment is activated (`source venv/bin/activate`).

Run the main script from the project's root directory:

```bash
python src/main.py
```

The script will:

1.  Load the configuration.
2.  Fetch transactions and balances from PrivatBank and Poster for the configured period.
3.  Compare the data.
4.  Generate a `SyncReport` object.
5.  Log detailed information and any errors to the file specified in `settings.log_file` (default: `logs/sync.log`) and also print logs to the console.
6.  **Attempt to send a notification message with the sync report summary to the configured Telegram chat ID.**

## Logging

Logs are stored in the `logs/` directory (by default `logs/sync.log`). Check this file for detailed information about the sync process, fetched data (if debug logging is enabled), comparisons, and any errors encountered.

## Deployment (Cron Job)

To run the synchronization script automatically every day at midnight, you can set up a cron job.

1.  **Open the crontab editor:**
    ```bash
    crontab -e
    ```

2.  **Add the following line:**

    Make sure to replace `<path-to-your-project>` with the actual absolute path to your project directory. This command assumes your virtual environment is named `venv` and is located within the project root.

    ```cron
    0 0 * * * cd <path-to-your-project> && <path-to-your-project>/venv/bin/python <path-to-your-project>/src/main.py >> <path-to-your-project>/logs/cron.log 2>&1
    ```

    *   `0 0 * * *`: This specifies the schedule (midnight every day).
    *   `cd <path-to-your-project>`: Changes the directory to your project root before running the script. This is important so the script can find the `config/config.yaml` file and `logs` directory correctly.
    *   `<path-to-your-project>/venv/bin/python`: Specifies the Python interpreter within your virtual environment. **Adjust this path if your virtual environment is named differently or located elsewhere.**
    *   `<path-to-your-project>/src/main.py`: The path to the main script.
    *   `>> <path-to-your-project>/logs/cron.log 2>&1`: Redirects both standard output (stdout) and standard error (stderr) to a log file named `cron.log` inside your project's `logs` directory. This helps in debugging if the cron job fails silently.

3.  **Save and Exit:** Save the changes to your crontab (the method depends on the editor, often `Ctrl+X` then `Y` then `Enter` for nano).

The script will now run automatically every day at midnight. Check `logs/cron.log` for the output of each run.

## Project Structure

```
├── config/
│   ├── config.example.yaml # Configuration template
│   └── config.yaml       # Your configuration file (needs to be created, **should be gitignored**)
├── logs/                 # Log files will be created here (**should be gitignored**)
├── requirements.txt      # Python dependencies
├── src/                  # Source code
│   ├── comparator.py     # Logic for comparing transactions and balances
│   ├── main.py           # Main script execution flow
│   ├── models.py         # Pydantic models for API responses and reports
│   ├── poster_api.py     # Poster API client class
│   ├── privat_api.py     # PrivatBank API client class
│   ├── telegram_notifier.py # Handles Telegram notifications
│   └── utils.py          # Utility functions (config loading, logging setup)
├── .gitignore            # Specifies intentionally untracked files that Git should ignore
└── README.md             # This file
```
