"""Shared configuration for PocketBudget."""

from pathlib import Path
from typing import Final


BASE_DIR: Final[Path] = Path(__file__).resolve().parent
DATA_DIR: Final[Path] = BASE_DIR / "data"
EXPORTS_DIR: Final[Path] = BASE_DIR / "exports"
CHARTS_DIR: Final[Path] = BASE_DIR / "charts"
EXPENSES_FILE: Final[Path] = DATA_DIR / "expenses.json"
BUDGETS_FILE: Final[Path] = DATA_DIR / "budgets.json"

CATEGORIES: Final[set[str]] = {
    "Food",
    "Travel",
    "Shopping",
    "Education",
    "Bills",
    "Entertainment",
    "Health",
    "Others",
}
EXPENSE_CATEGORIES = CATEGORIES
PAYMENT_METHODS: Final[tuple[str, ...]] = (
    "Cash",
    "UPI",
    "Card",
    "Net Banking",
)

MENU_OPTIONS: Final[dict[str, str]] = {
    "1": "Add Expense",
    "2": "View Expenses",
    "3": "Edit Expense",
    "4": "Delete Expense",
    "5": "Search Expenses",
    "6": "Add Income",
    "7": "Set Monthly Budget",
    "8": "Check Budget Status",
    "9": "Monthly Expense Report",
    "10": "Spending Analysis",
    "11": "Export Monthly Statement to CSV",
    "12": "Show Charts",
    "13": "Financial Advisor",
    "0": "Exit",
}

CHART_COLORS: Final[list[str]] = [
    "#2563EB",
    "#F59E0B",
    "#10B981",
    "#EF4444",
    "#8B5CF6",
    "#06B6D4",
    "#F97316",
    "#64748B",
]
CHART_BACKGROUND: Final[str] = "#FFFFFF"
TEXT_COLOR: Final[str] = "#1F2937"
GRID_COLOR: Final[str] = "#E5E7EB"
OVER_BUDGET_COLOR: Final[str] = "#DC2626"
CHART_DPI: Final[int] = 300
FIGURE_SIZE: Final[tuple[int, int]] = (10, 6)
COLOR_SUCCESS: Final[str] = "\033[32m"
COLOR_WARNING: Final[str] = "\033[33m"
COLOR_ERROR: Final[str] = "\033[31m"
COLOR_RESET: Final[str] = "\033[0m"
INVALID_MENU_CHOICE_MESSAGE: Final[str] = (
    "Invalid menu choice. Choose a number from 0 to 13."
)
NO_EXPENSES_MESSAGE: Final[str] = (
    "No expenses are available yet. Choose 'Add expense' to get started."
)

CSV_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "type",
    "amount",
    "category",
    "date",
    "description",
    "payment_method",
)
