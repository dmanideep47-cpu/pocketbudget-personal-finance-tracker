"""Small helpers for consistent, safe terminal presentation."""

import os
import platform
import sys
from typing import TextIO

from constants import (
    COLOR_ERROR,
    COLOR_RESET,
    COLOR_SUCCESS,
    COLOR_WARNING,
    MENU_OPTIONS,
)


def supports_ansi(stream: TextIO = sys.stdout) -> bool:
    """Return whether the current output terminal is known to support ANSI."""
    if not stream.isatty() or os.environ.get("NO_COLOR"):
        return False
    if platform.system() != "Windows":
        return True
    return bool(
        os.environ.get("WT_SESSION")
        or os.environ.get("ANSICON")
        or os.environ.get("ConEmuANSI") == "ON"
        or os.environ.get("TERM_PROGRAM") == "vscode"
    )


def print_message(message: str, color: str | None = None) -> None:
    """Print a message, using color only when the terminal supports it."""
    if color and supports_ansi():
        print(f"{color}{message}{COLOR_RESET}")
    else:
        print(message)


def print_success(message: str) -> None:
    """Print a user-facing success message."""
    print_message(f"Success: {message}", COLOR_SUCCESS)


def print_warning(message: str) -> None:
    """Print a user-facing warning message."""
    print_message(f"Warning: {message}", COLOR_WARNING)


def print_error(message: str) -> None:
    """Print a user-facing error message."""
    print_message(f"Error: {message}", COLOR_ERROR)


def print_heading(title: str) -> None:
    """Print a section title with consistent separators."""
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def display_menu() -> None:
    """Print the complete PocketBudget terminal menu."""
    print("========== POCKETBUDGET ==========")
    for choice, label in MENU_OPTIONS.items():
        if choice != "0":
            print(f"{choice}. {label}")
    print("0. Exit")
    print("==================================")
