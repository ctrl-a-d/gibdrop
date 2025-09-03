<p align="center">
  <img src="https://i.imgur.com/w458d2t.png" alt="gibdrop CLI logo" width="400"/>
</p>

# gibdrop

A helper utility for automating and patching the [Twitch-Channel-Points-Miner-v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2) streamer list with real-time drop campaign detection.

## Purpose

Automatically discovers and manages streamers for active Twitch drop campaigns. Fetches Rust drops from the official Facepunch website and real drop campaigns from Twitch's APIs using your Twitch-Channel-Points-Miner authentication cookies.

## Features
- **Campaign Browser**: Interactive selection of active drop campaigns with real streamer data
- **Multi-source Detection**: 
  - 🦀 Rust drops from Facepunch website
  - 📋 Your enrolled campaigns from Twitch Inventory API  
  - 🌐 Public campaigns from Twitch Dashboard API
- **Docker Integration**: Automated container management with proper file mounting
- **Auto-patching**: Modifies `run.py` for dynamic streamer loading

## Usage
1. **Setup Twitch-Channel-Points-Miner**: Clone [Twitch-Channel-Points-Miner-v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2) and verify it works
2. **Get gibdrop**: Download `gibdrop.py` and `gibdrop_dockermgr.py` (for Docker) into your miner directory
3. **Run**: `python3 gibdrop.py`
4. **Browse Campaigns**: Use menu option 4 to see active drop campaigns and select streamers
5. **Start Mining**: Choose Docker (automated) or CLI mode (manual - exit gibdrop and run `python3 run.py`)

## Campaign Browser
- Automatically fetches Rust drops as campaign #1
- Shows real Twitch campaigns you can join
- Displays accurate streamer counts and drop information
- Supports multiple campaign selection: `1,2,3` or `1 2 3`
- Manual editing: Add custom streamers to `selected_campaigns.txt`
- Use `default_streamers.txt` to farm your favorite streamers when not running campaigns

## Notes
- Requires Twitch-Channel-Points-Miner cookies for real campaign detection
- Creates virtual environment automatically if needed
- All streamers use global settings (per-streamer settings not supported)
- For drop priority: comment out `PRIORITY.STREAKS` in your `run.py`
