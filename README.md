<p align="center">
  <img src="https://i.imgur.com/bFkYrqb.png" alt="gibdrop CLI logo" width="400"/>
</p>

# gibdrop

**Version: 0.0.3**

> **This project is vibe coded. Which means it might work or not work.**

A helper utility for automating and patching the [Twitch-Channel-Points-Miner-v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2) streamer list.

## Purpose

The main intent of this script is to make farming Twitch drops for [Rust](https://store.steampowered.com/app/252490/Rust/) as easy as possible. It automatically fetches all available Rust drop streamers from the official [website](https://twitch.facepunch.com/), saves their usernames to a file, and allows you to load them and start the miner with minimal effort.

After you have collected all the Rust drops, you can easily switch back to your default streamers list and continue farming channel points or other drops as usual.

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
- **Docker workflow**: Build and run a patched Docker image directly from the gibdrop menu. The script ensures all required files and a suitable Dockerfile are present, and only rebuilds the image if needed.
- All Docker actions are fully automated from the gibdrop menu.

## Usage
1. **Clone the main miner project** ([Twitch-Channel-Points-Miner-v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2)) and make sure the miner itself works!
   - Only proceed if the miner is working as expected.
2. **Get the gibdrop files:**
   - You can either **clone this repo** ([ctrl-a-d/gibdrop](https://github.com/ctrl-a-d/gibdrop)) or download the files directly:
     - `gibdrop.py` (required)
     - `gibdrop_dockermgr.py` (only needed if you plan to use Docker)
   - Place the files in the same directory as your Twitch-Channel-Points-Miner-v2 project.
3. **Just run:**
   ```bash
   python3 gibdrop.py
   ```
   - On first run, the script will try to install dependencies system-wide. If that fails (e.g. on managed Linux distros), it will create a local virtual environment (`.gibdrop_venv`), install dependencies there, and restart itself automatically.
   - You do NOT need to manually activate the virtual environment.
4. **Use the menu to:**
   - Patch `run.py`: This will import the necessary modules and add logic so the miner reads the streamer list from your managed files (`default_streamers.txt`, `drop_streamers.txt`, and `active_streamers.txt`) instead of a hardcoded list.
   - Manage streamer lists
   - Start the Twitch miner
   - **To use Docker:** Simply select the Docker option in the gibdrop menu when you are ready to run the miner. The script will:
     - Ensure all required `.txt` files and the patched Dockerfile exist (creating them if missing)
     - Check if the Docker image needs to be rebuilt (only if the Dockerfile or dependencies changed)
     - Build the image and run the container with your local files mounted in
     - You never need to run any Docker commands or helper scripts manually

## Notes
- The script will automatically create the three .txt files it uses (`default_streamers.txt`, `drop_streamers.txt`, and `active_streamers.txt`) if they do not exist.
- `.gibdrop_venv` is created automatically if needed and can be safely deleted if you want to reset the environment.
- The drop streamer patcher is only for Rust Twitch drops.
- **Important Note**: Due to how the patched script loads streamers, per-streamer settings (like in `example.py`) are not supported. All streamers will use the global settings from your `run.py` configuration.
- **To prioritize drops over streaks:** Edit your `run.py` and comment out the `PRIORITY.STREAKS` line. This ensures the miner focuses on drop farming first.
