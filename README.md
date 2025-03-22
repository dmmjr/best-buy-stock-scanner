A script to scan specific product pages and notify you when they come back in stock.

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

# GPU Configuration
GPU_1_NAME=Product name
GPU_1_URL=https://www.bestbuy.com/site/...

GPU_2_NAME=Product name
GPU_2_URL=https://www.bestbuy.com/site/...

...add as many as you'd like
```
[Discord webhooks](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)  
[How to find your Discord User ID](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID#h_01HRSTXPS5H5D7JBY2QKKPVKNA)

# Run script
```
python run.py
```
