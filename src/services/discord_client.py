"""Discord bot client for sending notifications"""
import asyncio
from datetime import datetime
from typing import Optional
import discord
from discord.ext import commands

from ..storage.models import Match
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class DiscordClient:
    """Discord bot client for notifications"""
    
    def __init__(
        self,
        token: str,
        channel_id: str,
        mention_role_id: Optional[str] = None,
        ping_everyone: bool = False
    ):
        """
        Initialize Discord client
        
        Args:
            token: Discord bot token
            channel_id: Channel ID to send notifications to
            mention_role_id: Optional role ID to mention
            ping_everyone: Whether to ping @everyone
        """
        self.token = token
        self.channel_id = int(channel_id)
        self.mention_role_id = int(mention_role_id) if mention_role_id else None
        self.ping_everyone = ping_everyone
        
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        
        self._setup_events()
    
    def _setup_events(self):
        """Set up Discord bot events"""
        @self.bot.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.bot.user}")
            logger.info(f"Bot is ready, monitoring channel {self.channel_id}")
    
    async def start(self):
        """Start the Discord bot"""
        await self.bot.start(self.token)
    
    async def close(self):
        """Close the Discord bot connection"""
        await self.bot.close()
    
    async def send_notification(self, match: Match) -> bool:
        """
        Send a notification for a match
        
        Args:
            match: Match to notify about
        
        Returns:
            True if notification was sent successfully
        """
        try:
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                logger.error(f"Channel {self.channel_id} not found")
                return False
            
            message = self._format_message(match)
            await channel.send(message)
            
            logger.info(
                f"Sent notification for {match.home_team} vs {match.away_team} "
                f"to channel {self.channel_id}"
            )
            return True
        
        except discord.errors.HTTPException as e:
            logger.error(f"Discord API error sending notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
    
    def _format_message(self, match: Match) -> str:
        """
        Format notification message
        
        Args:
            match: Match object
        
        Returns:
            Formatted message string
        """
        # Convert datetime to Unix timestamp for Discord timestamps
        timestamp = int(match.start_time_utc.timestamp())
        
        # Build message
        lines = [
            "🔔 **CDL Match Starting Soon!**",
            f"{match.home_team} vs {match.away_team}",
            f"Start time: <t:{timestamp}:F> (<t:{timestamp}:R>)"
        ]
        
        # Add URL if available
        if match.url:
            lines.append(f"More info: {match.url}")
        
        message = "\n".join(lines)
        
        # Add mentions
        mentions = []
        if self.ping_everyone:
            mentions.append("@everyone")
        if self.mention_role_id:
            mentions.append(f"<@&{self.mention_role_id}>")
        
        if mentions:
            message = " ".join(mentions) + "\n" + message
        
        return message
    
    async def send_with_retry(self, match: Match, max_retries: int = 3) -> bool:
        """
        Send notification with exponential backoff retry
        
        Args:
            match: Match to notify about
            max_retries: Maximum number of retry attempts
        
        Returns:
            True if notification was sent successfully
        """
        for attempt in range(max_retries):
            success = await self.send_notification(match)
            if success:
                return True
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info(f"Retrying notification in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
        
        logger.error(f"Failed to send notification after {max_retries} attempts")
        return False

