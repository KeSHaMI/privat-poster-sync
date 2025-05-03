#!/bin/bash

# Deployment script for PrivatBank-Poster Sync Tool

# --- Configuration ---
# Set the absolute path to the project directory on the server
PROJECT_DIR="/root/code/privat-poster-sync"
# Set the name of the virtual environment directory
VENV_DIR="venv"
# Set the path to the main Python script
MAIN_SCRIPT="src/main.py"
# Set the path for the deployment log file
LOG_FILE="${PROJECT_DIR}/logs/deploy.log"
# Set the path for the cron execution log file (used if running via cron)
CRON_LOG_FILE="${PROJECT_DIR}/logs/cron_run.log"

# --- Script ---

# Function to log messages
log_message() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "${LOG_FILE}"
}

# Ensure the script exits if any command fails
set -e

log_message "Starting deployment script..."

# Navigate to the project directory
cd "${PROJECT_DIR}" || { log_message "Error: Could not navigate to project directory ${PROJECT_DIR}"; exit 1; }
log_message "Changed directory to ${PROJECT_DIR}"

# Create logs directory if it doesn't exist
mkdir -p logs
log_message "Ensured logs directory exists."

# Check if virtual environment exists, create if not
if [ ! -d "${VENV_DIR}" ]; then
  log_message "Virtual environment not found. Creating one at ${PROJECT_DIR}/${VENV_DIR}..."
  python3 -m venv "${VENV_DIR}" || { log_message "Error: Failed to create virtual environment."; exit 1; }
  log_message "Virtual environment created."
fi

# Activate virtual environment
source "${VENV_DIR}/bin/activate" || { log_message "Error: Failed to activate virtual environment."; exit 1; }
log_message "Activated virtual environment."

# Install/update dependencies
log_message "Installing/updating dependencies from requirements.txt..."
pip install -r requirements.txt || { log_message "Error: Failed to install dependencies."; deactivate; exit 1; }
log_message "Dependencies installed successfully."

# Run the main sync script
log_message "Running the main sync script (${MAIN_SCRIPT})..."
# Redirect script output to the cron log file if this script is run by cron
# Otherwise, output will go to stdout/stderr or wherever the deploy script's output is redirected
python "${MAIN_SCRIPT}" >> "${CRON_LOG_FILE}" 2>&1 || { log_message "Error: Main script execution failed. Check ${CRON_LOG_FILE} for details."; deactivate; exit 1; }
log_message "Main script finished successfully. Output logged to ${CRON_LOG_FILE}"

# Deactivate virtual environment
deactivate
log_message "Deactivated virtual environment."

log_message "Deployment script finished successfully."

# Exit cleanly
exit 0
