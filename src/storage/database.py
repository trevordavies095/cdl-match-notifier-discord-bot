"""SQLite database operations"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from .models import Match, Notification


class Database:
    """SQLite database manager for matches and notifications"""
    
    def __init__(self, db_path: str = "data/bot.db"):
        """Initialize database connection"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Matches table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id TEXT PRIMARY KEY,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    start_time_utc TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    url TEXT,
                    description TEXT
                )
            """)
            
            # Notifications table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    match_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    notified_at TEXT NOT NULL,
                    PRIMARY KEY (match_id, channel_id)
                )
            """)
            
            # Indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_matches_start_time 
                ON matches(start_time_utc)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_match_id 
                ON notifications(match_id)
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def upsert_match(self, match: Match):
        """Insert or update a match"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO matches 
                (id, home_team, away_team, start_time_utc, source, created_at, url, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match.id,
                match.home_team,
                match.away_team,
                match.start_time_utc.isoformat(),
                match.source,
                match.created_at.isoformat(),
                match.url,
                match.description
            ))
            conn.commit()
    
    def get_match(self, match_id: str) -> Optional[Match]:
        """Get a match by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_match(row)
            return None
    
    def get_upcoming_matches(self, before_time: datetime) -> List[Match]:
        """Get all matches with start_time_utc <= before_time"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM matches 
                WHERE start_time_utc <= ?
                ORDER BY start_time_utc ASC
            """, (before_time.isoformat(),))
            return [self._row_to_match(row) for row in cursor.fetchall()]
    
    def get_matches_to_notify(
        self, 
        notification_time: datetime,
        channel_id: str
    ) -> List[Match]:
        """Get matches that should be notified but haven't been yet"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.* FROM matches m
                LEFT JOIN notifications n ON m.id = n.match_id AND n.channel_id = ?
                WHERE m.start_time_utc >= ? 
                AND n.match_id IS NULL
                ORDER BY m.start_time_utc ASC
            """, (channel_id, notification_time.isoformat()))
            return [self._row_to_match(row) for row in cursor.fetchall()]
    
    def mark_notified(self, match_id: str, channel_id: str):
        """Mark a match as notified for a channel"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO notifications 
                (match_id, channel_id, notified_at)
                VALUES (?, ?, ?)
            """, (match_id, channel_id, datetime.utcnow().isoformat()))
            conn.commit()
    
    def is_notified(self, match_id: str, channel_id: str) -> bool:
        """Check if a match has been notified for a channel"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM notifications 
                WHERE match_id = ? AND channel_id = ?
            """, (match_id, channel_id))
            return cursor.fetchone() is not None
    
    def prune_old_data(self, days: int = 30):
        """Remove matches and notifications older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete old matches
            cursor.execute("""
                DELETE FROM matches 
                WHERE start_time_utc < ?
            """, (cutoff.isoformat(),))
            # Delete orphaned notifications
            cursor.execute("""
                DELETE FROM notifications 
                WHERE match_id NOT IN (SELECT id FROM matches)
            """)
            conn.commit()
    
    def _row_to_match(self, row: sqlite3.Row) -> Match:
        """Convert database row to Match object"""
        return Match(
            id=row['id'],
            home_team=row['home_team'],
            away_team=row['away_team'],
            start_time_utc=datetime.fromisoformat(row['start_time_utc']),
            source=row['source'],
            created_at=datetime.fromisoformat(row['created_at']),
            url=row['url'],
            description=row['description']
        )

