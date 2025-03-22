A web scraper that scans specific product pages at Bestbuy.com, and notifies you via Discord when they are in stock.

# Create and activate virtual environment
```
python -m venv venv
venv\Scripts\activate
```

# Install requirements
```
pip install requirements.txt
```

# Set environment variables
```
# Discord Configuration
DISCORD_WEBHOOK_URL=12345678
DISCORD_USER_IDS=123,987 (supports multiple separated by comma)

# Product Configuration
PRODUCT_1_NAME=Product name
PRODUCT_1_URL=https://www.bestbuy.com/site/...

PRODUCT_2_NAME=Product name
PRODUCT_2_URL=https://www.bestbuy.com/site/...

...add as many as you'd like
```
[Discord webhooks](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)  
[How to find your Discord User ID](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID#h_01HRSTXPS5H5D7JBY2QKKPVKNA)

# Run script
```
python run.py
```
