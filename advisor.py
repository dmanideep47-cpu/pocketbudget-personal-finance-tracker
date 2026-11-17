"""Rule-based monthly financial summaries and beginner-friendly suggestions."""

from typing import Any, Iterable, Mapping

from analytics import financial_summary
from budget_manager import (
    _budget_entry,
    calculate_category_totals,
    check_over_budget,
)
from file_handler import load_budgets, load_expenses, load_income
from terminal_ui import print_heading, print_warning
from validations import prompt_for_month, validate_month


def financial_advisor(
    month: str | None = None,
    expenses: Iterable[Mapping[str, Any]] | None = None,
    incomes: Iterable[Mapping[str, Any]] | None = None,
    budgets: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize monthly finances and suggest practical spending adjustments."""
    selected_month = validate_month(month) if month is not None else prompt_for_month()
    expense_records = load_expenses() if expenses is None else list(expenses)
    income_records = load_income() if incomes is None else list(incomes)
    budget_records = load_budgets() if budgets is None else budgets
    summary = financial_summary(selected_month, expense_records, income_records)
    monthly_expenses = [
        record
        for record in expense_records
        if record.get("type", "expense") == "expense"
        if str(record.get("date", "")).startswith(selected_month)
    ]
    category_totals = calculate_category_totals(monthly_expenses)
    highest_category = (
        max(category_totals, key=category_totals.get) if category_totals else None
    )
    budget_entry = _budget_entry(budget_records, selected_month)
    over_budget_categories = [
        category
        for category in budget_entry.get("categories", {})
        if check_over_budget(
            selected_month, monthly_expenses, budget_records, category
        )
    ]
    total_income = float(summary["total_income"])
    total_expenses = float(summary["total_expenses"])
    savings = float(summary["savings"])
    savings_percentage = float(summary["savings_percentage"])
    suggestions: list[str] = []

    if not monthly_expenses and total_income == 0:
        suggestions.append(
            "Record income and expenses to receive useful monthly advice."
        )
    if over_budget_categories:
        suggestions.append(
            "Over-budget categories: " + ", ".join(sorted(over_budget_categories)) + "."
        )
    if total_income > 0 and total_expenses > total_income * 0.8:
        suggestions.append(
            "Expenses are above 80% of income; review flexible spending."
        )
    if highest_category and total_expenses > 0:
        share = category_totals[highest_category] / total_expenses
        if share > 0.4:
            suggestions.append(
                f"{highest_category} is {share:.0%} of spending; consider reducing "
                "non-essential costs in this category."
            )
    if total_income > 0 and savings < total_income * 0.2:
        suggestions.append("Aim to save at least 20% of your income where practical.")
    if not suggestions:
        suggestions.append(
            "Your spending is on track; keep recording transactions regularly."
        )

    result: dict[str, Any] = {
        **summary,
        "highest_spending_category": highest_category,
        "over_budget_categories": over_budget_categories,
        "suggestions": suggestions,
    }
    print_heading(f"Financial Advisor | {selected_month}")
    print(f"Income: {total_income:.2f}")
    print(f"Expenses: {total_expenses:.2f}")
    print(f"Savings: {savings:.2f} ({savings_percentage:.1f}% of income)")
    if highest_category:
        print(
            f"Highest spending category: {highest_category} "
            f"({category_totals[highest_category]:.2f})"
        )
    if over_budget_categories:
        print_warning("Over budget: " + ", ".join(sorted(over_budget_categories)))
    print("\nSuggestions:")
    for suggestion in suggestions:
        print(f"  - {suggestion}")
    return result
