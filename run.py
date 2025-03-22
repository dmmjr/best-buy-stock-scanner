import os
from dotenv import load_dotenv
import asyncio
import aiohttp
from yarl import URL
import random
import json
from datetime import datetime
from time import time
from sys import exit
from bs4 import BeautifulSoup
from colorama import Fore, Style, init
import logging
import http.cookies

# Import settings
from settings import *

# Load environment variables from .env file
load_dotenv()

# Initialize colorama once
init()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("stock_scanner")

# Configuration  
discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
discord_user_ids = os.getenv('DISCORD_USER_IDS', '').split(',')

# Load user agents from the JSON file
def load_user_agents():
    try:
        if os.path.exists(USER_AGENTS_FILE):
            with open(USER_AGENTS_FILE, 'r') as f:
                agents = json.load(f)
                logger.info(f"Loaded {len(agents)} user agents from {USER_AGENTS_FILE}")
                return agents
        else:
            logger.warning(f"User agents file {USER_AGENTS_FILE} not found. This is required for the application to work.")
            exit(1)
    except Exception as e:
        logger.error(f"Error loading user agents: {e}")
        exit(1)

# Load header templates from the JSON file
def load_headers():
    try:
        if os.path.exists(HEADERS_FILE):
            with open(HEADERS_FILE, 'r') as f:
                headers = json.load(f)
                logger.info(f"Loaded header templates from {HEADERS_FILE}")
                return headers
        else:
            logger.error(f"Headers file {HEADERS_FILE} not found. This is required for the application to work.")
            exit(1)
    except Exception as e:
        logger.error(f"Error loading headers: {e}")
        exit(1)

# Load user agents and headers
USER_AGENTS = load_user_agents()
HEADERS = load_headers()

def get_random_headers(header_type="common"):
    """Generate headers with a random user agent"""
    user_agent = random.choice(USER_AGENTS)
    
    # Get the base headers template
    if header_type in HEADERS:
        headers = HEADERS[header_type].copy()
    else:
        headers = HEADERS["common"].copy()
    
    # Add the user agent
    headers["User-Agent"] = user_agent
    
    return headers

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

# Product tracking from environment variables
products = {}

# Parse product environment variables
for i in range(1, 10):  # Support up to 9 products
    product_name = os.getenv(f'PRODUCT_{i}_NAME')
    product_url = os.getenv(f'PRODUCT_{i}_URL')
    
    if product_name and product_url:
        products[product_name] = {
            'url': product_url,
        }

# If no products defined in env vars, use defaults
if not products:
    logger.warning("No products defined in environment variables. At least one product is required.")
    exit(1)

# Extract SKU IDs for tracking
for product_name, product_info in products.items():
    url = product_info['url']
    sku_id = url.split('skuId=')[1].split('&')[0] if 'skuId=' in url else None
    products[product_name]['sku_id'] = sku_id

product_stock_status = {product: False for product in products}
product_stock_times = {}
product_check_delays = {product: DEFAULT_DELAY for product in products}
retry_counts = {product: 0 for product in products}
html_cache = {}  # Store HTML content to avoid re-parsing

async def send_discord_notification(product_name, url, in_stock=True, duration=None):
    current_time = datetime.now().strftime(TIMESTAMP_FORMAT)
    user_pings = ' '.join([f'<@{user_id}>' for user_id in discord_user_ids])
    
    # Fix the message construction with proper string formatting
    if in_stock:
        message = (
            f"## {product_name} is IN STOCK!\n"
            f"-# {current_time}\n"
            f"[product page]({url})\n"
            f"{user_pings}"
        )
    else:
        message = (
            f"## {product_name} is OUT OF STOCK\n"
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

async def check_availability(product_name, product_info, session):
    url = product_info['url']
    sku_id = product_info.get('sku_id')
    current_time = datetime.now()
    formatted_time = current_time.strftime(TIMESTAMP_FORMAT)
    
    try:
        # Add random delay between 1 and 3 seconds to appear more human-like
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        # Use fresh headers for each request
        request_headers = get_random_headers()
        
        # Try to check availability
        is_in_stock = False
        button_found = False
        
        # Scrape the product page with standard approach
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
                    
                    # Create button selectors including the SKU-specific one
                    selectors = BUTTON_SELECTORS.copy()
                    if sku_id:
                        selectors.append(f'[data-sku-id="{sku_id}"] button')
                    
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
                    if not button_found:
                        for indicator in PROTECTION_INDICATORS:
                            if soup.select_one(indicator) or 'CF-' in str(response.headers) or 'captcha' in html_content.lower():
                                logger.warning(f"Detected protection mechanism for {product_name}. Consider using a proxy or reducing request frequency.")
                                break
                    
                    # If no button found, try looking for text patterns
                    if not button_found:
                        # Look for availability text in the page
                        for availability_selector in TEXT_SELECTORS:
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
                retry_counts[product_name] += 1
                product_check_delays[product_name] = min(300, DEFAULT_DELAY * (2 ** min(retry_counts[product_name], 5)))
                return  # Exit early to avoid further processing
            else:
                logger.error(f"HTTP error: {response.status} when accessing {url}")
        
        if not button_found:
            raise ValueError("Add to cart button not found with any selector")
        
        # Process stock status changes
        if is_in_stock:
            if not product_stock_status[product_name]:
                product_stock_status[product_name] = True
                product_stock_times[product_name] = current_time
                product_check_delays[product_name] = INSTOCK_DELAY
                await send_discord_notification(product_name, url)
            status = "IN STOCK!!!"
            msg_template = IN_STOCK_MSG
        else:
            if product_stock_status[product_name]:
                duration = current_time - product_stock_times[product_name]
                product_stock_status[product_name] = False
                product_check_delays[product_name] = DEFAULT_DELAY
                await send_discord_notification(product_name, url, False, duration)
            status = "OUT OF STOCK..."
            msg_template = OUT_STOCK_MSG
        
        print(f"[{TIME_PREFIX}] {msg_template}".format(
            timestamp=formatted_time,
            product=product_name,
            status=status
        ))
        
        # Reset retry count on success
        retry_counts[product_name] = 0
        
    except Exception as e:
        # Improved error handling
        retry_counts[product_name] += 1
        backoff_delay = min(120, DEFAULT_DELAY * (2 ** min(retry_counts[product_name], 4)))
        product_check_delays[product_name] = backoff_delay
        logger.error(f"Error checking {product_name}: {str(e)}. Retrying in {backoff_delay}s")
        
        # If we've failed multiple times, try to save the HTML for debugging
        if retry_counts[product_name] >= MAX_RETRIES:
            try:
                debug_file = f"debug_{product_name.replace(' ', '_')}_{int(time())}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    if url in html_cache:
                        f.write(str(html_cache[url]['soup']))
                logger.info(f"Saved debug HTML to {debug_file}")
            except Exception as save_error:
                logger.error(f"Could not save debug HTML: {save_error}")

async def main_async():
    logger.info("Starting Best Buy product availability checker...\nPress Ctrl+C to exit\n")
    
    # Log the products we're tracking
    logger.info(f"Tracking {len(products)} products:")
    for name, info in products.items():
        logger.info(f"  - {name}: {info['url']}")
    
    last_check = {product: 0 for product in products}
    
    # Load saved cookies
    cookies_dict = load_cookies()
    
    # Create a cookie jar from the saved cookies
    jar = aiohttp.CookieJar()
    
    # Create a base URL object
    base_url = URL(BASE_URL)
    
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
                async with session.get(BASE_URL, headers=get_random_headers(), timeout=REQUEST_TIMEOUT) as response:
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
                
                # Find next product to check
                next_check_time = float('inf')
                for product_name in products:
                    check_time = last_check[product_name] + product_check_delays[product_name]
                    if check_time < next_check_time:
                        next_check_time = check_time
                
                # Sleep until next check is due
                sleep_time = max(0, next_check_time - current_time)
                if (sleep_time > 0):
                    await asyncio.sleep(sleep_time)
                
                # Check which products need processing
                current_time = time()
                tasks = []
                
                for product_name, product_info in products.items():
                    if current_time >= last_check[product_name] + product_check_delays[product_name]:
                        tasks.append(check_availability(product_name, product_info, session))
                        last_check[product_name] = current_time
                
                # Run all checks with some concurrency control
                if tasks:
                    # Run checks with some concurrency control
                    for i in range(0, len(tasks), BATCH_SIZE):
                        batch = tasks[i:i+BATCH_SIZE]
                        await asyncio.gather(*batch)
                        if i + BATCH_SIZE < len(tasks):
                            # Add small delay between batches
                            await asyncio.sleep(random.uniform(BATCH_DELAY_MIN, BATCH_DELAY_MAX))
                    
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