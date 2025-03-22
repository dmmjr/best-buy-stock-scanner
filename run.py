import os
from dotenv import load_dotenv
import asyncio
import aiohttp
from yarl import URL  # Add this import
import random
import json
from datetime import datetime
from time import time
from sys import exit
from bs4 import BeautifulSoup
from colorama import Fore, Style, init
import logging
import http.cookies

# Load environment variables from .env file
load_dotenv()

# Initialize colorama once
init()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_scanner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("stock_scanner")

# Constants
REQUEST_TIMEOUT = 15  # Increased timeout
DEFAULT_DELAY = 30
INSTOCK_DELAY = 5
MAX_RETRIES = 3
CACHE_TTL = 30  # Reduced cache TTL for fresher content
COOKIES_FILE = 'bestbuy_cookies.json'
USER_AGENTS_FILE = 'user_agents.json'

# Pre-formatted strings
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
TIME_PREFIX = f"{Fore.LIGHTBLACK_EX}{{timestamp}}{Style.RESET_ALL}"
IN_STOCK_MSG = f"{Fore.GREEN}{{gpu}} is {{status}}{Style.RESET_ALL}"
OUT_STOCK_MSG = f"{Fore.RED}{{gpu}} is {{status}}{Style.RESET_ALL}"

# Configuration  
discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
discord_user_ids = os.getenv('DISCORD_USER_IDS', '').split(',')

# Rotating user agents to avoid detection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/123.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def get_random_headers():
    """Generate random headers to mimic different browsers"""
    user_agent = random.choice(USER_AGENTS)
    return {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.bestbuy.com/',
        'sec-ch-ua': '"Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'Upgrade-Insecure-Requests': '1',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-dest': 'document',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive'
    }

# Cookie management functions
def save_cookies(cookies_dict):
    """Save cookies to a file"""
    try:
        with open(COOKIES_FILE, 'w') as f:
            json.dump(cookies_dict, f)
    except Exception as e:
        logger.error(f"Error saving cookies: {e}")

def load_cookies():
    """Load cookies from a file"""
    try:
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading cookies: {e}")
    return {}

def extract_cookies_from_response(response):
    """Extract cookies from response headers"""
    cookies_dict = {}
    if 'Set-Cookie' in response.headers:
        for cookie_str in response.headers.getall('Set-Cookie', []):
            cookie = http.cookies.SimpleCookie()
            cookie.load(cookie_str)
            for key, morsel in cookie.items():
                cookies_dict[key] = morsel.value
    return cookies_dict

def update_session_cookies(session, new_cookies):
    """Update session cookies with new values"""
    if not new_cookies:
        return
    for name, value in new_cookies.items():
        session.cookie_jar.update_cookies({name: value})

# GPU tracking from environment variables
gpus = {}

# Parse GPU environment variables
for i in range(1, 10):  # Support up to 9 GPUs
    gpu_name = os.getenv(f'GPU_{i}_NAME')
    gpu_url = os.getenv(f'GPU_{i}_URL')
    
    if gpu_name and gpu_url:
        gpus[gpu_name] = {
            'url': gpu_url,
        }

# If no GPUs defined in env vars, use defaults
if not gpus:
    logger.warning("No GPUs defined in environment variables. Using defaults.")
    gpus = { 
        'RTX 5090 FE': {
            'url': 'https://www.bestbuy.com/site/nvidia-geforce-rtx-5090-32gb-gddr7-graphics-card-dark-gun-metal/6614151.p?skuId=6614151',
        },
        'RTX 5080 FE': {
            'url': 'https://www.bestbuy.com/site/nvidia-geforce-rtx-5080-16gb-gddr7-graphics-card-gun-metal/6614153.p?skuId=6614153',
        }
    }

# Extract SKU IDs for API access
for gpu_name, gpu_info in gpus.items():
    url = gpu_info['url']
    sku_id = url.split('skuId=')[1].split('&')[0] if 'skuId=' in url else None
    gpus[gpu_name]['sku_id'] = sku_id

gpu_stock_status = {gpu: False for gpu in gpus}
gpu_stock_times = {}
gpu_check_delays = {gpu: DEFAULT_DELAY for gpu in gpus}
retry_counts = {gpu: 0 for gpu in gpus}
html_cache = {}  # Store HTML content to avoid re-parsing

async def send_discord_notification(gpu_name, url, in_stock=True, duration=None):
    current_time = datetime.now().strftime(TIMESTAMP_FORMAT)
    user_pings = ' '.join([f'<@{user_id}>' for user_id in discord_user_ids])
    
    # Fix the message construction with proper string formatting
    if in_stock:
        message = (
            f"## {gpu_name} is IN STOCK!\n"
            f"-# {current_time}\n"
            f"[product page]({url})\n"
            f"{user_pings}"
        )
    else:
        message = (
            f"## {gpu_name} is OUT OF STOCK\n"
            f"-# {current_time}\n"
            f"It was in stock for: {str(duration).split('.')[0]}"
        )
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(discord_webhook_url, json={"content": message}, timeout=REQUEST_TIMEOUT) as response:
                return response.status == 204
    except Exception as e:
        print(f"Error sending Discord notification: {str(e)}")
        return False

async def check_availability(gpu_name, gpu_info, session):
    url = gpu_info['url']
    sku_id = gpu_info.get('sku_id')
    current_time = datetime.now()
    formatted_time = current_time.strftime(TIMESTAMP_FORMAT)
    
    try:
        # Add random delay between 1 and 3 seconds to appear more human-like
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        # Use fresh headers for each request
        request_headers = get_random_headers()
        
        # Try multiple methods to check availability
        is_in_stock = False
        button_found = False
        
        # Method 1: Scrape the product page with standard approach
        async with session.get(url, headers=request_headers, timeout=REQUEST_TIMEOUT) as response:
            if response.status == 200:
                html_content = await response.text()
                
                # Update session cookies
                new_cookies = extract_cookies_from_response(response)
                update_session_cookies(session, new_cookies)
                
                # Store cookies for future sessions
                all_cookies = {}
                for cookie in session.cookie_jar:
                    all_cookies[cookie.key] = cookie.value
                save_cookies(all_cookies)
                
                # Parse HTML with error handling
                try:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    html_cache[url] = {'soup': soup, 'timestamp': time()}
                    
                    # Try multiple button selectors
                    selectors = [
                        'button.add-to-cart-button',
                        'button[data-button-state="ADD_TO_CART"]',
                        '.add-to-cart-button',
                        f'[data-sku-id="{sku_id}"] button' if sku_id else None
                    ]
                    
                    for selector in selectors:
                        if not selector:
                            continue
                            
                        add_to_cart_btn = soup.select_one(selector)
                        if add_to_cart_btn:
                            button_found = True
                            button_text = add_to_cart_btn.text.strip().upper()
                            button_state = add_to_cart_btn.get('data-button-state', '')
                            button_class = ' '.join(add_to_cart_btn.get('class', []))
                            is_disabled = 'disabled' in button_class or add_to_cart_btn.get('disabled') == 'disabled'
                            
                            logger.info(f"Found button with selector '{selector}'. Text: '{button_text}', State: '{button_state}', Disabled: {is_disabled}")
                            
                            if button_state == 'ADD_TO_CART' or ('ADD TO CART' in button_text and not is_disabled):
                                is_in_stock = True
                                break
                    
                    # Check for CloudFlare or other protection mechanisms
                    if not button_found and (
                        soup.select_one('#challenge-running') or
                        soup.select_one('.cf-browser-verification') or
                        'CF-' in str(response.headers) or
                        'captcha' in html_content.lower()
                    ):
                        logger.warning(f"Detected protection mechanism for {gpu_name}. Consider using a proxy or reducing request frequency.")
                    
                    # If no button found, try looking for text patterns
                    if not button_found:
                        # Look for availability text in the page
                        for availability_selector in ['.fulfillment-add-to-cart-button', '.priceView-hero-price', '.priceView-customer-price']:
                            availability_element = soup.select_one(availability_selector)
                            if availability_element:
                                text = availability_element.text.strip().upper()
                                if 'ADD TO CART' in text and 'SOLD OUT' not in text:
                                    is_in_stock = True
                                    button_found = True
                                    break
                except Exception as parse_error:
                    logger.error(f"Error parsing HTML: {parse_error}")
            elif response.status == 429 or response.status == 403:
                logger.warning(f"Received status {response.status} - Rate limited or blocked. Backing off...")
                retry_counts[gpu_name] += 1
                gpu_check_delays[gpu_name] = min(300, DEFAULT_DELAY * (2 ** min(retry_counts[gpu_name], 5)))
                return  # Exit early to avoid further processing
            else:
                logger.error(f"HTTP error: {response.status} when accessing {url}")
        
        # Method 2: If scraping failed, try the API approach
        if not button_found and sku_id:
            api_url = f"https://www.bestbuy.com/api/tcfb/model.json?paths=%5B%5B%22shop%22%2C%22buttonstate%22%2C%22v5%22%2C%22item%22%2C%22skus%22%2C{sku_id}%2C%22conditions%22%2C%22NONE%22%2C%22destinationZipCode%22%2C%22NONE%22%2C%22storeId%22%2C%22NONE%22%2C%22context%22%2C%22NONE%22%2C%22addAll%22%2C%22false%22%5D%5D&method=get"
            
            try:
                api_headers = get_random_headers()
                api_headers['Accept'] = 'application/json'
                
                await asyncio.sleep(random.uniform(0.5, 1.5))  # Small delay between requests
                
                async with session.get(api_url, headers=api_headers, timeout=REQUEST_TIMEOUT) as api_response:
                    if api_response.status == 200:
                        api_data = await api_response.json()
                        # Parse the API response to determine stock status
                        if 'jsonGraph' in api_data and 'buttonstate' in api_data['jsonGraph']:
                            button_state_data = api_data['jsonGraph']['buttonstate']
                            for key, value in button_state_data.items():
                                if sku_id in key and 'buttonstate' in key:
                                    if value.get('value') == 'ADD_TO_CART':
                                        is_in_stock = True
                                        button_found = True
                                        logger.info(f"API check indicates {gpu_name} is in stock")
                                    break
            except Exception as api_error:
                logger.error(f"API check failed: {str(api_error)}")
        
        if not button_found:
            all_buttons = html_cache.get(url, {}).get('soup', BeautifulSoup('', 'html.parser')).find_all('button')
            logger.warning(f"Found {len(all_buttons)} buttons on the page. First few buttons:")
            for i, btn in enumerate(all_buttons[:5]):
                logger.warning(f"Button {i+1}: {btn.get('class', 'No class')} - Text: {btn.text.strip()}")
            
            raise ValueError("Add to cart button not found with any selector")
        
        # Process stock status changes
        if is_in_stock:
            if not gpu_stock_status[gpu_name]:
                gpu_stock_status[gpu_name] = True
                gpu_stock_times[gpu_name] = current_time
                gpu_check_delays[gpu_name] = INSTOCK_DELAY
                await send_discord_notification(gpu_name, url)
            status = "IN STOCK!!!"
            msg_template = IN_STOCK_MSG
        else:
            if gpu_stock_status[gpu_name]:
                duration = current_time - gpu_stock_times[gpu_name]
                gpu_stock_status[gpu_name] = False
                gpu_check_delays[gpu_name] = DEFAULT_DELAY
                await send_discord_notification(gpu_name, url, False, duration)
            status = "OUT OF STOCK..."
            msg_template = OUT_STOCK_MSG
        
        print(f"[{TIME_PREFIX}] {msg_template}".format(
            timestamp=formatted_time,
            gpu=gpu_name,
            status=status
        ))
        
        # Reset retry count on success
        retry_counts[gpu_name] = 0
        
    except Exception as e:
        # Improved error handling
        retry_counts[gpu_name] += 1
        backoff_delay = min(120, DEFAULT_DELAY * (2 ** min(retry_counts[gpu_name], 4)))
        gpu_check_delays[gpu_name] = backoff_delay
        logger.error(f"Error checking {gpu_name}: {str(e)}. Retrying in {backoff_delay}s")
        
        # If we've failed multiple times, try to save the HTML for debugging
        if retry_counts[gpu_name] >= MAX_RETRIES:
            try:
                debug_file = f"debug_{gpu_name.replace(' ', '_')}_{int(time())}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    if url in html_cache:
                        f.write(str(html_cache[url]['soup']))
                logger.info(f"Saved debug HTML to {debug_file}")
            except Exception as save_error:
                logger.error(f"Could not save debug HTML: {save_error}")

async def main_async():
    logger.info("Starting Best Buy GPU availability checker...\nPress Ctrl+C to exit\n")
    
    # Log the GPUs we're tracking
    logger.info(f"Tracking {len(gpus)} GPUs:")
    for name, info in gpus.items():
        logger.info(f"  - {name}: {info['url']}")
    
    last_check = {gpu: 0 for gpu in gpus}
    
    # Load saved cookies
    cookies_dict = load_cookies()
    
    # Create a cookie jar from the saved cookies
    jar = aiohttp.CookieJar()
    
    # Create a base URL object
    base_url = URL('https://www.bestbuy.com')
    
    # Add cookies to the jar with proper URL object
    for name, value in cookies_dict.items():
        jar.update_cookies({name: value}, base_url)
    
    # Create a session with cookies and trace_configs
    session_kwargs = {
        'cookie_jar': jar,
        'timeout': aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    }
    
    async with aiohttp.ClientSession(**session_kwargs) as session:
        try:
            # First make a warmup request to the main site to get cookies
            try:
                await asyncio.sleep(random.uniform(1.0, 3.0))
                async with session.get('https://www.bestbuy.com', headers=get_random_headers(), timeout=REQUEST_TIMEOUT) as response:
                    if response.status == 200:
                        new_cookies = extract_cookies_from_response(response)
                        update_session_cookies(session, new_cookies)
                        all_cookies = {}
                        for cookie in session.cookie_jar:
                            all_cookies[cookie.key] = cookie.value
                        save_cookies(all_cookies)
                        logger.info("Initialized session with cookies from bestbuy.com")
            except Exception as e:
                logger.warning(f"Warmup request failed: {e}")
                
            while True:
                current_time = time()
                
                # Find next GPU to check
                next_check_time = float('inf')
                for gpu_name in gpus:
                    check_time = last_check[gpu_name] + gpu_check_delays[gpu_name]
                    if check_time < next_check_time:
                        next_check_time = check_time
                
                # Sleep until next check is due
                sleep_time = max(0, next_check_time - current_time)
                if (sleep_time > 0):
                    await asyncio.sleep(sleep_time)
                
                # Check which GPUs need processing
                current_time = time()
                tasks = []
                
                for gpu_name, gpu_info in gpus.items():
                    if current_time >= last_check[gpu_name] + gpu_check_delays[gpu_name]:
                        tasks.append(check_availability(gpu_name, gpu_info, session))
                        last_check[gpu_name] = current_time
                
                # Run all checks with some concurrency control
                if tasks:
                    # Run checks with some concurrency control (3 at a time)
                    for i in range(0, len(tasks), 3):
                        batch = tasks[i:i+3]
                        await asyncio.gather(*batch)
                        if i + 3 < len(tasks):
                            # Add small delay between batches
                            await asyncio.sleep(random.uniform(2.0, 5.0))
                    
        except KeyboardInterrupt:
            logger.info("\n\nExiting checker...")
            exit(0)

def main():
    """Legacy synchronous main function for compatibility"""
    import platform
    if platform.system() == 'Windows':
        # Fix for Windows asyncio policy
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    # Run the async main function
    asyncio.run(main_async())

if __name__ == "__main__":
    main()