"""Timezone conversion utilities"""
from datetime import datetime
from typing import Optional
import pytz


def to_utc(dt: datetime, tz: Optional[str] = None) -> datetime:
    """
    Convert a datetime to UTC.
    
    Args:
        dt: Datetime object (naive or timezone-aware)
        tz: Optional timezone string (e.g., 'America/New_York')
            If provided and dt is naive, dt is assumed to be in that timezone
    
    Returns:
        Datetime object in UTC
    """
    if dt.tzinfo is None:
        if tz:
            # Naive datetime, assume it's in the specified timezone
            tz_obj = pytz.timezone(tz)
            dt = tz_obj.localize(dt)
        else:
            # Naive datetime, assume UTC
            dt = pytz.UTC.localize(dt)
    
    return dt.astimezone(pytz.UTC).replace(tzinfo=None)


def now_utc() -> datetime:
    """Get current UTC time as naive datetime"""
    return datetime.utcnow()

