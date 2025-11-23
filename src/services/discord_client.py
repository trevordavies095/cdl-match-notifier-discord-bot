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
        mention_role_name: Optional[str] = None,
        ping_everyone: bool = False
    ):
        """
        Initialize Discord client
        
        Args:
            token: Discord bot token
            channel_id: Channel ID to send notifications to
            mention_role_id: Optional role ID to mention (takes precedence over role_name)
            mention_role_name: Optional role name to mention (looked up after bot connects)
            ping_everyone: Whether to ping @everyone
        """
        self.token = token
        self.channel_id = int(channel_id)
        self.mention_role_id = int(mention_role_id) if mention_role_id else None
        self.mention_role_name = mention_role_name
        self.ping_everyone = ping_everyone
        
        intents = discord.Intents.default()
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        
        self._setup_events()
    
    def _setup_events(self):
        """Set up Discord bot events"""
        @self.bot.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.bot.user}")
            logger.info(f"Bot is ready, monitoring channel {self.channel_id}")
            
            # Resolve role name to ID if provided and role_id not already set
            if self.mention_role_name and not self.mention_role_id:
                await self._resolve_role_name()
    
    async def start(self):
        """Start the Discord bot"""
        await self.bot.start(self.token)
    
    async def close(self):
        """Close the Discord bot connection"""
        await self.bot.close()
    
    async def _resolve_role_name(self):
        """
        Resolve role name to role ID by searching in the guild
        
        This is called after the bot connects to Discord.
        """
        try:
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                logger.warning(
                    f"Cannot resolve role name '{self.mention_role_name}': "
                    f"Channel {self.channel_id} not found"
                )
                return
            
            guild = channel.guild
            if not guild:
                logger.warning(
                    f"Cannot resolve role name '{self.mention_role_name}': "
                    f"Guild not found for channel {self.channel_id}"
                )
                return
            
            # Search for role by name (case-insensitive)
            role = discord.utils.get(guild.roles, name=self.mention_role_name)
            
            if role:
                self.mention_role_id = role.id
                logger.info(
                    f"Resolved role name '{self.mention_role_name}' to role ID {role.id}"
                )
            else:
                logger.warning(
                    f"Role '{self.mention_role_name}' not found in server '{guild.name}'. "
                    f"Please check that the role exists and the name is spelled correctly. "
                    f"The bot will continue without role mentions."
                )
        except Exception as e:
            logger.error(f"Error resolving role name '{self.mention_role_name}': {e}")
    
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
                logger.error("Make sure the bot is in the server and the channel ID is correct")
                return False
            
            # Check if bot has permission to send messages
            if not channel.permissions_for(channel.guild.me).send_messages:
                logger.error(f"Bot lacks permission to send messages in channel {self.channel_id}")
                logger.error("Please ensure the bot has 'Send Messages' permission in this channel")
                return False
            
            message = self._format_message(match)
            await channel.send(message)
            
            logger.info(
                f"Sent notification for {match.home_team} vs {match.away_team} "
                f"to channel {self.channel_id}"
            )
            return True
        
        except discord.errors.Forbidden as e:
            logger.error(f"Permission denied: {e}")
            logger.error("The bot needs 'Send Messages' permission in the channel.")
            logger.error("Check the channel permissions and ensure the bot role has access.")
            return False
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

