"""
User Agent Generator

Dynamically generates realistic user agent strings based on common browser patterns
and version combinations. This allows for a practically unlimited number of unique
user agents while maintaining realistic patterns.
"""
import random
from datetime import datetime, timedelta

# Browser base patterns
CHROME_PATTERN = "Mozilla/5.0 ({os}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36{chrome_extra}"
FIREFOX_PATTERN = "Mozilla/5.0 ({os}; rv:{firefox_version}) Gecko/20100101 Firefox/{firefox_version}"
SAFARI_PATTERN = "Mozilla/5.0 ({mac_os}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Version/{safari_version} Safari/{webkit_version}"
EDGE_PATTERN = "Mozilla/5.0 ({os}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36 Edg/{edge_version}"
OPERA_PATTERN = "Mozilla/5.0 ({os}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36 OPR/{opera_version}"
BRAVE_PATTERN = "Mozilla/5.0 ({os}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36 Brave/{brave_version}"

# Platform variations
WINDOWS_OS = [
    "Windows NT 10.0; Win64; x64",
    "Windows NT 10.0; WOW64",
    "Windows NT 10.0",
    "Windows NT 11.0; Win64; x64"
]

LINUX_OS = [
    "X11; Linux x86_64",
    "X11; Ubuntu; Linux x86_64",
    "X11; Fedora; Linux x86_64",
    "X11; Linux x86_64; rv:{firefox_version}"
]

MAC_OS = [
    "Macintosh; Intel Mac OS X 10_{mac_minor}_{mac_patch}",
    "Macintosh; Intel Mac OS X 14_{mac_minor}_{mac_patch}"
]

MOBILE_OS = [
    "iPhone; CPU iPhone OS {ios_version} like Mac OS X",
    "iPad; CPU OS {ios_version} like Mac OS X",
    "Linux; Android {android_version}"
]

# Version generators
def _get_chrome_version():
    # Chrome versions typically from 115-125 currently
    major = random.randint(115, 125)
    minor = random.randint(0, 0)
    build = random.randint(0, 9999)
    patch = random.randint(0, 999)
    
    # Different version formats
    formats = [
        f"{major}.0.{build}.{patch}",
        f"{major}.0.{build}",
        f"{major}.{minor}.{build}.{patch}",
        f"{major}.0.0.0"
    ]
    return random.choice(formats)

def _get_firefox_version():
    # Firefox versions typically from 110-125 currently
    major = random.randint(110, 125)
    minor = random.randint(0, 0)
    
    # Different version formats
    formats = [
        f"{major}.0",
        f"{major}.{minor}",
        "102.0" # ESR version
    ]
    return random.choice(formats)

def _get_webkit_version():
    # Recent WebKit versions
    major = 605
    minor = random.randint(1, 1)
    patch = random.randint(10, 15)
    return f"{major}.{minor}.{patch}"

def _get_safari_version():
    # Safari versions
    major = random.randint(15, 17)
    minor = random.randint(0, 4)
    patch = random.choice(["", ".1", ".2", ".3"])
    return f"{major}.{minor}{patch}"

def _get_edge_version():
    # Edge versions typically close to Chrome
    chrome_major = random.randint(115, 125)
    edge_major = chrome_major  # Edge version number matches Chrome
    edge_minor = random.randint(0, 0)
    edge_build = random.randint(0, 999)
    
    formats = [
        f"{edge_major}.0.{edge_build}.0",
        f"{edge_major}.{edge_minor}.{edge_build}.0",
        f"{edge_major}.0.0.0"
    ]
    return random.choice(formats)

def _get_opera_version():
    # Opera versions 
    major = random.randint(100, 108)
    minor = random.randint(0, 0)
    patch = random.randint(0, 0)
    return f"{major}.{minor}.{patch}.{random.randint(0, 999)}"

def _get_mac_versions():
    mac_minor = random.randint(13, 15)
    mac_patch = random.randint(0, 7)
    return mac_minor, mac_patch

def _get_ios_version():
    major = random.randint(15, 17)
    minor = random.randint(0, 4)
    patch = random.randint(0, 1)
    return f"{major}_{minor}_{patch}"

def _get_android_version():
    major = random.randint(10, 14)
    minor = random.randint(0, 0)
    patch = random.randint(0, 0)
    return f"{major}.{minor}.{patch}"

def generate_chrome_ua(use_mobile=False):
    chrome_version = _get_chrome_version()
    os_string = random.choice(MOBILE_OS) if use_mobile else random.choice(WINDOWS_OS + MAC_OS + LINUX_OS)

    # Format the OS string
    if "Mac OS X" in os_string:
        mac_minor, mac_patch = _get_mac_versions()
        os_string = os_string.format(mac_minor=mac_minor, mac_patch=mac_patch)
    elif "iPhone" in os_string or "iPad" in os_string:
        os_string = os_string.format(ios_version=_get_ios_version())
    elif "Android" in os_string:
        os_string = os_string.format(android_version=_get_android_version())
    
    # Extras for Chrome
    extras = [""]
    if random.random() < 0.2:  # 20% chance to add mobile
        extras.append(" Mobile")
    
    chrome_extra = random.choice(extras)
    
    return CHROME_PATTERN.format(
        os=os_string,
        chrome_version=chrome_version,
        chrome_extra=chrome_extra
    )

def generate_firefox_ua(use_mobile=False):
    firefox_version = _get_firefox_version()
    os_string = random.choice(MOBILE_OS) if use_mobile else random.choice(WINDOWS_OS + MAC_OS + LINUX_OS)
    
    # Format the OS string
    if "Mac OS X" in os_string:
        mac_minor, mac_patch = _get_mac_versions()
        os_string = os_string.format(mac_minor=mac_minor, mac_patch=mac_patch)
    elif "iPhone" in os_string or "iPad" in os_string:
        os_string = os_string.format(ios_version=_get_ios_version())
    elif "Android" in os_string:
        os_string = os_string.format(android_version=_get_android_version())
    elif "rv:" in os_string:
        os_string = os_string.format(firefox_version=firefox_version)
    
    return FIREFOX_PATTERN.format(
        os=os_string,
        firefox_version=firefox_version
    )

def generate_safari_ua(use_mobile=False):
    webkit_version = _get_webkit_version()
    safari_version = _get_safari_version()
    
    if use_mobile:
        ios_version = _get_ios_version()
        os_string = random.choice([
            f"iPhone; CPU iPhone OS {ios_version} like Mac OS X",
            f"iPad; CPU OS {ios_version} like Mac OS X"
        ])
    else:
        mac_minor, mac_patch = _get_mac_versions()
        os_string = f"Macintosh; Intel Mac OS X 10_{mac_minor}_{mac_patch}"
    
    return SAFARI_PATTERN.format(
        mac_os=os_string,
        webkit_version=webkit_version,
        safari_version=safari_version
    )

def generate_edge_ua():
    chrome_version = _get_chrome_version()
    edge_version = _get_edge_version()
    os_string = random.choice(WINDOWS_OS + MAC_OS)
    
    # Format the OS string
    if "Mac OS X" in os_string:
        mac_minor, mac_patch = _get_mac_versions()
        os_string = os_string.format(mac_minor=mac_minor, mac_patch=mac_patch)
    
    return EDGE_PATTERN.format(
        os=os_string,
        chrome_version=chrome_version,
        edge_version=edge_version
    )

def generate_opera_ua():
    chrome_version = _get_chrome_version()
    opera_version = _get_opera_version()
    os_string = random.choice(WINDOWS_OS + MAC_OS + LINUX_OS)
    
    # Format the OS string
    if "Mac OS X" in os_string:
        mac_minor, mac_patch = _get_mac_versions()
        os_string = os_string.format(mac_minor=mac_minor, mac_patch=mac_patch)
    
    return OPERA_PATTERN.format(
        os=os_string,
        chrome_version=chrome_version,
        opera_version=opera_version
    )

def generate_brave_ua():
    chrome_version = _get_chrome_version()
    brave_version = chrome_version  # Brave version usually matches Chrome
    os_string = random.choice(WINDOWS_OS + MAC_OS + LINUX_OS)
    
    # Format the OS string
    if "Mac OS X" in os_string:
        mac_minor, mac_patch = _get_mac_versions()
        os_string = os_string.format(mac_minor=mac_minor, mac_patch=mac_patch)
    
    return BRAVE_PATTERN.format(
        os=os_string,
        chrome_version=chrome_version,
        brave_version=brave_version
    )

__all__ = ['get_random_user_agent', 'generate_user_agents']

def get_random_user_agent(include_mobile=False):
    """
    Generate a random user agent string.
    
    Args:
        include_mobile (bool): Whether to include mobile user agents
        
    Returns:
        str: A randomly generated user agent string
    """
    ua_generators = [
        # Desktop browsers have higher weights
        (generate_chrome_ua, 0.50, False),   # 50% chance of Chrome
        (generate_firefox_ua, 0.25, False),  # 25% chance of Firefox
        (generate_edge_ua, 0.10, False),     # 10% chance of Edge
        (generate_safari_ua, 0.05, False),   # 5% chance of Safari
        (generate_opera_ua, 0.05, False),    # 5% chance of Opera
        (generate_brave_ua, 0.05, False),    # 5% chance of Brave
    ]
    
    if include_mobile:
        # Add mobile browsers
        ua_generators.extend([
            (generate_chrome_ua, 0.30, True),   # Mobile Chrome
            (generate_safari_ua, 0.20, True),   # Mobile Safari
            (generate_firefox_ua, 0.10, True),  # Mobile Firefox
        ])
    
    # Choose a generator based on weight
    weights = [item[1] for item in ua_generators]
    total = sum(weights)
    normalized_weights = [w/total for w in weights]
    
    generator, _, use_mobile = random.choices(ua_generators, weights=normalized_weights, k=1)[0]
    
    if use_mobile:
        return generator(use_mobile=True)
    return generator()

def generate_user_agents(count=10, include_mobile=True):
    """
    Generate a list of random user agent strings.
    
    Args:
        count (int): Number of user agents to generate
        include_mobile (bool): Whether to include mobile user agents
        
    Returns:
        list: A list of randomly generated user agent strings
    """
    return [get_random_user_agent(include_mobile) for _ in range(count)]

# Example usage
if __name__ == "__main__":
    # Generate 5 random user agents
    for ua in generate_user_agents(5):
        print(ua)
