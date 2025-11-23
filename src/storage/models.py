"""Data models for matches and notifications"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Match:
    """Represents a CDL match"""
    id: str
    home_team: str
    away_team: str
    start_time_utc: datetime
    source: str  # 'ics' or 'schedule'
    created_at: datetime
    url: Optional[str] = None
    description: Optional[str] = None
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if not isinstance(other, Match):
            return False
        return self.id == other.id


@dataclass
class Notification:
    """Represents a sent notification"""
    match_id: str
    channel_id: str
    notified_at: datetime
    
    def __hash__(self):
        return hash((self.match_id, self.channel_id))
    
    def __eq__(self, other):
        if not isinstance(other, Notification):
            return False
        return (self.match_id == other.match_id and 
                self.channel_id == other.channel_id)

