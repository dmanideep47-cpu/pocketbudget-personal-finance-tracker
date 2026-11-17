"""Monthly total and category-budget setup and calculations."""

import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from constants import BUDGETS_FILE
from file_handler import DataFileError, load_budgets, load_expenses, save_json
from terminal_ui import print_heading, print_success, print_warning
from validations import (
    prompt_for_amount,
    prompt_for_category,
    prompt_for_month,
    validate_category,
    validate_month,
    validate_positive_amount,
)


def calculate_category_totals(
    expenses: Iterable[Mapping[str, Any]],
) -> dict[str, float]:
    """Return totals for each category in the supplied expense records."""
    totals: dict[str, float] = {}
    for expense in expenses:
        if expense.get("type", "expense") != "expense":
            continue
        category = str(expense.get("category", "Others"))
        totals[category] = totals.get(category, 0.0) + float(expense.get("amount", 0))
    return totals


def _budget_entry(budgets: Mapping[str, Any], month: str) -> dict[str, Any]:
    """Normalize the month's direct category-budget mapping."""
    entry = budgets.get(month, {})
    if not isinstance(entry, dict):
        raise DataFileError(f"Budget data for {month} must be a category dictionary.")

    normalized_categories: dict[str, float] = {}
    for category, value in entry.items():
        try:
            normalized_category = validate_category(category)
            amount = float(value)
        except (TypeError, ValueError) as error:
            raise DataFileError(f"Budget for {category!r} in {month} is invalid.") from error
        if not math.isfinite(amount) or amount <= 0:
            raise DataFileError(
                f"Budget for {category!r} in {month} must be positive and finite."
            )
        normalized_categories[normalized_category] = amount

    return {
        "total": sum(normalized_categories.values()),
        "categories": normalized_categories,
    }


def _expense_total(
    month: str,
    expenses: Iterable[Mapping[str, Any]],
    category: str | None = None,
) -> float:
    """Sum monthly expenses, optionally limited to one category."""
    return sum(
        float(expense.get("amount", 0))
        for expense in expenses
        if expense.get("type", "expense") == "expense"
        and str(expense.get("date", "")).startswith(month)
        and (category is None or expense.get("category") == category)
    )


def calculate_budget_left(
    month: str,
    expenses: Iterable[Mapping[str, Any]],
    budgets: Mapping[str, Any],
    category: str | None = None,
) -> float:
    """Return remaining monthly or category budget; negative means over budget."""
    selected_category = (
        validate_category(category) if category is not None else None
    )
    entry = _budget_entry(budgets, month)
    if selected_category is None:
        limit = float(entry.get("total", 0))
    else:
        limit = float(entry.get("categories", {}).get(selected_category, 0))
    return limit - _expense_total(month, expenses, selected_category)


def check_over_budget(
    month: str,
    expenses: Iterable[Mapping[str, Any]],
    budgets: Mapping[str, Any],
    category: str | None = None,
) -> bool:
    """Return whether actual spending exceeds a configured budget limit."""
    selected_category = (
        validate_category(category) if category is not None else None
    )
    entry = _budget_entry(budgets, month)
    if selected_category is None:
        has_budget = bool(entry.get("categories")) or bool(entry.get("total"))
    else:
        has_budget = selected_category in entry.get("categories", {})
    return has_budget and calculate_budget_left(
        month,
        expenses,
        budgets,
        selected_category,
    ) < 0


def set_budget(
    month: str | None = None,
    category: str | None = None,
    amount: float | None = None,
    budgets_path: Path = BUDGETS_FILE,
) -> float:
    """Set a monthly category limit while preserving other category budgets."""
    print_heading("Set Monthly Budget")
    selected_month = validate_month(month) if month is not None else prompt_for_month()
    category = (
        prompt_for_category()
        if category is None
        else validate_category(category)
    )
    budget_amount = (
        validate_positive_amount(amount)
        if amount is not None
        else prompt_for_amount("Budget amount: ")
    )

    budgets = load_budgets(budgets_path)
    entry = _budget_entry(budgets, selected_month)
    categories = dict(entry["categories"])
    categories[category] = budget_amount
    budgets[selected_month] = categories
    save_json(budgets_path, budgets)
    print_success(
        f"{category} budget for {selected_month} set to {budget_amount:.2f}."
    )
    return budget_amount


def show_budget_status() -> None:
    """Display configured total and category budgets and any overspending."""
    print_heading("Monthly Budget Status")
    month = prompt_for_month()
    expenses = load_expenses()
    budgets = load_budgets()
    entry = _budget_entry(budgets, month)
    if not entry:
        print(f"No budget is set for {month}.")
        return

    category_budgets = entry.get("categories", {})
    if category_budgets:
        remaining = calculate_budget_left(month, expenses, budgets)
        total_budget = sum(category_budgets.values())
        total_spent = _expense_total(month, expenses)
        print(
            f"Overall: budget {total_budget:.2f}, spent {total_spent:.2f}, "
            f"remaining {remaining:.2f}"
        )
        if remaining < 0:
            print_warning(f"Overall budget exceeded by {abs(remaining):.2f}.")
        print("Category budgets:")
        for category, limit in sorted(category_budgets.items()):
            remaining = calculate_budget_left(month, expenses, budgets, category)
            print(
                f"  {category}: budget {float(limit):.2f}, "
                f"spent {_expense_total(month, expenses, category):.2f}, "
                f"remaining {remaining:.2f}"
            )
            if remaining < 0:
                print_warning(f"{category} budget exceeded by {abs(remaining):.2f}.")
    if not category_budgets:
        print(f"No usable budget is set for {month}.")
