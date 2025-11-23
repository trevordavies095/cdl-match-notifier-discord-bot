"""Team ID loader from ICS links file"""
import re
from pathlib import Path
from typing import List

from .logger import setup_logger

logger = setup_logger(__name__)


def parse_ics_links_file(file_path: str) -> List[str]:
    """
    Parse ICS links file and extract team IDs
    
    Expected file format:
    Team Name: webcal://.../team_id.ics
    Team Name: https://.../team_id.ics
    
    Args:
        file_path: Path to the ICS links file
        
    Returns:
        List of team IDs extracted from URLs
    """
    team_ids = []
    file = Path(file_path)
    
    if not file.exists():
        logger.warning(f"ICS links file not found: {file_path}")
        return team_ids
    
    try:
        with open(file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Check if line has the expected format (Team Name: URL)
                if ':' not in line:
                    logger.warning(f"Line {line_num} in {file_path} doesn't contain ':' - skipping: {line}")
                    continue
                
                # Split on first colon to separate team name from URL
                parts = line.split(':', 1)
                if len(parts) != 2:
                    logger.warning(f"Line {line_num} in {file_path} has unexpected format - skipping: {line}")
                    continue
                
                url = parts[1].strip()
                
                # Extract team ID from URL
                team_id = _extract_team_id_from_url(url)
                if team_id:
                    team_ids.append(team_id)
                    logger.debug(f"Extracted team ID '{team_id}' from line {line_num}")
                else:
                    logger.warning(f"Could not extract team ID from URL on line {line_num}: {url}")
        
        logger.info(f"Parsed {len(team_ids)} team ID(s) from {file_path}")
        return team_ids
    
    except Exception as e:
        logger.error(f"Error reading ICS links file {file_path}: {e}")
        return team_ids


def _extract_team_id_from_url(url: str) -> str:
    """
    Extract team ID from ICS URL
    
    Handles both webcal:// and https:// protocols.
    Extracts the part before .ics from URLs like:
    - webcal://.../team_id.ics
    - https://.../team_id.ics
    
    Args:
        url: ICS URL string
        
    Returns:
        Team ID string, or empty string if extraction fails
    """
    # Normalize webcal:// to https:// for easier parsing
    normalized_url = url.replace("webcal://", "https://", 1)
    
    # Pattern to match team ID before .ics
    # Matches: .../team_id.ics or .../team_id.ics?params
    pattern = r'/([^/]+)\.ics'
    match = re.search(pattern, normalized_url)
    
    if match:
        return match.group(1)
    
    return ""

