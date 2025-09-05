"""
Utility module for managing project paths dynamically.
This ensures the application works regardless of where it's installed.
"""

import os


def get_project_root():
    """
    Get the project root directory (where main.py is located).
    
    Returns:
        str: Absolute path to the project root directory
    """
    # Get the directory containing this file
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level to reach the project root (where main.py is)
    project_root = os.path.dirname(current_file_dir)
    return project_root


def get_tools_dir():
    """
    Get the tools directory path.
    
    Returns:
        str: Absolute path to the tools directory
    """
    return os.path.join(get_project_root(), "tools")


def get_database_path():
    """
    Get the database file path.
    
    Returns:
        str: Absolute path to the database file
    """
    return os.path.join(get_project_root(), "database", "forensic_system.db")


def get_forensic_collection_dir():
    """
    Get the forensic collection directory path.
    
    Returns:
        str: Absolute path to the forensic collection directory
    """
    return os.path.join(get_project_root(), "ForensicCollection")


def get_evidence_dir():
    """
    Get the evidence directory path.
    
    Returns:
        str: Absolute path to the evidence directory
    """
    return os.path.join(get_project_root(), "evidence")


def get_temp_dir():
    """
    Get the temporary directory path.
    
    Returns:
        str: Absolute path to the temp directory
    """
    return os.path.join(get_project_root(), "temp")


def get_static_dir():
    """
    Get the static resources directory path.
    
    Returns:
        str: Absolute path to the static directory
    """
    return os.path.join(get_project_root(), "static")


def get_ui_dir():
    """
    Get the UI directory path.
    
    Returns:
        str: Absolute path to the UI directory
    """
    return os.path.join(get_project_root(), "ui")


def ensure_directories():
    """
    Ensure all necessary directories exist.
    Creates directories if they don't exist.
    """
    directories = [
        get_forensic_collection_dir(),
        get_evidence_dir(),
        get_temp_dir(),
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
