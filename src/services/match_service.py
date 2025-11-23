"""Match service for normalization, deduplication, and filtering"""
from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple
from difflib import SequenceMatcher

from ..storage.models import Match
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class MatchService:
    """Service for match normalization and processing"""
    
    def __init__(self, teams_filter: Optional[List[str]] = None):
        """
        Initialize match service
        
        Args:
            teams_filter: Optional list of team names to filter by
        """
        self.teams_filter = teams_filter
        if teams_filter:
            # Normalize team names for filtering
            self.teams_filter_normalized = [
                self._normalize_team_name(team) for team in teams_filter
            ]
        else:
            self.teams_filter_normalized = None
    
    def normalize_matches(self, matches: List[Match]) -> List[Match]:
        """
        Normalize and deduplicate matches
        
        Args:
            matches: List of matches from various sources
        
        Returns:
            Normalized and deduplicated list of matches
        """
        # Normalize team names
        normalized = [self._normalize_match(match) for match in matches]
        
        # Deduplicate
        deduplicated = self._deduplicate_matches(normalized)
        
        # Filter by teams if configured
        if self.teams_filter_normalized:
            filtered = self._filter_by_teams(deduplicated)
        else:
            filtered = deduplicated
        
        logger.info(f"Normalized {len(matches)} matches to {len(filtered)} unique matches")
        return filtered
    
    def _normalize_match(self, match: Match) -> Match:
        """Normalize a single match (team names, times)"""
        return Match(
            id=match.id,
            home_team=self._normalize_team_name(match.home_team),
            away_team=self._normalize_team_name(match.away_team),
            start_time_utc=match.start_time_utc,
            source=match.source,
            created_at=match.created_at,
            url=match.url,
            description=match.description
        )
    
    def _normalize_team_name(self, team_name: str) -> str:
        """
        Normalize team name for consistent matching
        
        Args:
            team_name: Raw team name
        
        Returns:
            Normalized team name
        """
        # Remove extra whitespace
        normalized = ' '.join(team_name.split())
        
        # Common team name variations
        # This could be expanded with a mapping if needed
        return normalized
    
    def _deduplicate_matches(self, matches: List[Match]) -> List[Match]:
        """
        Deduplicate matches from different sources
        
        Matches are considered duplicates if:
        - Same teams (order doesn't matter)
        - Start time within 1 hour of each other
        
        Args:
            matches: List of matches
        
        Returns:
            Deduplicated list (keeps the most recent source)
        """
        seen: Set[str] = set()
        unique_matches = []
        
        # Sort by created_at (most recent first) to prefer newer data
        sorted_matches = sorted(matches, key=lambda m: m.created_at, reverse=True)
        
        for match in sorted_matches:
            # Generate deduplication key
            key = self._get_dedup_key(match)
            
            if key not in seen:
                seen.add(key)
                unique_matches.append(match)
            else:
                logger.debug(f"Deduplicated match: {match.home_team} vs {match.away_team}")
        
        return unique_matches
    
    def _get_dedup_key(self, match: Match) -> str:
        """
        Generate deduplication key for a match
        
        Args:
            match: Match object
        
        Returns:
            Deduplication key string
        """
        # Normalize team names (alphabetical order)
        teams = tuple(sorted([
            match.home_team.lower(),
            match.away_team.lower()
        ]))
        
        # Round start time to nearest hour for deduplication window
        hour_rounded = match.start_time_utc.replace(minute=0, second=0, microsecond=0)
        
        return f"{teams[0]}|{teams[1]}|{hour_rounded.isoformat()}"
    
    def _filter_by_teams(self, matches: List[Match]) -> List[Match]:
        """
        Filter matches to only include those with configured teams
        
        Args:
            matches: List of matches
        
        Returns:
            Filtered list of matches
        """
        filtered = []
        
        for match in matches:
            home_normalized = self._normalize_team_name(match.home_team).lower()
            away_normalized = self._normalize_team_name(match.away_team).lower()
            
            # Check if either team matches any filter
            for filter_team in self.teams_filter_normalized:
                filter_lower = filter_team.lower()
                
                # Exact match or partial match
                if (filter_lower in home_normalized or 
                    filter_lower in away_normalized or
                    self._team_name_similar(home_normalized, filter_lower) or
                    self._team_name_similar(away_normalized, filter_lower)):
                    filtered.append(match)
                    break
        
        logger.info(f"Filtered to {len(filtered)} matches for configured teams")
        return filtered
    
    def _team_name_similar(self, name1: str, name2: str, threshold: float = 0.8) -> bool:
        """
        Check if two team names are similar using sequence matching
        
        Args:
            name1: First team name
            name2: Second team name
            threshold: Similarity threshold (0-1)
        
        Returns:
            True if names are similar enough
        """
        ratio = SequenceMatcher(None, name1, name2).ratio()
        return ratio >= threshold
    
    def update_match_time(self, match: Match, new_start_time: datetime) -> Match:
        """
        Update match start time (for handling time changes)
        
        Args:
            match: Existing match
            new_start_time: New start time
        
        Returns:
            Updated match with new ID
        """
        # Generate new ID with updated time
        from ..services.ics_parser import ICSParser
        parser = ICSParser("")
        new_id = parser._generate_match_id(match.home_team, match.away_team, new_start_time)
        
        return Match(
            id=new_id,
            home_team=match.home_team,
            away_team=match.away_team,
            start_time_utc=new_start_time,
            source=match.source,
            created_at=datetime.utcnow(),
            url=match.url,
            description=match.description
        )

