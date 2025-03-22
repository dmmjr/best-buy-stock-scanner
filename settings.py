import os
from colorama import Fore, Style

# File paths
COOKIES_FILE = 'bestbuy_cookies.json'
USER_AGENTS_FILE = 'user_agents.json'
HEADERS_FILE = 'headers.json'
LOG_FILE = 'stock_scanner.log'

# Request settings
REQUEST_TIMEOUT = 15  # Increased timeout for slow connections

# Timing settings
DEFAULT_DELAY = 30    # Default delay between checks (seconds)
INSTOCK_DELAY = 5     # Reduced delay when product is in stock (seconds)
MAX_RETRIES = 3       # Maximum number of retries on failure
CACHE_TTL = 30        # Cache time-to-live (seconds)

# Batch processing
BATCH_SIZE = 3        # Number of concurrent checks to perform
BATCH_DELAY_MIN = 2.0 # Minimum delay between batches (seconds)
BATCH_DELAY_MAX = 5.0 # Maximum delay between batches (seconds)

# Formatting
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
TIME_PREFIX = f"{Fore.LIGHTBLACK_EX}{{timestamp}}{Style.RESET_ALL}"
IN_STOCK_MSG = f"{Fore.GREEN}{{product}} is {{status}}{Style.RESET_ALL}"
OUT_STOCK_MSG = f"{Fore.RED}{{product}} is {{status}}{Style.RESET_ALL}"

# Base URLs
BASE_URL = 'https://www.bestbuy.com'

# CSS Selectors for stock checking
BUTTON_SELECTORS = [
    'button.add-to-cart-button',
    'button[data-button-state="ADD_TO_CART"]',
    '.add-to-cart-button',
    # The SKU-specific selector is added dynamically
]

TEXT_SELECTORS = [
    '.fulfillment-add-to-cart-button',
    '.priceView-hero-price',
    '.priceView-customer-price'
]

# Protection detection selectors
PROTECTION_INDICATORS = [
    '#challenge-running',
    '.cf-browser-verification'
]
