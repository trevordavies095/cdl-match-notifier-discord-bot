"""Test script for Discord notifications"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta

from .config import Config
from .storage.database import Database
from .storage.models import Match
from .services.discord_client import DiscordClient
from .services.ics_parser import ICSParser
from .utils.logger import setup_logger
from .utils.timezone import now_utc

logger = setup_logger(__name__)


def create_test_match(
    team1: str,
    team2: str,
    start_time: datetime,
    source: str = "test"
) -> Match:
    """
    Create a test match object
    
    Args:
        team1: First team name
        team2: Second team name
        start_time: Match start time (UTC)
        source: Match source identifier
    
    Returns:
        Match object
    """
    # Use ICSParser to generate a valid match ID
    parser = ICSParser("")
    match_id = parser._generate_match_id(team1, team2, start_time)
    
    return Match(
        id=match_id,
        home_team=team1,
        away_team=team2,
        start_time_utc=start_time,
        source=source,
        created_at=now_utc(),
        url=None,
        description="Test match for notification testing"
    )


async def test_immediate_notification(
    team1: str,
    team2: str,
    config: Config
):
    """
    Test immediate notification by sending directly to Discord
    
    Args:
        team1: First team name
        team2: Second team name
        config: Configuration object
    """
    logger.info("Testing immediate notification mode...")
    
    # Create test match with start time 1 minute from now
    start_time = now_utc() + timedelta(minutes=1)
    match = create_test_match(team1, team2, start_time)
    
    logger.info(
        f"Created test match: {match.home_team} vs {match.away_team} "
        f"(starts at {match.start_time_utc})"
    )
    
    # Initialize Discord client
    discord_client = DiscordClient(
        token=config.discord_bot_token,
        channel_id=config.discord_channel_id,
        mention_role_id=config.discord_mention_role_id,
        ping_everyone=config.discord_ping_everyone
    )
    
    # Start Discord client
    discord_task = asyncio.create_task(discord_client.start())
    
    # Wait for Discord to connect
    logger.info("Connecting to Discord...")
    await asyncio.sleep(3)
    
    try:
        # Send notification
        logger.info("Sending test notification...")
        success = await discord_client.send_notification(match)
        
        if success:
            logger.info("✓ Test notification sent successfully!")
        else:
            logger.error("✗ Failed to send test notification")
            sys.exit(1)
    finally:
        # Clean up
        await discord_client.close()
        discord_task.cancel()
        try:
            await discord_task
        except asyncio.CancelledError:
            pass


def test_scheduled_notification(
    team1: str,
    team2: str,
    minutes: int,
    config: Config
):
    """
    Test scheduled notification by creating a match in the database
    
    Args:
        team1: First team name
        team2: Second team name
        minutes: Minutes from now to set match start time
        config: Configuration object
    """
    logger.info(f"Testing scheduled notification mode (match starts in {minutes} minutes)...")
    
    # Create test match with start time N minutes from now
    start_time = now_utc() + timedelta(minutes=minutes)
    match = create_test_match(team1, team2, start_time)
    
    logger.info(
        f"Created test match: {match.home_team} vs {match.away_team} "
        f"(starts at {match.start_time_utc})"
    )
    
    # Store in database
    database = Database(db_path="data/bot.db")
    database.upsert_match(match)
    
    logger.info(f"✓ Test match stored in database (ID: {match.id})")
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Start the main bot: python -m src.main")
    logger.info(f"2. Wait for the notification service to pick up the match")
    logger.info(f"   (notification will be sent {config.notify_minutes_before} minutes before start time)")
    logger.info(f"3. Expected notification time: {start_time - timedelta(minutes=config.notify_minutes_before)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Test Discord notifications for CDL matches"
    )
    parser.add_argument(
        "--immediate",
        action="store_true",
        help="Send notification immediately (bypasses notification service timing)"
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=20,
        help="Minutes from now for match start time (scheduled mode, default: 20)"
    )
    parser.add_argument(
        "--team1",
        type=str,
        default="Test Team A",
        help="First team name (default: 'Test Team A')"
    )
    parser.add_argument(
        "--team2",
        type=str,
        default="Test Team B",
        help="Second team name (default: 'Test Team B')"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = Config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    if args.immediate:
        # Immediate mode: send notification right away
        asyncio.run(test_immediate_notification(args.team1, args.team2, config))
    else:
        # Scheduled mode: create match in database
        test_scheduled_notification(args.team1, args.team2, args.minutes, config)


if __name__ == "__main__":
    main()

