"""Notification service for scheduling and sending match notifications"""
import asyncio
from datetime import datetime, timedelta
from typing import List

from ..storage.database import Database
from ..storage.models import Match
from ..services.discord_client import DiscordClient
from ..utils.logger import setup_logger
from ..utils.timezone import now_utc

logger = setup_logger(__name__)


class NotificationService:
    """Service for managing match notifications"""
    
    def __init__(
        self,
        database: Database,
        discord_client: DiscordClient,
        notify_minutes_before: int = 15,
        check_interval: int = 30
    ):
        """
        Initialize notification service
        
        Args:
            database: Database instance
            discord_client: Discord client instance
            notify_minutes_before: Minutes before match to send notification
            check_interval: Seconds between notification checks
        """
        self.database = database
        self.discord_client = discord_client
        self.notify_minutes_before = notify_minutes_before
        self.check_interval = check_interval
        self.running = False
    
    async def start(self):
        """Start the notification checking loop"""
        self.running = True
        logger.info(f"Starting notification service (check every {self.check_interval}s)")
        
        while self.running:
            try:
                await self._check_and_notify()
            except Exception as e:
                logger.error(f"Error in notification loop: {e}")
            
            await asyncio.sleep(self.check_interval)
    
    def stop(self):
        """Stop the notification checking loop"""
        self.running = False
        logger.info("Stopping notification service")
    
    async def _check_and_notify(self):
        """Check for matches that need notification and send them"""
        now = now_utc()
        
        # Calculate notification time window
        # We want to notify when: now >= (start_time - notify_minutes_before)
        # So: start_time >= (now + notify_minutes_before)
        notification_deadline = now + timedelta(minutes=self.notify_minutes_before)
        
        # Get matches that should be notified
        # Matches where start_time - notify_minutes_before <= now < start_time
        # This means: start_time >= now + notify_minutes_before AND start_time > now
        matches_to_notify = self._get_matches_to_notify(now, notification_deadline)
        
        if not matches_to_notify:
            return
        
        logger.info(f"Found {len(matches_to_notify)} matches to notify")
        
        for match in matches_to_notify:
            # Double-check we're in the notification window
            notification_time = match.start_time_utc - timedelta(minutes=self.notify_minutes_before)
            
            if now >= notification_time and now < match.start_time_utc:
                # Check if already notified
                if not self.database.is_notified(match.id, self.discord_client.channel_id):
                    success = await self.discord_client.send_with_retry(match)
                    if success:
                        self.database.mark_notified(match.id, self.discord_client.channel_id)
                        logger.info(
                            f"Notified about match: {match.home_team} vs {match.away_team} "
                            f"(starts at {match.start_time_utc})"
                        )
    
    def _get_matches_to_notify(self, now: datetime, deadline: datetime) -> List[Match]:
        """
        Get matches that should be notified
        
        Args:
            now: Current time
            deadline: Latest start time for matches to notify about
        
        Returns:
            List of matches that need notification
        """
        # Get all matches that start between now and deadline
        all_upcoming = self.database.get_upcoming_matches(deadline)
        
        # Filter to matches that haven't been notified yet
        matches_to_notify = []
        for match in all_upcoming:
            # Only notify if we're past the notification time but before match start
            notification_time = match.start_time_utc - timedelta(minutes=self.notify_minutes_before)
            
            if (now >= notification_time and 
                now < match.start_time_utc and
                not self.database.is_notified(match.id, self.discord_client.channel_id)):
                matches_to_notify.append(match)
        
        return matches_to_notify

