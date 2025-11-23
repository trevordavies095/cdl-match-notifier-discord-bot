"""Configuration loading and validation"""
import os
from typing import List, Optional
from dotenv import load_dotenv

from .utils.logger import setup_logger
from .utils.team_loader import parse_ics_links_file

logger = setup_logger(__name__)

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration"""
    
    def __init__(self):
        """Load and validate configuration"""
        # Discord configuration
        self.discord_bot_token = self._get_required("DISCORD_BOT_TOKEN")
        self.discord_channel_id = self._get_required("DISCORD_CHANNEL_ID")
        self.discord_mention_role_id = os.getenv("DISCORD_MENTION_ROLE_ID")
        self.discord_mention_role_name = os.getenv("DISCORD_MENTION_ROLE_NAME")
        self.discord_ping_everyone = os.getenv("DISCORD_PING_EVERYONE", "false").lower() == "true"
        
        # Role ID takes precedence over role name if both are provided
        if self.discord_mention_role_id and self.discord_mention_role_name:
            logger.info(
                f"Both DISCORD_MENTION_ROLE_ID and DISCORD_MENTION_ROLE_NAME are set. "
                f"Using role ID (takes precedence)."
            )
        
        # Team filtering
        teams_str = os.getenv("TEAMS", "")
        self.teams: Optional[List[str]] = None
        if teams_str.strip():
            self.teams = [team.strip() for team in teams_str.split(",") if team.strip()]
        
        # Notification settings
        self.notify_minutes_before = int(os.getenv("NOTIFY_MINUTES_BEFORE", "15"))
        self.schedule_fetch_interval = int(os.getenv("SCHEDULE_FETCH_INTERVAL", "60"))
        
        # ICS feed configuration
        self.ics_base_url = os.getenv(
            "ICS_BASE_URL",
            "https://cdl-public-archive.s3.us-east-2.amazonaws.com/CDL-calendar-sync/2026"
        )
        
        # Team IDs for ICS feeds - can come from file or env var
        self.team_ids: Optional[List[str]] = None
        
        # Try loading from file first (configurable via TEAM_ICS_FILE)
        team_ics_file = os.getenv("TEAM_ICS_FILE", "ical_links.txt")
        file_team_ids = parse_ics_links_file(team_ics_file)
        
        # Also check for TEAM_IDS environment variable
        team_ids_str = os.getenv("TEAM_IDS", "")
        env_team_ids: List[str] = []
        if team_ids_str.strip():
            env_team_ids = [tid.strip() for tid in team_ids_str.split(",") if tid.strip()]
        
        # Merge file and env var team IDs (file takes precedence, but merge unique IDs)
        all_team_ids = list(file_team_ids)
        for tid in env_team_ids:
            if tid not in all_team_ids:
                all_team_ids.append(tid)
        
        if all_team_ids:
            self.team_ids = all_team_ids
            if file_team_ids:
                logger.info(f"Loaded {len(file_team_ids)} team ID(s) from {team_ics_file}")
            if env_team_ids:
                logger.info(f"Loaded {len(env_team_ids)} team ID(s) from TEAM_IDS environment variable")
            if file_team_ids and env_team_ids:
                logger.info(f"Total unique team IDs: {len(self.team_ids)}")
        
        self._validate()
        logger.info("Configuration loaded successfully")
    
    def _get_required(self, key: str) -> str:
        """Get required environment variable"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return value
    
    def _validate(self):
        """Validate configuration values"""
        if self.notify_minutes_before < 0:
            raise ValueError("NOTIFY_MINUTES_BEFORE must be non-negative")
        
        if self.schedule_fetch_interval < 1:
            raise ValueError("SCHEDULE_FETCH_INTERVAL must be at least 1 minute")
        
        # Validate Discord channel ID is numeric
        try:
            int(self.discord_channel_id)
        except ValueError:
            raise ValueError("DISCORD_CHANNEL_ID must be a numeric channel ID")
        
        logger.info(f"Notification lead time: {self.notify_minutes_before} minutes")
        logger.info(f"Schedule fetch interval: {self.schedule_fetch_interval} minutes")
        if self.teams:
            logger.info(f"Team filter: {', '.join(self.teams)}")
        else:
            logger.info("Team filter: All matches")

