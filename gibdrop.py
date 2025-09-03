import sys
import os
import subprocess
import re
import shutil
import urllib.request
import pickle
from datetime import datetime, timezone
import gibdrop_dockermgr

# Try to import optional dependencies - will be installed if missing
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    # These will be handled by the bootstrap code below
    requests = None
    BeautifulSoup = None

def reset_terminal_colors():
    """Reset terminal colors to default after Docker operations that may leave ANSI color codes active."""
    print("\033[0m", end="")  # ANSI reset code

# --- Bootstrap: install dependencies if missing ---
REQUIRED_PACKAGES = ["requests", "beautifulsoup4"]
VENV_DIR = ".gibdrop_venv"

def in_venv():
    return (
        hasattr(sys, "real_prefix") or
        (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )

def ensure_venv_available():
    try:
        import venv
        return True
    except ImportError:
        print("Python 'venv' module is not installed. Attempting to install it...")
        # Try to detect the OS and install venv
        if shutil.which('apt-get'):
            cmd = ['sudo', 'apt-get', 'update']
            try:
                subprocess.check_call(cmd)
            except Exception:
                pass
            cmd = ['sudo', 'apt-get', 'install', '-y', 'python3-venv']
        elif shutil.which('apk'):
            cmd = ['sudo', 'apk', 'add', 'py3-virtualenv']
        elif shutil.which('yum'):
            cmd = ['sudo', 'yum', 'install', '-y', 'python3-venv']
        else:
            print("Could not detect package manager. Please install python3-venv manually.")
            return False
        try:
            subprocess.check_call(cmd)
            import venv
            print("'venv' module installed successfully.")
            return True
        except Exception as e:
            print(f"Failed to install 'venv': {e}\nPlease install python3-venv manually using your system's package manager.")
            return False

try:
    # Check if we successfully imported the required packages
    if requests is None or BeautifulSoup is None:
        raise ImportError("Dependencies not available")
    # Test the imports
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Attempting system install...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + REQUIRED_PACKAGES)
        print("Dependencies installed. Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print(f"System install failed: {e}\nTrying with a virtual environment...")
        if not in_venv():
            # Create venv if it doesn't exist
            if not os.path.isdir(VENV_DIR):
                if not ensure_venv_available():
                    print("Cannot continue without Python venv support. Exiting.")
                    sys.exit(1)
                print("Creating virtual environment for gibdrop...")
                subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
            # Install dependencies in the venv
            pip_path = os.path.join(VENV_DIR, "bin", "pip")
            python_path = os.path.join(VENV_DIR, "bin", "python")
            if os.name == "nt":
                pip_path = os.path.join(VENV_DIR, "Scripts", "pip.exe")
                python_path = os.path.join(VENV_DIR, "Scripts", "python.exe")
            subprocess.check_call([pip_path, "install"] + REQUIRED_PACKAGES)
            print("Restarting script inside virtual environment...")
            os.execv(python_path, [python_path] + sys.argv)
        else:
            print("Failed to install dependencies, even in a virtual environment. Exiting.")
            sys.exit(1)

# StreamerManager: Handles loading, saving, and fetching streamer lists (default, drop, active) for the Twitch miner.
class StreamerManager:
    def get_rust_drops(self):
        url = "https://twitch.facepunch.com/#drops"
        response = requests.get(url)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract campaign dates from the event-date section
        campaign_start = None
        campaign_end = None
        is_active = False
        
        event_date_div = soup.find('div', class_='event-date')
        if event_date_div:
            # Look for JavaScript timestamp patterns: new Date(1234567890000)
            timestamp_pattern = r'new Date\((\d+)\)'
            timestamps = re.findall(timestamp_pattern, str(event_date_div))
            
            if len(timestamps) >= 2:
                # Convert JavaScript timestamps (milliseconds) to Python timestamps (seconds)
                start_timestamp = int(timestamps[0]) / 1000
                end_timestamp = int(timestamps[1]) / 1000
                
                campaign_start = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
                campaign_end = datetime.fromtimestamp(end_timestamp, tz=timezone.utc)
                
                # Check if campaign is currently active
                now = datetime.now(timezone.utc)
                is_active = campaign_start <= now <= campaign_end
                
                print(f"    📅 Rust drops campaign: {campaign_start.strftime('%Y-%m-%d %H:%M UTC')} - {campaign_end.strftime('%Y-%m-%d %H:%M UTC')}")
                if is_active:
                    print(f"    ✅ Campaign is currently ACTIVE")
                elif now < campaign_start:
                    print(f"    ⏳ Campaign starts in {campaign_start - now}")
                else:
                    print(f"    ❌ Campaign ended {now - campaign_end} ago")
        
        # Only fetch streamers if campaign is active or no date info found (fallback)
        if is_active or campaign_start is None:
            streamer_drops_div = soup.find('div', class_='streamer-drops')
            if not streamer_drops_div:
                print("    ⚠️  Streamer drops section not found!")
                return [], 0, campaign_start, campaign_end, is_active
            
            streamer_names_spans = streamer_drops_div.find_all('span', class_='streamer-name')
            rust_streamer_names = [span.get_text(strip=True) for span in streamer_names_spans]
            
            # Get general drops count
            general_drops_count = 0
            drops_div = soup.find('div', id='drops', class_='section drops')
            if drops_div:
                h1_title = drops_div.find('h1', class_='title')
                if h1_title:
                    span = h1_title.find('span')
                    if span:
                        text = span.get_text(strip=True)
                        try:
                            general_drops_count = int(text.strip('()'))
                        except ValueError:
                            general_drops_count = 0
            
            return rust_streamer_names, general_drops_count, campaign_start, campaign_end, is_active
        else:
            print(f"    ⚠️  Campaign not active, skipping streamer fetch")
            return [], 0, campaign_start, campaign_end, is_active

    def get_all_drop_streamers(self):
        """
        Fetches streamers from all active Twitch drop campaigns using multiple methods.
        This is a more comprehensive approach than just fetching Rust drops.
        """
        try:
            print("Fetching active Twitch drop campaigns...")
            
            # Method 1: Try to get campaigns from Twitch's public drops page
            all_streamers = set()
            campaign_info = {}
            
            # First try scraping the public drops page
            try:
                drops_url = "https://www.twitch.tv/drops/campaigns"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(drops_url, headers=headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # Look for campaign data in script tags or data attributes
                    # This is a fallback method as the page structure may change
                    print("Attempting to parse drops page...")
                    
            except Exception as e:
                print(f"Drops page scraping failed: {e}")
            
            # Method 2: Try GraphQL with a different approach (public directory)
            try:
                print("Trying alternative GraphQL approach...")
                
                # Get popular games first
                popular_games = ["Rust", "Counter-Strike 2", "VALORANT", "World of Warcraft", 
                               "League of Legends", "Apex Legends", "Fortnite", "Escape from Tarkov"]
                
                url = "https://gql.twitch.tv/gql"
                headers = {
                    'Client-Id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                for game in popular_games:
                    try:
                        # First get the game slug
                        slug_query = {
                            "operationName": "DirectoryGameRedirect",
                            "variables": {"name": game},
                            "extensions": {
                                "persistedQuery": {
                                    "version": 1,
                                    "sha256Hash": "1f0300090caceec51f33c5e20647aceff9017f740f223c3c532ba6fa59f6b6cc"
                                }
                            }
                        }
                        
                        response = requests.post(url, json=slug_query, headers=headers)
                        if response.status_code == 200:
                            data = response.json()
                            game_data = data.get('data', {}).get('game')
                            if game_data and game_data.get('slug'):
                                slug = game_data['slug']
                                
                                # Now get channels for this game
                                directory_query = {
                                    "operationName": "DirectoryPage_Game",
                                    "variables": {
                                        "limit": 50,
                                        "slug": slug,
                                        "imageWidth": 50,
                                        "includeIsDJ": False,
                                        "options": {
                                            "broadcasterLanguages": [],
                                            "freeformTags": None,
                                            "includeRestricted": ["SUB_ONLY_LIVE"],
                                            "recommendationsContext": {"platform": "web"},
                                            "sort": "VIEWER_COUNT",
                                            "systemFilters": [],
                                            "tags": [],
                                            "requestID": "JIRA-VXP-2397",
                                        },
                                        "includeIsDJ": False,
                                        "sortTypeIsRecency": False,
                                    },
                                    "extensions": {
                                        "persistedQuery": {
                                            "version": 1,
                                            "sha256Hash": "c7c9d5aad09155c4161d2382092dc44610367f3536aac39019ec2582ae5065f9"
                                        }
                                    }
                                }
                                
                                response = requests.post(url, json=directory_query, headers=headers)
                                if response.status_code == 200:
                                    data = response.json()
                                    streams = data.get('data', {}).get('game', {}).get('streams', {}).get('edges', [])
                                    
                                    game_streamers = []
                                    for stream in streams:
                                        node = stream.get('node', {})
                                        broadcaster = node.get('broadcaster')
                                        if broadcaster and broadcaster.get('displayName'):
                                            streamer_name = broadcaster['displayName']
                                            all_streamers.add(streamer_name)
                                            game_streamers.append(streamer_name)
                                    
                                    if game_streamers:
                                        campaign_info[game] = game_streamers
                                        print(f"Found {len(game_streamers)} streamers for {game}")
                    
                    except Exception as e:
                        print(f"Failed to fetch streamers for {game}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Alternative GraphQL approach failed: {e}")
            
            # Method 3: Fallback to known drop streamer sources
            if not all_streamers:
                print("Falling back to known drop streamer sources...")
                
                # Add known popular drop streamers
                known_streamers = [
                    # Rust streamers (some examples)
                    "Shroud", "summit1g", "xQcOW", "pokimane", "DisguisedToast",
                    "Myth", "TSM_Daequan", "Ninja", "DrLupo", "TimTheTatman",
                    # Add more as needed
                ]
                
                for streamer in known_streamers:
                    all_streamers.add(streamer)
                
                campaign_info["Popular Streamers"] = known_streamers
                print(f"Added {len(known_streamers)} known popular streamers")
            
            return list(all_streamers), campaign_info
            
        except Exception as e:
            print(f"Error fetching drop campaigns: {e}")
            return [], {}

    def get_drops_enabled_streamers(self, game_name):
        """
        Get streamers that have drops enabled for a specific game.
        This is used when campaigns don't have specific eligible streamers listed.
        """
        try:
            print(f"Fetching drops-enabled streamers for {game_name}...")
            
            url = "https://gql.twitch.tv/gql"
            headers = {
                'Client-Id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # First get the game slug
            slug_query = {
                "operationName": "DirectoryGameRedirect",
                "variables": {"name": game_name},
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "1f0300090caceec51f33c5e20647aceff9017f740f223c3c532ba6fa59f6b6cc"
                    }
                }
            }
            
            response = requests.post(url, json=slug_query, headers=headers)
            if response.status_code != 200:
                return []
            
            data = response.json()
            game_data = data.get('data', {}).get('game')
            if not game_data or not game_data.get('slug'):
                return []
            
            slug = game_data['slug']
            
            # Get live streamers with drops enabled for this game
            # Using the same query structure as TwitchDropsMiner
            directory_query = {
                "operationName": "DirectoryPage_Game",
                "variables": {
                    "limit": 100,  # Get more streamers
                    "slug": slug,
                    "imageWidth": 50,
                    "includeIsDJ": False,
                    "options": {
                        "broadcasterLanguages": [],
                        "freeformTags": None,
                        "includeRestricted": ["SUB_ONLY_LIVE"],
                        "recommendationsContext": {"platform": "web"},
                        "sort": "VIEWER_COUNT",  # Sort by viewers for best streamers
                        "systemFilters": ["DROPS_ENABLED"],  # This is the key filter!
                        "tags": [],
                        "requestID": "JIRA-VXP-2397",
                    },
                    "includeIsDJ": False,
                    "sortTypeIsRecency": False,
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "c7c9d5aad09155c4161d2382092dc44610367f3536aac39019ec2582ae5065f9"
                    }
                }
            }
            
            response = requests.post(url, json=directory_query, headers=headers)
            if response.status_code != 200:
                print(f"      Failed to fetch drops-enabled streamers: HTTP {response.status_code}")
                return []
            
            data = response.json()
            streams = data.get('data', {}).get('game', {}).get('streams', {}).get('edges', [])
            
            streamers = []
            for stream in streams:
                node = stream.get('node', {})
                broadcaster = node.get('broadcaster')
                if broadcaster and broadcaster.get('displayName'):
                    streamers.append(broadcaster['displayName'])
            
            print(f"      Found {len(streamers)} drops-enabled streamers")
            return streamers
            
        except Exception as e:
            print(f"Error fetching drops-enabled streamers for {game_name}: {e}")
            return []

    def get_drops_enabled_streamers_by_slug(self, game_slug, game_name, target_count=5):
        """
        Get streamers that have drops enabled for a specific game using the game slug directly.
        Filters for ASCII-only streamers and fetches multiple pages to get accurate total count.
        Returns tuple: (top_streamers_list, total_ascii_count)
        """
        try:
            print(f"    Fetching drops-enabled streamers for {game_name} (slug: {game_slug})...")
            
            url = "https://gql.twitch.tv/gql"
            headers = {
                'Client-Id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            ascii_streamers = []
            skipped_streamers = []
            offset = 0
            limit = 20
            
            # Fetch multiple pages to get a more accurate total count
            # We'll fetch up to 100 streamers (5 pages) to get a better picture
            max_pages = 5
            pages_fetched = 0
            
            while pages_fetched < max_pages and offset < 100:  # Safety limit
                # Get live streamers with drops enabled for this game using the slug directly
                directory_query = {
                    "operationName": "DirectoryPage_Game",
                    "variables": {
                        "limit": limit,
                        "cursor": str(offset) if offset > 0 else None,
                        "slug": game_slug,
                        "imageWidth": 50,
                        "includeIsDJ": False,
                        "options": {
                            "broadcasterLanguages": [],
                            "freeformTags": None,
                            "includeRestricted": ["SUB_ONLY_LIVE"],
                            "recommendationsContext": {"platform": "web"},
                            "sort": "VIEWER_COUNT",  # Sort by viewers for best streamers
                            "systemFilters": ["DROPS_ENABLED"],  # This is the key filter!
                            "tags": [],
                            "requestID": "JIRA-VXP-2397",
                        },
                        "includeIsDJ": False,
                        "sortTypeIsRecency": False,
                    },
                    "extensions": {
                        "persistedQuery": {
                            "version": 1,
                            "sha256Hash": "c7c9d5aad09155c4161d2382092dc44610367f3536aac39019ec2582ae5065f9"
                        }
                    }
                }
                
                response = requests.post(url, json=directory_query, headers=headers)
                if response.status_code != 200:
                    print(f"      Failed to fetch drops-enabled streamers: HTTP {response.status_code}")
                    break
                
                try:
                    data = response.json()
                except:
                    print(f"      Failed to parse JSON response")
                    break
                
                # Check for GraphQL errors
                if 'errors' in data:
                    print(f"      GraphQL errors: {data['errors']}")
                    break
                
                # Navigate through the response structure carefully
                if 'data' not in data:
                    print(f"      No 'data' field in response")
                    break
                    
                if 'game' not in data['data'] or not data['data']['game']:
                    print(f"      No game data in response")
                    break
                    
                game_data = data['data']['game']
                if 'streams' not in game_data or not game_data['streams']:
                    print(f"      No streams data in game response")
                    break
                    
                streams_data = game_data['streams']
                if 'edges' not in streams_data:
                    print(f"      No edges in streams data")
                    break
                    
                streams = streams_data['edges']
                if not streams:
                    print(f"      No stream edges found at offset {offset}")
                    break
                
                # Process streamers and filter for ASCII
                for stream in streams:
                    node = stream.get('node', {})
                    broadcaster = node.get('broadcaster')
                    if broadcaster and broadcaster.get('displayName'):
                        streamer_name = broadcaster['displayName']
                        if streamer_name.isascii():
                            ascii_streamers.append(streamer_name)
                        else:
                            skipped_streamers.append(streamer_name)
                
                offset += limit
                pages_fetched += 1
            
            if skipped_streamers:
                print(f"      ⚠️  Skipped {len(skipped_streamers)} non-ASCII streamers: {', '.join(skipped_streamers[:3])}{'...' if len(skipped_streamers) > 3 else ''}")
            
            total_ascii_count = len(ascii_streamers)
            top_streamers = ascii_streamers[:target_count]
            
            print(f"      ✅ Found {total_ascii_count} ASCII streamers for {game_name} (showing top {len(top_streamers)})")
            return top_streamers, total_ascii_count
            
        except Exception as e:
            print(f"Error fetching drops-enabled streamers for {game_name}: {e}")
            return [], 0

    def load_twitch_auth_cookies(self):
        """
        Load authentication cookies from Twitch-Channel-Points-Miner's cookie file.
        This allows us to authenticate with Twitch and access real drop campaigns.
        """
        # Get the directory where gibdrop.py is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check common locations for Twitch-Channel-Points-Miner cookie files
        possible_paths = [
            os.path.join(script_dir, "cookies"),  # Same directory as gibdrop.py
            "cookies",  # Current working directory
            "../Twitch-Channel-Points-Miner-v2/cookies",  # Parent directory
            "../../Twitch-Channel-Points-Miner-v2/cookies",  # Grandparent directory
        ]
        
        # Add common installation paths
        home_dir = os.path.expanduser("~")
        possible_paths.extend([
            os.path.join(home_dir, "Twitch-Channel-Points-Miner-v2", "cookies"),
            os.path.join(home_dir, "twitch", "Twitch-Channel-Points-Miner-v2", "cookies"),
            "/opt/Twitch-Channel-Points-Miner-v2/cookies",  # Common system install location
        ])
        
        print("🔍 Looking for authentication cookies...")
        cookies = {}
        
        for cookie_dir in possible_paths:
            print(f"   Checking: {cookie_dir}")
            try:
                if os.path.exists(cookie_dir):
                    print(f"   ✅ Found directory: {cookie_dir}")
                    # Look for .pkl files in the cookies directory
                    pkl_files = [f for f in os.listdir(cookie_dir) if f.endswith('.pkl')]
                    if pkl_files:
                        print(f"   📁 Found {len(pkl_files)} .pkl files: {pkl_files}")
                        
                        for filename in pkl_files:
                            cookie_path = os.path.join(cookie_dir, filename)
                            try:
                                with open(cookie_path, 'rb') as f:
                                    cookie_data = pickle.load(f)
                                
                                # Parse cookie data (list of cookie dicts)
                                if isinstance(cookie_data, list):
                                    for cookie in cookie_data:
                                        if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                                            cookies[cookie['name']] = cookie['value']
                                
                                print(f"✅ Loaded authentication cookies from {cookie_path}")
                                print(f"   Found cookies: {list(cookies.keys())}")
                                return cookies
                                
                            except Exception as e:
                                print(f"⚠ Failed to load {cookie_path}: {e}")
                                continue
                    else:
                        print(f"   ⚠ Directory exists but no .pkl files found")
                else:
                    print(f"   ❌ Directory not found")
            except Exception as e:
                print(f"   ❌ Error checking {cookie_dir}: {e}")
                continue
        
        print("❌ No authentication cookies found in any location")
        return cookies

    def get_current_campaigns(self):
        """
        Fetch current active drop campaigns from Twitch using authentication cookies.
        
        This function uses Twitch-Channel-Points-Miner's saved authentication cookies to access
        real drop campaign data through Twitch's Inventory GraphQL API.
        """
        try:
            print("Fetching active drop campaigns from Twitch...")
            
            # Try to load authentication cookies from Twitch-Channel-Points-Miner
            auth_cookies = self.load_twitch_auth_cookies()
            
            if not auth_cookies:
                print("❌ No authentication cookies found")
                print("💡 To get real drop campaigns:")
                print("   1. Run Twitch-Channel-Points-Miner once to generate auth cookies")
                print("   2. Or use other menu options to select streamers manually")
                return []
            
            print("🔑 Using Twitch-Channel-Points-Miner authentication cookies")
            
            # Try to get real campaigns using the Inventory API
            real_campaigns = self._fetch_real_campaigns_via_inventory(auth_cookies)
            if real_campaigns:
                print(f"🎉 Found {len(real_campaigns)} REAL active drop campaigns!")
                return real_campaigns
            else:
                print("ℹ️ No active drop campaigns found in user's inventory")
                return []
            
        except Exception as e:
            print(f"Error fetching campaigns: {e}")
            return []

    def _fetch_real_campaigns_via_inventory(self, auth_cookies):
        """
        Fetch real drop campaigns using the Inventory GraphQL API with authentication.
        """
        try:
            url = "https://gql.twitch.tv/gql"
            headers = {
                'Client-Id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Add authentication
            cookie_string = "; ".join([f"{name}={value}" for name, value in auth_cookies.items()])
            headers['Cookie'] = cookie_string
            
            if 'auth-token' in auth_cookies:
                headers['Authorization'] = f"OAuth {auth_cookies['auth-token']}"
            
            print("🔍 Trying multiple campaign discovery methods...")
            
            # Method 1: Inventory query (shows enrolled campaigns)
            print("  📋 Method 1: Checking user inventory for enrolled campaigns...")
            inventory_query = {
                "operationName": "Inventory",
                "variables": {
                    "fetchRewardCampaigns": False,
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "d86775d0ef16a63a33ad52e80eaff963b2d5b72fada7c991504a57496e1d8e4b"
                    }
                }
            }
            
            response = requests.post(url, json=inventory_query, headers=headers, timeout=15)
            
            inventory_campaigns = []
            if response.status_code == 200:
                data = response.json()
                
                if 'data' in data and data['data'] and 'currentUser' in data['data']:
                    user_data = data['data']['currentUser']
                    inventory = user_data.get('inventory', {})
                    campaigns_in_progress = inventory.get('dropCampaignsInProgress', [])
                    
                    print(f"    ✅ Found {len(campaigns_in_progress)} campaigns in user inventory")
                    
                    print(f"    ✅ Found {len(campaigns_in_progress)} campaigns in user inventory")
                    
                    for campaign_data in campaigns_in_progress:
                        try:
                            status = campaign_data.get('status', 'UNKNOWN')
                            campaign_name = campaign_data.get('name', 'Unknown Campaign')
                            game_data = campaign_data.get('game', {})
                            game_name = game_data.get('name', 'Unknown Game') if game_data else 'Unknown Game'
                            
                            print(f"    📋 Inventory: {campaign_name} ({game_name}) - Status: {status}")
                            
                            # Only include active campaigns
                            if status == 'ACTIVE':
                                campaign_name = campaign_data.get('name', 'Unknown Campaign')
                                game_data = campaign_data.get('game', {})
                                
                                # Get game information from the campaign data
                                if game_data:
                                    game_name = game_data.get('name', 'Unknown Game')
                                    game_slug = game_data.get('slug', '')
                                else:
                                    game_name = 'Unknown Game'
                                    game_slug = ''
                                
                                # Try to get eligible streamers from time-based drops
                                eligible_streamers = []
                                drops = campaign_data.get('timeBasedDrops', [])
                                
                                # Extract streamers from drops if available
                                for drop in drops:
                                    drop_streamers = drop.get('eligibleStreamers', [])
                                    for streamer in drop_streamers:
                                        if isinstance(streamer, dict) and streamer.get('displayName'):
                                            eligible_streamers.append(streamer['displayName'])
                                        elif isinstance(streamer, str):
                                            eligible_streamers.append(streamer)
                                
                                # Remove duplicates while preserving order
                                unique_streamers = []
                                seen = set()
                                for streamer in eligible_streamers:
                                    if streamer not in seen:
                                        unique_streamers.append(streamer)
                                        seen.add(streamer)
                                
                                # If no streamers found in campaign data, try to fetch them separately
                                if not unique_streamers and game_name and game_name != 'Unknown Game':
                                    print(f"    No eligible streamers in campaign data, fetching drops-enabled streamers for {game_name}...")
                                    drops_enabled_streamers, total_fetched = self.get_drops_enabled_streamers_by_slug(game_slug, game_name, 5)
                                    unique_streamers = drops_enabled_streamers  # Already limited to 5 ASCII streamers
                                else:
                                    total_fetched = len(unique_streamers)  # Use actual streamers found in campaign data
                                
                                campaign_info = {
                                    'name': campaign_name,
                                    'game': game_name,
                                    'slug': game_slug,
                                    'streamers': unique_streamers,
                                    'streamer_count': len(unique_streamers),
                                    'fetched_streamer_count': total_fetched,
                                    'total_viewers': 0,
                                    'status': status,
                                    'campaign_id': campaign_data.get('id', ''),
                                    'start_time': campaign_data.get('startAt', ''),
                                    'end_time': campaign_data.get('endAt', ''),
                                    'details_url': campaign_data.get('detailsURL', ''),
                                    'image_url': campaign_data.get('imageURL', ''),
                                    'drops_count': len(drops),
                                    'type': 'INVENTORY_CAMPAIGN'
                                }
                                inventory_campaigns.append(campaign_info)
                                print(f"    🏆 {campaign_name} ({game_name}) - {len(drops)} drops, {len(unique_streamers)} streamers")
                                
                        except Exception as e:
                            print(f"    Error parsing inventory campaign: {e}")
                            continue
                else:
                    print("    ❌ No user data in inventory response")
            else:
                print(f"    ❌ Inventory API failed: HTTP {response.status_code}")
            
            # Method 2: Try ViewerDropsDashboard API (different endpoint, might show more campaigns)
            print("  🌐 Method 2: Checking ViewerDropsDashboard API...")
            try:
                campaigns_query = {
                    "operationName": "ViewerDropsDashboard",
                    "variables": {},
                    "extensions": {
                        "persistedQuery": {
                            "version": 1,
                            "sha256Hash": "5a33c1d45d3012503f8c9a7eccdde3de5b4b5d9ec262cce16d2e93bd5afecbb0"
                        }
                    }
                }
                
                response = requests.post(url, json=campaigns_query, headers=headers, timeout=15)
                public_campaigns = []
                
                if response.status_code == 200:
                    data = response.json()
                    campaigns_data = data.get('data', {}).get('currentUser', {}).get('dropCampaigns', [])
                    
                    print(f"    ✅ Found {len(campaigns_data)} campaigns in dashboard API")
                    
                    for campaign_data in campaigns_data:
                        try:
                            status = campaign_data.get('status', 'UNKNOWN')
                            if status == 'ACTIVE':
                                campaign_name = campaign_data.get('name', 'Unknown Campaign')
                                game_data = campaign_data.get('game', {})
                                game_name = game_data.get('name', 'Unknown Game') if game_data else 'Unknown Game'
                                game_slug = game_data.get('slug', '') if game_data else ''
                                
                                # Check if this campaign is already in our inventory list
                                already_found = any(c['name'] == campaign_name for c in inventory_campaigns)
                                if not already_found:
                                    # Get streamers for this campaign
                                    streamers = []
                                    total_fetched = 0
                                    if game_slug:
                                        streamers, total_fetched = self.get_drops_enabled_streamers_by_slug(game_slug, game_name, 5)
                                    
                                    campaign_info = {
                                        'name': campaign_name,
                                        'game': game_name,
                                        'slug': game_slug,
                                        'streamers': streamers,
                                        'streamer_count': len(streamers),
                                        'fetched_streamer_count': total_fetched,
                                        'total_viewers': 0,
                                        'status': status,
                                        'campaign_id': campaign_data.get('id', ''),
                                        'start_time': campaign_data.get('startAt', ''),
                                        'end_time': campaign_data.get('endAt', ''),
                                        'details_url': campaign_data.get('detailsURL', ''),
                                        'image_url': campaign_data.get('imageURL', ''),
                                        'drops_count': len(campaign_data.get('timeBasedDrops', [])),
                                        'type': 'DASHBOARD_CAMPAIGN'
                                    }
                                    public_campaigns.append(campaign_info)
                                    print(f"    🌟 {campaign_name} ({game_name}) - dashboard campaign, {len(streamers)} streamers")
                                
                        except Exception as e:
                            print(f"    Error parsing public campaign: {e}")
                            continue
                            
                else:
                    print(f"    ❌ ViewerDropsDashboard API failed: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"    ❌ ViewerDropsDashboard query error: {e}")
                public_campaigns = []
            
            # Combine campaigns from both authenticated APIs
            all_campaigns = inventory_campaigns + public_campaigns
            print(f"🎯 Total campaigns found: {len(all_campaigns)} ({len(inventory_campaigns)} inventory + {len(public_campaigns)} dashboard)")
            
            return all_campaigns
            
        except Exception as e:
            print(f"❌ Campaign discovery error: {e}")
            return []

    def save_default_streamers(self, streamer_list, filename="default_streamers.txt"):
        # Clean and save streamers (filtering already done during fetching)
        cleaned_streamers = []
        for name in streamer_list:
            cleaned_name = name.strip()
            if cleaned_name:
                cleaned_streamers.append(cleaned_name)
        
        print(f"   📝 Writing {len(cleaned_streamers)} streamers to {filename}")
        
        # Check if filename exists as a directory and remove it
        if os.path.exists(filename) and os.path.isdir(filename):
            print(f"   ⚠️  {filename} exists as directory, removing it...")
            import shutil
            shutil.rmtree(filename)
        
        with open(filename, "w", encoding="utf-8") as f:
            for name in cleaned_streamers:
                f.write(f"{name}\n")

    def load_default_streamers_from_file(self, filename="default_streamers.txt"):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                streamer_names = []
                for line in f:
                    line = line.strip()
                    if line:
                        match = re.match(r'Streamer\("([^\"]+)"\),?', line)
                        if match:
                            streamer_names.append(match.group(1))
                        else:
                            streamer_names.append(line)
                return streamer_names
        except FileNotFoundError:
            return []

    def load_drop_streamers_from_file(self, filename="streamer_names.txt"):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return []

    def load_active_streamers(self):
        try:
            with open("active_streamers.txt", "r", encoding="utf-8") as f:
                filename = f.read().strip()
            return self.load_default_streamers_from_file(filename)
        except FileNotFoundError:
            return []

# Patcher: Ensures run.py exists and is patched for dynamic streamer loading; manages dependency installation.
class Patcher:
    def __init__(self, required_packages):
        self.required_packages = required_packages

    def install_dependencies(self):
        print("Installing required Python packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + self.required_packages)
        print("Dependencies installed.")

    def ensure_run_py(self):
        if not os.path.exists("run.py"):
            if os.path.exists("example.py"):
                shutil.copy("example.py", "run.py")
                print("run.py not found. Copied example.py to run.py.")
            else:
                print("Neither run.py nor example.py found! Attempting to download example.py from GitHub...")
                url = "https://raw.githubusercontent.com/rdavydov/Twitch-Channel-Points-Miner-v2/master/example.py"
                try:
                    urllib.request.urlretrieve(url, "example.py")
                    print("Downloaded example.py from GitHub.")
                    shutil.copy("example.py", "run.py")
                    print("Copied downloaded example.py to run.py.")
                except Exception as e:
                    print(f"Failed to download example.py: {e}")
                    sys.exit(1)

    def patch_run_py(self):
        runpy_path = "run.py"
        backup_path = "run.py.bak"
        if not os.path.exists(runpy_path):
            print("run.py not found!")
            return
        # Backup original if not already backed up
        if not os.path.exists(backup_path):
            shutil.copy(runpy_path, backup_path)
            print("Backed up run.py to run.py.bak.")
        with open(runpy_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Find the last occurrence of twitch_miner.mine(
        pattern = re.compile(r"twitch_miner\.mine\s*\(", re.MULTILINE)
        matches = list(pattern.finditer(content))
        if not matches:
            print("No twitch_miner.mine( call found. No changes made.")
            return
        last_match = matches[-1]
        start = last_match.start()
        paren_start = last_match.end() - 1
        # Bracket matching to find the end
        depth = 0
        end = -1
        for i in range(paren_start, len(content)):
            if content[i] == '(': depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            print("Could not find matching closing parenthesis for twitch_miner.mine(. No changes made.")
            return
        # Replace the entire function call (from start to end+1)
        replacement = (
            "twitch_miner.mine(\n"
            "    streamer_objects,                   # [gibdrop] patched: dynamic streamer list\n"
            "    followers=False,                    # Automatic download the list of your followers\n"
            "    followers_order=FollowersOrder.ASC  # Sort the followers list by follow date. ASC or DESC\n"
            ")\n"
        )
        new_content = content[:start] + replacement + content[end+1:]
        # Insert import and streamer loading if not present
        import_lines = (
            "import os\n\n"
            "def load_active_streamers():\n"
            "    try:\n"
            "        with open('active_streamers.txt', 'r', encoding='utf-8') as f:\n"
            "            filename = f.read().strip()\n"
            "        with open(filename, 'r', encoding='utf-8') as f2:\n"
            "            return [line.strip() for line in f2 if line.strip()]\n"
            "    except Exception as e:\n"
            "        print(f'Failed to load active streamers: {e}')\n"
            "        return []\n\n"
            "streamer_names = load_active_streamers()\n"
            "streamer_objects = [Streamer(name) for name in streamer_names]\n\n"
        )
        if "streamer_objects = [Streamer(name) for name in streamer_names]" not in new_content:
            # Insert after Streamer import
            streamer_import = "from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings"
            idx = new_content.find(streamer_import)
            if idx != -1:
                insert_idx = new_content.find("\n", idx) + 1
                new_content = new_content[:insert_idx] + import_lines + new_content[insert_idx:]
                print("Inserted streamer loading logic for active_streamers.txt.")
            else:
                print("Could not find Streamer import to insert streamer loading logic. Please check run.py.")
        with open(runpy_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("run.py patched successfully! If anything went wrong, restore from run.py.bak.")

class GibdropMenu:
    def __init__(self, streamer_manager, patcher):
        self.streamer_manager = streamer_manager
        self.patcher = patcher
        self.ASCII_ART = r"""
          __          __                         
       __/\ \        /\ \                        
   __ /\_\ \ \____   \_\ \  _ __   ___   _____   
 /'_ `\/\ \ \ '__`\  /'_` \/\`'__\/ __`\/\ '__`\ 
/\ \L\ \ \ \ \ \L\ \/\ \L\ \ \ \//\ \L\ \ \ \L\ \
\ \____ \ \_\ \_,__/\ \___,_\ \_\\ \____/\ \ ,__/
 \/___L\ \/_/\/___/  \/__,_ /\/_/ \/___/  \ \ \/ 
   /\____/                                 \ \_\ 
   \_/__/                                   \/_/ 
"""
        self.CREDIT_STR = "vibe coded by ctrl-a-d"

    def print_ascii_art(self):
        print(self.ASCII_ART)
        print(self.CREDIT_STR)

    def clear_screen(self):
        os.system("cls" if os.name == "nt" else "clear")

    def press_any_key(self):
        input("Press Enter to continue...")
        self.clear_screen()

    def set_active_streamers(self, filename):
        with open("active_streamers.txt", "w", encoding="utf-8") as f:
            f.write(filename)

    def set_default_streamers(self):
        print("Enter your default streamers (comma separated, e.g. streamer1, streamer2, streamer3):")
        user_input = input("Streamers: ")
        streamer_list = [name.strip() for name in user_input.split(",") if name.strip()]
        if streamer_list:
            self.streamer_manager.save_default_streamers(streamer_list)
            print(f"Saved {len(streamer_list)} default streamers to default_streamer.txt.")
        else:
            print("No streamers entered. Nothing was saved.")
        self.press_any_key()

    def load_default_streamers_menu(self):
        self.set_active_streamers("default_streamers.txt")
        print("Default streamers set as active.")
        self.press_any_key()

    def get_all_drop_streamers(self):
        """Fetch streamers from ALL active Twitch drop campaigns (not just Rust)"""
        all_streamers, campaign_info = self.streamer_manager.get_all_drop_streamers()
        
        if not all_streamers:
            print("No active drop campaigns found or failed to fetch data.")
            print("This might be because:")
            print("1. No drop campaigns are currently active")
            print("2. Twitch API is not accessible")
            print("3. Authentication might be required for some campaigns")
            self.press_any_key()
            return
        
        print(f"\nFound {len(all_streamers)} unique streamers across all active drop campaigns:\n")
        
        # Display by game
        for game, streamers in campaign_info.items():
            print(f"{game}:")
            for streamer in streamers:
                print(f"  - {streamer}")
            print()
        
        # Save all streamers to file
        self.streamer_manager.save_default_streamers(sorted(all_streamers), filename="all_drop_streamers.txt")
        print(f"Saved {len(all_streamers)} streamers to all_drop_streamers.txt")
        
        # Also save by game
        for game, streamers in campaign_info.items():
            safe_game_name = "".join(c for c in game if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"drop_streamers_{safe_game_name.replace(' ', '_').lower()}.txt"
            self.streamer_manager.save_default_streamers(streamers, filename=filename)
            print(f"Saved {len(streamers)} {game} streamers to {filename}")
        
        self.press_any_key()

    def browse_and_select_campaigns(self):
        """Interactive campaign browser - shows current campaigns and lets user select which to add"""
        print("🔍 Fetching current campaigns...")
        campaigns = self.streamer_manager.get_current_campaigns()

        # Always try to fetch Rust drops first
        print("🦀 Fetching Rust drop streamers...")
        try:
            rust_streamers, drops_count, campaign_start, campaign_end, is_active = self.streamer_manager.get_rust_drops()
            
            if rust_streamers and is_active:
                # Format campaign dates for display
                start_time = campaign_start.strftime('%Y-%m-%d %H:%M UTC') if campaign_start else ''
                end_time = campaign_end.strftime('%Y-%m-%d %H:%M UTC') if campaign_end else ''
                
                # Create a virtual Rust campaign as the first option
                rust_campaign = {
                    'name': 'Rust Drop Streamers',
                    'game': 'Rust',
                    'slug': 'rust',
                    'streamers': rust_streamers,
                    'streamer_count': len(rust_streamers),
                    'fetched_streamer_count': len(rust_streamers),
                    'total_viewers': 0,
                    'status': 'ACTIVE',
                    'campaign_id': 'rust_drops',
                    'start_time': start_time,
                    'end_time': end_time,
                    'details_url': 'https://twitch.facepunch.com/#drops',
                    'image_url': '',
                    'drops_count': drops_count,
                    'type': 'RUST_DROPS',
                    'is_active': is_active
                }
                
                # Insert Rust campaign at the beginning
                campaigns.insert(0, rust_campaign)
                print(f"✅ Added Rust drops as campaign #1 ({len(rust_streamers)} streamers)")
            elif campaign_start and not is_active:
                print("⚠️ Rust campaign found but not currently active")
            else:
                print("⚠️ No Rust drop streamers found")
        except Exception as e:
            print(f"⚠️ Error fetching Rust streamers: {e}")

        # Show logs/errors before clearing screen
        print("\n(Review any logs above. Press Enter to continue...)")
        input()

        if not campaigns:
            print("❌ No active drop campaigns found.")
            print("\nThis could be because:")
            print("  • No drop campaigns are currently active on Twitch")
            print("  • Authentication cookies are missing or expired")
            print("  • Twitch-Channel-Points-Miner hasn't been run yet to generate cookies")
            print("  • Rust drops page is not accessible")
            print("\n💡 To get drop campaigns:")
            print("  1. Run Twitch-Channel-Points-Miner first to generate authentication")
            print("  2. Check https://www.twitch.tv/drops/campaigns manually")
            print("  3. Use other menu options to select streamers by game")
            self.press_any_key()
            return

        # We only show real campaigns now
        selected_campaigns = []

        while True:
            self.clear_screen()
            self.print_ascii_art()

            print(f"\n🎮 ACTIVE DROP CAMPAIGNS ({len(campaigns)} found)")
            print("=" * 60)
            print("   🦀 Rust = Rust drop streamers (from Facepunch)")
            print("   📋 Inventory = Campaigns you've joined (from Inventory API)")
            print("   🌐 Dashboard = Campaigns from ViewerDropsDashboard API")
            print()

            # Display campaigns with selection status
            for i, campaign in enumerate(campaigns, 1):
                status = "✓ SELECTED" if campaign in selected_campaigns else ""

                # Show source type with emoji
                source_emoji = {
                    'RUST_DROPS': '🦀',
                    'INVENTORY_CAMPAIGN': '📋',
                    'DASHBOARD_CAMPAIGN': '🌐'
                }.get(campaign.get('type', 'INVENTORY_CAMPAIGN'), '🏆')

                # Format display differently for Rust vs other campaigns
                if campaign.get('type') == 'RUST_DROPS':
                    # Rust: Show campaign name first (traditional format)
                    if status:
                        print(f"{i:2}) [{status}] {source_emoji} {campaign['name']}")
                    else:
                        print(f"{i:2}) {source_emoji} {campaign['name']}")
                    
                    # Show Rust-specific details
                    fetched_count = campaign.get('fetched_streamer_count', campaign.get('streamer_count', 0))
                    if fetched_count > 0:
                        drops_count = campaign.get('drops_count', 0)
                        if drops_count > 0:
                            print(f"     🎮 {campaign['game']} | 👥 {fetched_count} streamers with drops | 🎁 {drops_count} general drops")
                        else:
                            print(f"     🎮 {campaign['game']} | 👥 {fetched_count} streamers with drops")
                    else:
                        print(f"     🎮 {campaign['game']} | ❌ No eligible streamers found")
                else:
                    # Other campaigns: Show game name first, then campaign details
                    if status:
                        print(f"{i:2}) [{status}] 🎮 {campaign['game']}")
                    else:
                        print(f"{i:2}) 🎮 {campaign['game']}")
                    
                    # Show campaign details underneath
                    fetched_count = campaign.get('fetched_streamer_count', campaign.get('streamer_count', 0))
                    streamer_count = campaign.get('streamer_count', 0)
                    if fetched_count > 0:
                        if fetched_count > 50:
                            print(f"     {source_emoji} {campaign['name']} | 👥 50+ active streamers (top {streamer_count} shown)")
                        else:
                            print(f"     {source_emoji} {campaign['name']} | 👥 {fetched_count} active streamers (top {streamer_count} shown)")
                    else:
                        print(f"     {source_emoji} {campaign['name']} | ❌ No eligible streamers found")

                # Show campaign details
                if campaign.get('type') == 'RUST_DROPS':
                    # Show Rust campaign timing if available
                    if campaign.get('start_time') and campaign.get('end_time'):
                        print(f"     ⏰ {campaign['start_time']} → {campaign['end_time']}")
                elif campaign.get('drops_count', 0) > 0:
                    print(f"     🎁 {campaign['drops_count']} drops available")
            
            print("\n" + "=" * 60)
            if selected_campaigns:
                total_selected_streamers = sum(len(c.get('streamers', [])) for c in selected_campaigns)
                print(f"🎯 Selected: {len(selected_campaigns)} campaigns, {total_selected_streamers} streamers")
            
            print("\n💡 Tip: If you're missing a campaign, you can edit selected_campaigns.txt and add the streamers you need")
            
            print("\nOptions:")
            print("1-{}) Toggle campaign selection (supports multiple: '1,2' or '1 2 3')".format(len(campaigns)))
            print("v) View streamers in selected campaigns")
            print("s) Save selected campaigns and set as active")
            print("a) Select all campaigns")
            print("c) Clear all selections")
            print("i) Show campaign info")
            print("0) Cancel and return to main menu")
            
            choice = input("\nEnter your choice: ").strip().lower()
            
            if choice == "0":
                return
            elif choice == "v":
                if not selected_campaigns:
                    print("\nNo campaigns selected yet.")
                    input("Press Enter to continue...")
                    continue
                
                print(f"\n📋 STREAMERS IN SELECTED CAMPAIGNS")
                print("=" * 50)
                for campaign in selected_campaigns:
                    streamer_list = campaign.get('streamers', [])
                    count = len(streamer_list)
                    if count > 0:
                        if campaign.get('type') == 'RUST_DROPS':
                            drops_count = campaign.get('drops_count', 0)
                            if drops_count > 0:
                                print(f"\n🦀 {campaign['name']} ({count} streamers with drops + {drops_count} general drops):")
                            else:
                                print(f"\n🦀 {campaign['name']} ({count} streamers with drops):")
                        else:
                            print(f"\n🎮 {campaign['name']} (Top {count} by viewer count):")
                        for i, streamer in enumerate(streamer_list, 1):
                            print(f"  {i:2}. {streamer}")
                    else:
                        print(f"\n🎮 {campaign['name']} (No streamers available)")
                
                input("\nPress Enter to continue...")
                continue
                
            elif choice == "i":
                print(f"\n📊 CAMPAIGN INFORMATION")
                print("=" * 50)
                print("🦀 Rust Drops:")
                print("   - Fetched from Facepunch's official Rust drops page")
                print("   - Streamers with drops = specific streamers that drop Rust items")
                print("   - General drops = items that drop from watching any Rust stream")
                print("🏆 Real Drop Campaigns:")
                print("   - Fetched from Twitch's Inventory API")
                print("   - These show actual active drop campaigns")
                print("   - Only streamers eligible for these campaigns can drop rewards")

                # Calculate total fetched streamers (not just top 5)
                total_fetched = sum(c.get('fetched_streamer_count', c.get('streamer_count', 0)) for c in campaigns)
                print(f"\n Total campaigns: {len(campaigns)}")
                print(f" Total available streamers: {total_fetched}")

                if campaigns:
                    print(f"\n📅 Campaign Details:")
                    for campaign in campaigns:
                        fetched_count = campaign.get('fetched_streamer_count', campaign.get('streamer_count', 0))
                        if campaign.get('type') == 'RUST_DROPS':
                            drops_count = campaign.get('drops_count', 0)
                            if drops_count > 0:
                                streamer_str = f"{fetched_count} streamers with drops + {drops_count} general drops"
                            else:
                                streamer_str = f"{fetched_count} streamers with drops"
                        elif fetched_count > 50:
                            shown_count = min(5, campaign.get('streamer_count', 0))
                            streamer_str = f"50+ active streamers (top {shown_count} shown)"
                        else:
                            shown_count = min(5, fetched_count) if fetched_count > 0 else 0
                            streamer_str = f"{fetched_count} active streamer{'s' if fetched_count != 1 else ''} (top {shown_count} shown)"
                        print(f"   • {campaign['name']} ({campaign['game']})")
                        print(f"     - {streamer_str}")
                        if campaign.get('drops_count') and campaign.get('type') != 'RUST_DROPS':
                            print(f"     - {campaign['drops_count']} drop rewards")

                input("\nPress Enter to continue...")
                continue
                
            elif choice == "s":
                if not selected_campaigns:
                    print("\nNo campaigns selected. Please select at least one campaign first.")
                    input("Press Enter to continue...")
                    continue
                
                # Combine all selected streamers
                all_selected_streamers = []
                
                for campaign in selected_campaigns:
                    streamers = campaign.get('streamers', [])
                    all_selected_streamers.extend(streamers)
                
                # Remove duplicates while preserving order
                unique_streamers = []
                seen = set()
                for streamer in all_selected_streamers:
                    if streamer not in seen:
                        unique_streamers.append(streamer)
                        seen.add(streamer)
                
                # Save combined file and individual campaign files
                combined_filename = "selected_campaigns.txt"
                self.streamer_manager.save_default_streamers(unique_streamers, combined_filename)
                
                # Also save individual campaign files for reference
                for campaign in selected_campaigns:
                    if campaign.get('type') == 'RUST_DROPS':
                        individual_filename = "rust_drop_streamers.txt"
                    else:
                        safe_name = "".join(c for c in campaign['name'] if c.isalnum() or c in (' ', '-', '_')).strip()
                        individual_filename = f"campaign_{safe_name.replace(' ', '_').lower()}.txt"
                    
                    campaign_streamers = campaign.get('streamers', [])
                    if campaign_streamers:
                        self.streamer_manager.save_default_streamers(campaign_streamers, individual_filename)
                
                print(f"\n✅ SAVED SUCCESSFULLY!")
                print(f"📁 Combined file: {combined_filename} ({len(unique_streamers)} unique streamers)")
                
                # Ask if user wants to set as active
                set_active = input(f"\nSet streamers as active? (y/n): ").strip().lower()
                if set_active == 'y':
                    self.set_active_streamers(combined_filename)
                    print("✅ Streamers set as active!")
                
                input("\nPress Enter to continue...")
                return
                
            elif choice == "a":
                selected_campaigns = campaigns.copy()
                print(f"\n✅ Selected all {len(campaigns)} campaigns!")
                input("Press Enter to continue...")
                continue
                
            elif choice == "c":
                selected_campaigns.clear()
                print("\n🗑️ Cleared all selections.")
                input("Press Enter to continue...")
                continue
                
            else:
                # Try to parse as campaign number(s) - support multiple selections
                try:
                    # Handle multiple campaign numbers separated by commas, spaces, or both
                    # Examples: "1,2", "1, 2", "1 2", "1,2,3"
                    choice_clean = choice.replace(',', ' ')  # Replace commas with spaces
                    campaign_numbers = [int(x.strip()) for x in choice_clean.split() if x.strip()]
                    
                    if not campaign_numbers:
                        print(f"\n❌ No valid numbers found. Please try again.")
                        input("Press Enter to continue...")
                        continue
                    
                    # Check if all numbers are valid
                    invalid_numbers = [num for num in campaign_numbers if not (1 <= num <= len(campaigns))]
                    if invalid_numbers:
                        print(f"\n❌ Invalid campaign number(s): {invalid_numbers}. Please enter numbers 1-{len(campaigns)}.")
                        input("Press Enter to continue...")
                        continue
                    
                    # Process each valid campaign number
                    selected_count = 0
                    deselected_count = 0
                    
                    for campaign_num in campaign_numbers:
                        campaign = campaigns[campaign_num - 1]
                        if campaign in selected_campaigns:
                            selected_campaigns.remove(campaign)
                            deselected_count += 1
                            print(f"❌ Deselected: {campaign['name']}")
                        else:
                            selected_campaigns.append(campaign)
                            selected_count += 1
                            streamer_count = len(campaign.get('streamers', []))
                            if streamer_count > 0:
                                if campaign.get('type') == 'RUST_DROPS':
                                    print(f"✅ Selected: {campaign['name']} ({streamer_count} Rust streamers)")
                                else:
                                    print(f"✅ Selected: {campaign['name']} (Top {streamer_count} by viewers)")
                            else:
                                print(f"✅ Selected: {campaign['name']} (No streamers)")
                    
                    # Summary message
                    if selected_count > 0 and deselected_count > 0:
                        print(f"\n📋 Summary: Selected {selected_count}, deselected {deselected_count} campaigns")
                    elif selected_count > 0:
                        print(f"\n📋 Summary: Selected {selected_count} campaign{'s' if selected_count > 1 else ''}")
                    elif deselected_count > 0:
                        print(f"\n📋 Summary: Deselected {deselected_count} campaign{'s' if deselected_count > 1 else ''}")
                    
                    input("Press Enter to continue...")
                    
                except ValueError:
                    print(f"\n❌ Invalid input. Please enter campaign numbers (1-{len(campaigns)}).")
                    print(f"💡 Examples: '1', '1,2', '1 2 3', '1, 2, 3'")
                    input("Press Enter to continue...")

    def load_all_drop_streamers_menu(self):
        self.set_active_streamers("all_drop_streamers.txt")
        print("All drop streamers set as active.")
        self.press_any_key()

    def start_twitch_farmer(self):
        print("How do you want to start the Twitch miner?")
        print("1) Docker")
        print("2) CLI (python run.py)")
        print("0) Cancel")
        choice = input("Enter your choice: ")
        if choice == "1":
            print("\nYou selected Docker. To support your patched run.py and dependencies, gibdrop will build a new Docker image based on the official miner image.\n")
            print("This will ensure your patched run.py and all dependencies work inside Docker.\n")
            gibdrop_dockermgr.ensure_dockerfile()
            gibdrop_dockermgr.ensure_txt_files()
            if gibdrop_dockermgr.needs_rebuild():
                print("No patched Docker image found, or you changed the Dockerfile / dependencies recently.\nNeed to rebuild image.")
                confirm = input("Continue and rebuild image? (y/n): ").strip().lower()
                if confirm != "y":
                    print("Cancelled Docker start.")
                    self.press_any_key()
                    return
                gibdrop_dockermgr.build_image()
                reset_terminal_colors()  # Reset colors after Docker build
            result = gibdrop_dockermgr.run_container()
            reset_terminal_colors()  # Reset colors after Docker run
            if result is False:
                # Docker start was cancelled, user already pressed enter in dockermgr, so just return
                return
            self.press_any_key()
        elif choice == "2":
            print("\nTo run the Twitch miner in CLI mode, please exit gibdrop and run:")
            print("  python3 run.py\n")
            print("If you want the miner to keep running after you close this terminal, use 'screen' or 'tmux':")
            print("  screen -S gibdrop-miner\n  python3 run.py\n")
            print("(Detach from screen with Ctrl+A, then D. Reattach with 'screen -r gibdrop-miner')\n")
            print("What would you like to do?")
            print("1) Return to menu")
            print("0) Exit gibdrop")
            subchoice = input("Enter your choice: ").strip()
            if subchoice == "0":
                print("\nExiting gibdrop. Goodbye!\n")
                sys.exit(0)
            else:
                self.clear_screen()
                return
        else:
            print("Cancelled.")
            self.press_any_key()

    def restart_miner_container(self):
        """Restart the Docker container to apply new streamer list changes."""
        print("🔄 Restarting Miner Container")
        print("=" * 50)
        print("This will restart your Docker container to apply any changes")
        print("to your streamer list without needing to rebuild the image.")
        print()
        
        if not self._check_docker_available():
            return
            
        success = gibdrop_dockermgr.restart_container()
        reset_terminal_colors()  # Reset colors after Docker restart
        if not success:
            self.press_any_key()

    def check_miner_status(self):
        """Check the status of the Docker container."""
        print("📊 Miner Container Status")
        print("=" * 50)
        
        if not self._check_docker_available():
            return
            
        gibdrop_dockermgr.check_container_status()
        reset_terminal_colors()  # Reset colors after Docker status check
        self.press_any_key()

    def _check_docker_available(self):
        """Check if Docker is available and accessible."""
        import subprocess
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                print("❌ Docker is not available or not accessible.")
                print("💡 Make sure Docker is installed and running.")
                self.press_any_key()
                return False
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("❌ Docker is not available or not accessible.")
            print("💡 Make sure Docker is installed and running.")
            self.press_any_key()
            return False

    def main_menu(self):
        while True:
            self.print_ascii_art()
            print("\nWelcome to gibdrop! Please select an option:")
            print()
            print("1) Patch run.py")
            print("2) Edit default streamer list")
            print("3) Set default streamer list as active")
            print("4) Browse and select current campaigns")
            print("5) Start twitch miner")
            print("6) Restart miner container (apply new streamer list)")
            print("7) Check miner container status")
            print("0) Exit")
            print()
            choice = input("Enter your choice: ")
            if choice == "1":
                self.patcher.ensure_run_py()
                self.patcher.patch_run_py()
                self.press_any_key()
            elif choice == "2":
                self.set_default_streamers()
            elif choice == "3":
                self.load_default_streamers_menu()
            elif choice == "4":
                self.browse_and_select_campaigns()
            elif choice == "5":
                self.start_twitch_farmer()
            elif choice == "6":
                self.restart_miner_container()
            elif choice == "7":
                self.check_miner_status()
            elif choice == "0":
                print()
                print("Exiting gibdrop. Goodbye!")
                print()
                break
            else:
                print()
                print("Invalid choice. Please try again.")
                self.press_any_key()

def main():
    streamer_manager = StreamerManager()
    patcher = Patcher(REQUIRED_PACKAGES)
    menu = GibdropMenu(streamer_manager, patcher)
    menu.main_menu()

if __name__ == "__main__":
    main()