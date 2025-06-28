<p align="center">
  <img src="https://i.imgur.com/uykQBYE.png" alt="gibdrop CLI logo" width="400"/>
</p>

# gibdrop

**Version: 0.0.2**

> **This project is vibecoded. Which means it might work or not work.**

A helper utility for automating and patching the [Twitch-Channel-Points-Miner-v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2) streamer list.

## Features
- Automatically manages Python dependencies and environment:
  - Tries to install dependencies system-wide
  - If not possible, creates a local virtual environment (`.gibdrop_venv`) and runs itself inside it
- Interactive menu for:
  - Patching `run.py` only
  - Managing default and drop streamer lists
  - Switching active streamer lists
  - Starting the Twitch miner
- Automatic patching of `run.py` (or creation from `example.py` or GitHub if missing)
- Ensures all dependencies (`requests`, `beautifulsoup4`) are installed (if needed)

## Usage
1. **Clone the main miner project** ([Twitch-Channel-Points-Miner-v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2)) and place `gibdrop.py` in the same directory.
2. **Before using gibdrop, make sure the miner itself works!**
   - Test that you can run the miner and it starts up without errors.
   - Only proceed if the miner is working as expected.
3. **Just run:**
   ```bash
   python3 gibdrop.py
   ```
   - On first run, the script will try to install dependencies system-wide. If that fails (e.g. on managed Linux distros), it will create a local virtual environment (`.gibdrop_venv`), install dependencies there, and restart itself automatically.
   - You do NOT need to manually activate the virtual environment.
4. Use the menu to:
   - Patch `run.py`: This will import the necessary modules and add logic so the miner reads the streamer list from your managed files (`default_streamers.txt`, `drop_streamers.txt`, and `active_streamers.txt`) instead of a hardcoded list).
   - Manage streamer lists
   - Start the Twitch miner

## Requirements
- Python 3.7+
- The main miner project files (see above)

## Notes
- The script will automatically create the three .txt files it uses (`default_streamers.txt`, `drop_streamers.txt`, and `active_streamers.txt`) if they do not exist.
- `.gibdrop_venv` is created automatically if needed and can be safely deleted if you want to reset the environment.
- The drop streamer patcher is only for Rust Twitch drops.
- For full miner functionality, see the [main project](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2).
