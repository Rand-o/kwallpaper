#!/usr/bin/env python3
"""
Shuffle List Manager - Manages daily theme shuffling.

This module handles the creation, persistence, and iteration of shuffled theme lists.
"""

import json
import random
from pathlib import Path
from datetime import date
from typing import List, Tuple, Optional, Dict, Any

from kwallpaper.wallpaper_changer import DEFAULT_SHUFFLE_LIST_PATH


def create_initial_shuffle(themes: List[str]) -> List[str]:
    """Create an initial shuffled list from themes.
    
    Args:
        themes: List of theme paths to shuffle
        
    Returns:
        Shuffled list of theme paths
    """
    shuffled = themes.copy()
    random.shuffle(shuffled)
    return shuffled


def get_next_theme(shuffle_list: List[str], current_index: int) -> Tuple[str, int]:
    """Get the next theme from the shuffle list.
    
    Args:
        shuffle_list: Current shuffled list of themes
        current_index: Current position in the list
        
    Returns:
        Tuple of (theme_path, new_index)
    """
    if not shuffle_list:
        raise ValueError("Shuffle list is empty")
    
    if current_index >= len(shuffle_list):
        current_index = 0
    
    theme = shuffle_list[current_index]
    new_index = current_index + 1
    
    return theme, new_index


def check_and_reshuffle(
    shuffle_list: List[str],
    current_index: int,
    last_used_date: str,
    current_date: Optional[str] = None
) -> bool:
    """Check if reshuffle is needed.
    
    Reshuffle only happens when the list is exhausted (current_index >= len(shuffle_list)).
    Date changes do NOT trigger reshuffle - they just advance to the next theme.
    
    Args:
        shuffle_list: Current shuffled list
        current_index: Current position in list
        last_used_date: Date when list was last used (YYYY-MM-DD format)
        current_date: Optional current date for testing (YYYY-MM-DD format)
        
    Returns:
        True if reshuffle is needed (list exhausted), False otherwise
    """
    if current_date is None:
        current_date = date.today().isoformat()
    
    if current_index >= len(shuffle_list):
        return True
    
    return False


def check_day_passed(last_change_date: str, current_date: Optional[str] = None) -> bool:
    """Check if a day has passed since the last theme change."""
    if current_date is None:
        current_date = date.today().isoformat()
    
    return last_change_date != current_date


def save_theme_change_date(
    last_change_date: str,
    shuffle_path: Optional[Path] = None
) -> None:
    """Save the date of the last theme change."""
    if shuffle_path is None:
        shuffle_path = DEFAULT_SHUFFLE_LIST_PATH
    
    shuffle_path.parent.mkdir(parents=True, exist_ok=True)
    
    state = load_shuffle_list(shuffle_path)
    state['last_change_date'] = last_change_date
    
    with open(shuffle_path, 'w') as f:
        json.dump(state, f, indent=2)


def load_theme_change_date(shuffle_path: Optional[Path] = None) -> str:
    """Load the date of the last theme change."""
    if shuffle_path is None:
        shuffle_path = DEFAULT_SHUFFLE_LIST_PATH
    
    state = load_shuffle_list(shuffle_path)
    return state.get('last_change_date', '')


def save_shuffle_list(
    shuffle_list: List[str],
    current_index: int,
    last_used_date: str,
    shuffle_path: Optional[Path] = None
) -> None:
    """Save shuffle list state to JSON file.
    
    Args:
        shuffle_list: Current shuffled list of themes
        current_index: Current position in the list
        last_used_date: Date when list was last used (YYYY-MM-DD format)
        shuffle_path: Optional path to save to (defaults to DEFAULT_SHUFFLE_LIST_PATH)
    """
    if shuffle_path is None:
        shuffle_path = DEFAULT_SHUFFLE_LIST_PATH
    
    shuffle_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing state to preserve last_change_date
    existing_state = load_shuffle_list(shuffle_path)
    state = {
        "shuffle_list": shuffle_list,
        "current_index": current_index,
        "last_used_date": last_used_date,
        "last_change_date": existing_state.get('last_change_date', '')
    }
    
    with open(shuffle_path, 'w') as f:
        json.dump(state, f, indent=2)


def load_shuffle_list(shuffle_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load shuffle list state from JSON file.
    
    Args:
        shuffle_path: Optional path to load from (defaults to DEFAULT_SHUFFLE_LIST_PATH)
        
    Returns:
        Dictionary with shuffle_list, current_index, and last_used_date
    """
    if shuffle_path is None:
        shuffle_path = DEFAULT_SHUFFLE_LIST_PATH
    
    if not shuffle_path.exists():
        return {
            "shuffle_list": [],
            "current_index": 0,
            "last_used_date": ""
        }
    
    with open(shuffle_path, 'r') as f:
        return json.load(f)


def get_current_date(timezone_str: Optional[str] = None) -> str:
    """Get current date in YYYY-MM-DD format.
    
    Args:
        timezone_str: Optional timezone string (e.g., "America/Phoenix")
                     If None, uses system local date
    
    Returns:
        Current date string in YYYY-MM-DD format
    """
    if timezone_str:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(timezone_str)).date().isoformat()
    return date.today().isoformat()
