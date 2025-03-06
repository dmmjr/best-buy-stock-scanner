import asyncio
import aiohttp
from datetime import datetime
from time import time
from sys import exit
from bs4 import BeautifulSoup
from colorama import Fore, Style, init

# Initialize colorama once
init()

# Constants
REQUEST_TIMEOUT = 5
DEFAULT_DELAY = 30
INSTOCK_DELAY = 5
MAX_RETRIES = 3
CACHE_TTL = 60  # Seconds to keep HTML cache valid

# Pre-formatted strings
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
TIME_PREFIX = f"{Fore.LIGHTBLACK_EX}{{timestamp}}{Style.RESET_ALL}"
IN_STOCK_MSG = f"{Fore.GREEN}{{gpu}} at {{vendor}} is {{status}}{Style.RESET_ALL}"
OUT_STOCK_MSG = f"{Fore.RED}{{gpu}} at {{vendor}} is {{status}}{Style.RESET_ALL}"

# Configuration  
discord_webhook_url = 'https://discord.com/api/webhooks/1334604131536736276/__rNWIMxU9RzhvSvonZricsITIZhOveGcCt_L12fO-d52INcsOQbJrWRr0VO_DaJGymw'
discord_user_ids = [
    '142106380764053504',  # Slippy D
    '134718395798126592'   # Frantik
]
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

VENDOR_BESTBUY = 'Best Buy'

# GPU tracking
gpus = {
    'RTX 5090 FE': {
        'url': 'https://www.bestbuy.com/site/nvidia-geforce-rtx-5090-32gb-gddr7-graphics-card-dark-gun-metal/6614151.p?skuId=6614151',
        'vendor': VENDOR_BESTBUY
    },
    'RTX 5080 FE': {
        'url': 'https://www.bestbuy.com/site/nvidia-geforce-rtx-5080-16gb-gddr7-graphics-card-gun-metal/6614153.p?skuId=6614153',
        'vendor': VENDOR_BESTBUY
   },
   'RX 9070XT XFX': {
        'url': 'https://www.bestbuy.com/site/xfx-swift-amd-radeon-rx-9070xt-16gb-gddr6-pci-express-5-0-gaming-graphics-card-black/6620455.p?skuId=6620455',
        'vendor': VENDOR_BESTBUY
   },
}
gpu_stock_status = {gpu: False for gpu in gpus}
gpu_stock_times = {}
gpu_check_delays = {gpu: DEFAULT_DELAY for gpu in gpus}
retry_counts = {gpu: 0 for gpu in gpus}
html_cache = {}  # Store HTML content to avoid re-parsing

async def send_discord_notification(gpu_name, vendor, url, in_stock=True, duration=None):
    current_time = datetime.now().strftime(TIMESTAMP_FORMAT)
    user_pings = ' '.join([f'<@{user_id}>' for user_id in discord_user_ids])
    
    # Fix the message construction with proper string formatting
    if in_stock:
        message = (
            f"## {gpu_name} at {vendor} is IN STOCK!\n"
            f"-# {current_time}\n"
            f"[product page]({url})\n"
            f"{user_pings}"
        )
    else:
        message = (
            f"## {gpu_name} at {vendor} is OUT OF STOCK\n"
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
    url, vendor = gpu_info['url'], gpu_info['vendor']
    current_time = datetime.now()
    formatted_time = current_time.strftime(TIMESTAMP_FORMAT)
    
    try:
        # Check if we have a cached version
        if url in html_cache and time() - html_cache[url]['timestamp'] < CACHE_TTL:
            soup = html_cache[url]['soup']
        else:
            async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                html_cache[url] = {'soup': soup, 'timestamp': time()}
        
        add_to_cart_btn = soup.find('button', class_='add-to-cart-button')
        
        if not add_to_cart_btn:
            raise ValueError("Button not found")
            
        button_state = add_to_cart_btn.get('data-button-state', '')
        is_disabled = 'c-button-disabled' in add_to_cart_btn.get('class', [])
        is_in_stock = button_state == 'ADD_TO_CART' and not is_disabled
        
        if is_in_stock:
            if not gpu_stock_status[gpu_name]:
                gpu_stock_status[gpu_name] = True
                gpu_stock_times[gpu_name] = current_time
                gpu_check_delays[gpu_name] = INSTOCK_DELAY
                await send_discord_notification(gpu_name, vendor, url)
            status = "IN STOCK!!!"
            msg_template = IN_STOCK_MSG
        else:
            if gpu_stock_status[gpu_name]:
                duration = current_time - gpu_stock_times[gpu_name]
                gpu_stock_status[gpu_name] = False
                gpu_check_delays[gpu_name] = DEFAULT_DELAY
                await send_discord_notification(gpu_name, vendor, url, False, duration)
            status = "OUT OF STOCK..."
            msg_template = OUT_STOCK_MSG
        
        print(f"[{TIME_PREFIX}] {msg_template}".format(
            timestamp=formatted_time,
            gpu=gpu_name,
            vendor=vendor,
            status=status
        ))
        
        # Reset retry count on success
        retry_counts[gpu_name] = 0
        
    except Exception as e:
        # Implement exponential backoff on error
        retry_counts[gpu_name] += 1
        backoff_delay = min(300, DEFAULT_DELAY * (2 ** retry_counts[gpu_name]))
        gpu_check_delays[gpu_name] = backoff_delay
        print(f"Error checking {gpu_name}: {str(e)}. Retrying in {backoff_delay}s")

async def main_async():
    print("Starting NVIDIA GPU availability checker...\nPress Ctrl+C to exit\n")
    last_check = {gpu: 0 for gpu in gpus}
    
    # Create a shared session for all requests
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
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
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
                # Check which GPUs need processing
                current_time = time()
                tasks = []
                
                for gpu_name, gpu_info in gpus.items():
                    if current_time >= last_check[gpu_name] + gpu_check_delays[gpu_name]:
                        tasks.append(check_availability(gpu_name, gpu_info, session))
                        last_check[gpu_name] = current_time
                
                # Run all checks in parallel
                if tasks:
                    await asyncio.gather(*tasks)
                    
        except KeyboardInterrupt:
            print("\n\nExiting checker...")
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