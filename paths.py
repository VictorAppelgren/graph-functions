from pathlib import Path
from typing import Optional


def get_project_root() -> Path:
    """
    Returns the absolute path to the project root directory.
    """
    # Start from this file's location, walk up until main.py is found
    project_root = Path(__file__).resolve().parent
    while (
        not (project_root / "main.py").exists() and project_root != project_root.parent
    ):
        project_root = project_root.parent
    return project_root


def get_data_dir() -> Path:
    """
    Returns the absolute path to the data directory (project_root/data).
    """
    return get_project_root() / "data"


def get_raw_news_dir(day: Optional[str] = None) -> Path:
    """
    Returns the absolute path to the raw news directory for a specific day.

    Args:
        day: Optional date string in format YYYY-MM-DD. If None, returns the raw_news base directory.

    Returns:
        Path to the raw news directory for the specified day or base raw_news directory if no day provided.
    """
    # The raw_news directory is inside the data directory
    raw_news_dir = get_project_root() / "data" / "raw_news"

    if day is not None:
        # Ensure day is in the expected format (YYYY-MM-DD)
        if len(day) != 10 or day[4] != "-" or day[7] != "-":
            raise ValueError(f"Day must be in format YYYY-MM-DD, got: {day}")

        # Return the path to the specific day's directory
        return raw_news_dir / day

    # Return the base raw_news directory
    return raw_news_dir
