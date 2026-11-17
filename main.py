"""Command-line entry point for PocketBudget."""

import logging
import sys
from typing import Callable

from advisor import financial_advisor
from analytics import (
    analyze_spending,
    export_monthly_csv,
    monthly_statement,
)
from budget_manager import set_budget, show_budget_status
from constants import INVALID_MENU_CHOICE_MESSAGE
from expense_manager import (
    add_expense,
    delete_expense,
    edit_expense,
    search_expenses,
    view_expenses,
)
from file_handler import DataFileError, ensure_storage
from income_manager import add_income
from terminal_ui import (
    display_menu,
    print_error,
    print_success,
    print_warning,
)
from validations import prompt_for_month
from visualizations import show_charts

LOGGER = logging.getLogger(__name__)


def export_statement() -> None:
    """Prompt for a month and export its expense statement."""
    export_monthly_csv(prompt_for_month())


def _menu_actions() -> dict[str, Callable[[], object]]:
    """Map menu choices to their terminal operations."""
    return {
        "1": add_expense,
        "2": view_expenses,
        "3": edit_expense,
        "4": delete_expense,
        "5": search_expenses,
        "6": add_income,
        "7": set_budget,
        "8": show_budget_status,
        "9": monthly_statement,
        "10": analyze_spending,
        "11": export_statement,
        "12": show_charts,
        "13": financial_advisor,
    }


def run_menu() -> None:
    """Initialize storage and run the validated terminal menu."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        ensure_storage()
    except (DataFileError, OSError) as error:
        LOGGER.exception("PocketBudget could not initialize its data files.")
        print_error(f"Could not initialize local data files: {error}")
        return

    actions = _menu_actions()
    while True:
        display_menu()
        try:
            choice = input("Enter your choice: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nPocketBudget closed.")
            return
        if choice == "0":
            print_success("Operation successful. Goodbye!")
            return
        action = actions.get(choice)
        if action is None:
            print_warning(INVALID_MENU_CHOICE_MESSAGE)
            continue
        try:
            action()
        except (EOFError, KeyboardInterrupt):
            print_warning("Operation cancelled; no incomplete changes were saved.")
        except DataFileError as error:
            LOGGER.error("Data validation failed: %s", error)
            print_error(str(error))
        except OSError as error:
            LOGGER.exception("A file operation failed.")
            print_error(f"A file operation failed: {error}")
        except ValueError as error:
            print_warning(str(error))


if __name__ == "__main__":
    run_menu()
