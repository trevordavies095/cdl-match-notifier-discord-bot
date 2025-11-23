# CDL Discord Bot

A Discord bot that automatically notifies you about upcoming Call of Duty League (CDL) matches.

## Features

- Automatic match notifications 15 minutes before start time
- Fetches schedules from CDL ICS feeds and official schedule page
- Filter matches by specific teams (optional)
- Persistent storage using SQLite
- Dockerized for easy deployment
- Automatic schedule updates

## Setup

### Prerequisites

- Python 3.11+ (for local development)
- Docker and Docker Compose (for containerized deployment)
- Discord Bot Token (see [Discord Developer Portal](https://discord.com/developers/applications))

### Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and configure:
   - `DISCORD_BOT_TOKEN`: Your Discord bot token
   - `DISCORD_CHANNEL_ID`: The channel ID where notifications will be sent
   - `TEAMS`: (Optional) Comma-separated team names to filter matches
   - Other settings as needed

### Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the bot:
   ```bash
   python -m src.main
   ```

### Docker Deployment

1. Build the Docker image:
   ```bash
   docker-compose build
   ```

2. Run the bot:
   ```bash
   docker-compose up -d
   ```

3. View logs:
   ```bash
   docker-compose logs -f
   ```

4. Stop the bot:
   ```bash
   docker-compose down
   ```

## Testing

The bot includes a test script for verifying Discord notifications work correctly.

### Immediate Test Notification

Send a test notification immediately (bypasses timing):
```bash
python -m src.test_notification --immediate
```

### Scheduled Test Notification

Create a test match in the database that will trigger a notification:
```bash
python -m src.test_notification --minutes 20
```

This creates a test match starting in 20 minutes (default). The notification service will pick it up and send it at the configured time.

### Custom Team Names

You can customize the team names in test notifications:
```bash
python -m src.test_notification --minutes 15 --team1 "Team A" --team2 "Team B"
```

**Note:** The test script requires the same `.env` configuration as the main bot (`DISCORD_BOT_TOKEN` and `DISCORD_CHANNEL_ID`).

## Configuration Options

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | - | Discord bot token |
| `DISCORD_CHANNEL_ID` | Yes | - | Channel ID for notifications |
| `TEAMS` | No | - | Comma-separated team names (empty = all matches) |
| `NOTIFY_MINUTES_BEFORE` | No | 15 | Minutes before match to send notification |
| `SCHEDULE_FETCH_INTERVAL` | No | 60 | Minutes between schedule fetches |
| `DISCORD_MENTION_ROLE_ID` | No | - | Role ID to mention in notifications |
| `DISCORD_PING_EVERYONE` | No | false | Whether to ping @everyone |
| `TEAM_IDS` | No | - | Comma-separated team IDs for ICS feeds |
| `TEAM_ICS_FILE` | No | `ical_links.txt` | Path to file containing team names and ICS URLs |
| `ICS_BASE_URL` | No | (CDL S3 URL) | Base URL for ICS feeds |

## Configuring Team ICS Feeds

The bot needs team IDs to fetch match schedules from ICS feeds. You can configure this in two ways:

### Option 1: Using a File (Recommended)

Create a file named `ical_links.txt` (or set `TEAM_ICS_FILE` to a custom path) with the following format:

```
Team Name: webcal://cdl-public-archive.s3.us-east-2.amazonaws.com/CDL-calendar-sync/2026/team_id.ics
Another Team: https://cdl-public-archive.s3.us-east-2.amazonaws.com/CDL-calendar-sync/2026/team_id.ics
```

Example:
```
Texas OpTic: webcal://cdl-public-archive.s3.us-east-2.amazonaws.com/CDL-calendar-sync/2026/blt19237b20a0dd1b07.ics
Vegas FaZe: webcal://cdl-public-archive.s3.us-east-2.amazonaws.com/CDL-calendar-sync/2026/bltd84beef53d2aa9db.ics
```

**Why use a file?** Teams rebrand frequently, and maintaining a file makes it easy to update team names without changing environment variables. The bot will automatically extract team IDs from the URLs.

### Option 2: Using Environment Variable

Set the `TEAM_IDS` environment variable with comma-separated team IDs:

```bash
TEAM_IDS=blt19237b20a0dd1b07,bltd84beef53d2aa9db
```

### Finding Team ICS Feed URLs

CDL teams have individual ICS calendar feeds. The URL pattern is:
```
https://cdl-public-archive.s3.us-east-2.amazonaws.com/CDL-calendar-sync/2026/{team_id}.ics
```

To find a team's ICS feed:
1. Check the official CDL website for team calendar links
2. Look for `.ics` or calendar subscription links
3. The team ID is typically in the URL (e.g., `blt19237b20a0dd1b07`)

**Note:** Both methods can be used together - team IDs from the file and environment variable will be merged (duplicates are automatically removed).

## Troubleshooting

### Bot doesn't send notifications

- Check that the bot has permission to send messages in the configured channel
- Verify the channel ID is correct (right-click channel → Copy ID)
- Check logs for errors

### No matches found

- **Check team ID configuration**: Ensure you have configured team IDs either via `ical_links.txt` file or `TEAM_IDS` environment variable
- Verify ICS feed URLs are accessible
- Check that team names in `TEAMS` match the actual team names in schedules
- Ensure the schedule page is accessible
- Check bot logs for specific error messages about missing team IDs

### Database errors

- Ensure the `data/` directory is writable
- Check disk space
- Try deleting `data/bot.db` to reset (will lose notification history)

## Project Structure

```
cdl-discord-bot/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration
│   ├── services/            # Service modules
│   ├── storage/             # Database layer
│   └── utils/               # Utilities
├── data/                    # Persistent storage
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## License

MIT

