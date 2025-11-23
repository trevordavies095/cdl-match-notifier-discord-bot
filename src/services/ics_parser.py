"""ICS feed parser for CDL team schedules"""
import hashlib
import re
from datetime import datetime
from typing import List, Optional, Tuple
import requests
from icalendar import Calendar

from ..storage.models import Match
from ..utils.logger import setup_logger
from ..utils.timezone import to_utc

logger = setup_logger(__name__)


class ICSParser:
    """Parser for ICS calendar feeds"""
    
    def __init__(self, base_url: str):
        """
        Initialize ICS parser
        
        Args:
            base_url: Base URL for CDL ICS feeds
        """
        self.base_url = base_url.rstrip('/')
    
    def fetch_ics(self, team_id: str) -> Optional[str]:
        """
        Fetch ICS feed for a team
        
        Args:
            team_id: Team identifier (e.g., 'blt19237b20a0dd1b07')
        
        Returns:
            ICS content as string, or None if fetch failed
        """
        url = f"{self.base_url}/{team_id}.ics"
        
        # Convert webcal:// to https://
        if url.startswith("webcal://"):
            url = url.replace("webcal://", "https://", 1)
        
        try:
            logger.debug(f"Fetching ICS feed: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch ICS feed {url}: {e}")
            return None
    
    def parse_ics(self, ics_content: str, source: str = "ics") -> List[Match]:
        """
        Parse ICS content and extract matches
        
        Args:
            ics_content: ICS file content as string
            source: Source identifier for matches
        
        Returns:
            List of Match objects
        """
        matches = []
        
        try:
            calendar = Calendar.from_ical(ics_content)
            
            for component in calendar.walk('VEVENT'):
                match = self._parse_event(component, source)
                if match:
                    matches.append(match)
            
            logger.info(f"Parsed {len(matches)} matches from ICS feed")
            return matches
        
        except Exception as e:
            logger.error(f"Failed to parse ICS content: {e}")
            return []
    
    def _parse_event(self, event, source: str) -> Optional[Match]:
        """
        Parse a single VEVENT into a Match object
        
        Args:
            event: icalendar VEVENT component
            source: Source identifier
        
        Returns:
            Match object or None if parsing fails
        """
        try:
            # Extract start time
            dtstart = event.get('DTSTART')
            if not dtstart:
                return None
            
            # Convert to datetime
            if isinstance(dtstart.dt, datetime):
                start_time = dtstart.dt
            else:
                # Handle date-only (all-day events)
                start_time = datetime.combine(dtstart.dt, datetime.min.time())
            
            # Convert to UTC
            start_time_utc = to_utc(start_time)
            
            # Extract summary (team names)
            summary = str(event.get('SUMMARY', ''))
            home_team, away_team = self._parse_teams_from_summary(summary)
            
            if not home_team or not away_team:
                logger.warning(f"Could not parse teams from summary: {summary}")
                return None
            
            # Extract optional fields
            url = str(event.get('URL', '')) if event.get('URL') else None
            description = str(event.get('DESCRIPTION', '')) if event.get('DESCRIPTION') else None
            
            # Generate match ID
            match_id = self._generate_match_id(home_team, away_team, start_time_utc)
            
            return Match(
                id=match_id,
                home_team=home_team,
                away_team=away_team,
                start_time_utc=start_time_utc,
                source=source,
                created_at=datetime.utcnow(),
                url=url,
                description=description
            )
        
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None
    
    def _parse_teams_from_summary(self, summary: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse team names from ICS SUMMARY field
        
        Common formats:
        - "Team A vs Team B"
        - "Team A v Team B"
        - "Team A @ Team B"
        
        Args:
            summary: SUMMARY field content
        
        Returns:
            Tuple of (home_team, away_team) or (None, None) if parsing fails
        """
        # Common separators
        separators = [' vs ', ' v ', ' @ ', ' VS ', ' V ', ' @ ']
        
        for sep in separators:
            if sep in summary:
                parts = summary.split(sep, 1)
                if len(parts) == 2:
                    home = parts[0].strip()
                    away = parts[1].strip()
                    # Remove common prefixes/suffixes
                    home = re.sub(r'^vs\s+', '', home, flags=re.IGNORECASE).strip()
                    away = re.sub(r'^vs\s+', '', away, flags=re.IGNORECASE).strip()
                    return home, away
        
        # Try to find "vs" or "v" anywhere
        match = re.search(r'(.+?)\s+(?:vs|v|@)\s+(.+)', summary, re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        
        return None, None
    
    def _generate_match_id(self, home_team: str, away_team: str, start_time: datetime) -> str:
        """
        Generate a unique match ID
        
        Args:
            home_team: Home team name
            away_team: Away team name
            start_time: Match start time
        
        Returns:
            Unique match ID string
        """
        # Normalize team names for ID generation
        normalized_home = home_team.lower().strip()
        normalized_away = away_team.lower().strip()
        
        # Use alphabetical order for consistent IDs regardless of home/away
        team_pair = tuple(sorted([normalized_home, normalized_away]))
        
        # Include date (not time) for uniqueness
        date_str = start_time.strftime("%Y-%m-%d")
        
        # Generate hash
        content = f"{team_pair[0]}|{team_pair[1]}|{date_str}"
        match_id = hashlib.md5(content.encode()).hexdigest()[:16]
        
        return f"match_{match_id}"

