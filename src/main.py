"""Main entry point for CDL Discord Bot"""
import asyncio
import signal
import sys
from pathlib import Path

from .config import Config
from .storage.database import Database
from .services.ics_parser import ICSParser
from .services.schedule_fetcher import ScheduleFetcher
from .services.match_service import MatchService
from .services.discord_client import DiscordClient
from .services.notification_service import NotificationService
from .utils.logger import setup_logger

logger = setup_logger(__name__)


class CDLBot:
    """Main bot orchestrator"""
    
    def __init__(self):
        """Initialize bot components"""
        self.config = Config()
        self.database = Database(db_path="data/bot.db")
        self.running = False
        
        # Initialize services
        self.ics_parser = ICSParser(self.config.ics_base_url)
        self.schedule_fetcher = ScheduleFetcher()
        self.match_service = MatchService(self.config.teams)
        self.discord_client = DiscordClient(
            token=self.config.discord_bot_token,
            channel_id=self.config.discord_channel_id,
            mention_role_id=self.config.discord_mention_role_id,
            ping_everyone=self.config.discord_ping_everyone
        )
        self.notification_service = NotificationService(
            database=self.database,
            discord_client=self.discord_client,
            notify_minutes_before=self.config.notify_minutes_before,
            check_interval=30
        )
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    async def start(self):
        """Start the bot"""
        self.running = True
        logger.info("Starting CDL Discord Bot...")
        
        # Prune old data on startup
        self.database.prune_old_data(days=30)
        
        # Start Discord client in background
        discord_task = asyncio.create_task(self.discord_client.start())
        
        # Wait a bit for Discord to connect
        await asyncio.sleep(2)
        
        # Start notification service
        notification_task = asyncio.create_task(self.notification_service.start())
        
        # Start schedule fetching loop
        schedule_task = asyncio.create_task(self._schedule_fetch_loop())
        
        try:
            # Run until stopped
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            # Stop services
            logger.info("Stopping services...")
            self.notification_service.stop()
            schedule_task.cancel()
            notification_task.cancel()
            
            # Close Discord client
            await self.discord_client.close()
            discord_task.cancel()
            
            logger.info("Bot stopped")
    
    async def _schedule_fetch_loop(self):
        """Background loop for fetching schedules"""
        logger.info("Starting schedule fetch loop...")
        
        # Fetch immediately on startup
        await self._fetch_and_process_schedules()
        
        # Then fetch on interval
        while self.running:
            try:
                await asyncio.sleep(self.config.schedule_fetch_interval * 60)
                if self.running:
                    await self._fetch_and_process_schedules()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in schedule fetch loop: {e}")
    
    async def _fetch_and_process_schedules(self):
        """Fetch schedules from all sources and process them"""
        logger.info("Fetching schedules...")
        all_matches = []
        
        # Fetch from ICS feeds
        # Note: For now, we'll need team IDs. This could be expanded
        # to discover all team feeds or use a mapping
        ics_matches = await self._fetch_ics_feeds()
        all_matches.extend(ics_matches)
        
        # Fetch from schedule page
        try:
            schedule_matches = self.schedule_fetcher.fetch_schedule()
            all_matches.extend(schedule_matches)
        except Exception as e:
            logger.error(f"Error fetching schedule page: {e}")
        
        # Process and store matches
        if all_matches:
            normalized = self.match_service.normalize_matches(all_matches)
            
            # Store in database
            for match in normalized:
                self.database.upsert_match(match)
            
            logger.info(f"Processed and stored {len(normalized)} matches")
        else:
            logger.warning("No matches found from any source")
            if not self.config.team_ids:
                logger.warning(
                    "This is likely because no team IDs are configured. "
                    "See previous messages for configuration instructions."
                )
        
        # Prune old data periodically
        self.database.prune_old_data(days=30)
    
    async def _fetch_ics_feeds(self) -> list:
        """Fetch matches from ICS feeds"""
        matches = []
        
        # Get team IDs from config
        team_ids = self.config.team_ids
        
        if not team_ids:
            logger.debug("No team IDs configured, skipping ICS feed fetch")
            logger.warning(
                "No team IDs found. To fetch ICS feeds, configure team IDs using one of:\n"
                "  1. Create 'ical_links.txt' file with format: 'Team Name: webcal://.../team_id.ics'\n"
                "  2. Set TEAM_IDS environment variable (comma-separated team IDs)\n"
                "  3. Set TEAM_ICS_FILE environment variable to point to your ICS links file"
            )
            return matches
        
        logger.info(f"Fetching ICS feeds for {len(team_ids)} team(s)")
        
        for team_id in team_ids:
            try:
                ics_content = self.ics_parser.fetch_ics(team_id)
                if ics_content:
                    parsed = self.ics_parser.parse_ics(ics_content, source="ics")
                    matches.extend(parsed)
                    logger.debug(f"Fetched {len(parsed)} matches from team {team_id}")
                else:
                    logger.warning(f"Failed to fetch ICS feed for team {team_id}")
            except Exception as e:
                logger.error(f"Error fetching ICS feed for team {team_id}: {e}")
        
        return matches


async def main():
    """Main entry point"""
    try:
        bot = CDLBot()
        await bot.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

