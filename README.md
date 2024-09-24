# jfmusicbot

    Jellyfin music bot for Discord.

## Requirements

Requirements related to the Jellyfin server:

- A Jellyfin Server accessible by the bot through its HTTP API
- An API key to the Jellyfin server
- Transcoding audio to `opus` codec be properly setup on the Jellyfin server

Requirements related to the bot server:

- A valid install of `ffmpeg` added to PATH
- Python and Poetry
- An internet connection that does not block access to Discord Voice

## How to setup

You will need to show file extensions if you are on Windows.

1. Create a copy of `config.yml.example` and name it `config.yml`, confirm rename the extension if asked.
2. Create a Discord application and get a bot token and supply it in `config.yml`
3. Supply your Jellyfin server address in `config.yml`
4. Create a Jellyfin API key in the dashboard and supply it in `config.yml`
5. Open a terminal in the bot folder
6. run `poetry install` to install dependencies

## How to run

1. Open a terminal in the bot folder
2. run `poetry run python3 main.py` to start the bot. You may need to run `poetry run python main.py` if you are on Windows.
3. press `Ctrl+C` in the terminal window to exit the bot. MacOS uses the same key bind.

## Commands

This list will assume the default prefix of `jfmusic`. This can be changed in the config.

- `/jfmusic search <term> <type> <when>`
  Search for a list of items using `<term>`. Options for `<when>` term: `now` stops current track and plays the specified track. `next` places the specified track next in the queue. `last` is the default behavior, places the specified track at the end of the playlist.
- `/jfmusic play <term> <type> <when>`
  Parameters work the same as the above command, except it directly uses the first result returned from the server, instead of asking the user to choose from a list of options
- `/jfmusic skip`
  Skips the current playing track
- `/jfmusic nowplaying`
  Shows the current playing track
- `/jfmusic queue`
  Shows the current playlist
- `/jfmusic start`
  Starts the player and plays the playlist
- `/jfmusic pause`
  Pauses playback
- `/jfmusic resume`
  Resumes playback
- `/jfmusic stop`
  Stops playback and clears the playlist
- `/jfmusic shuffle`
  Shuffles the playlist
- `/jfmusic remove <index>`
  Removes the item at the specified index from the playlist. Index starts with 1.
- `/jfmusic promote <index>`
  Promotes the item at the specified index from the playlist to the front. Index starts with 1.
- `/jfmusic demote <index>`
  Demotes the item at the specified index from the playlist to the back. Index starts with one

## Known limitations / issues / missing features

Intend to fix:

- No queue management functions: play now
- No elapsed time in playback status
- No proper pagination in playlist

Framework Limitation:

- Stage channels might be broken

I don't need myself but you are welcome to send PRs:

- Login as Jellyfin user instead of using apikey
