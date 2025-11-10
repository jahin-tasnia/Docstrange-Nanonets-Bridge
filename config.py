# config.py
API_KEY = "Nanonets_API_Key"  # replace with your actual API key
URL = "https://extraction-api.nanonets.com/extract"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Defaults (the code will auto-adjust if API returns 413/504 etc.)
DEFAULT_CHUNK_SIZE = 10  # was 25
MIN_CHUNK_SIZE = 5  # floor for auto-shrinking
REQUEST_TIMEOUT = 300  # seconds
MAX_RETRIES = 3
RETRY_SLEEP_BASE = 2  # seconds (exponential backoff)

# NEW
POLL_SLEEP_SEC = 2  # wait between polls
POLL_MAX_SECONDS = 240  # per chunk, per mode
