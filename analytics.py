"""Pandas-powered financial reports, summaries, and monthly CSV export."""

from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from budget_manager import calculate_category_totals
from constants import CSV_COLUMNS, EXPORTS_DIR
from file_handler import load_expenses, load_income
from terminal_ui import print_heading, print_success
from validations import prompt_for_month, validate_month

INCOME_COLUMNS = ("id", "type", "amount", "date", "source", "description")


def expenses_dataframe(expenses: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    """Build a typed DataFrame for expenses, including when there are no rows."""
    frame = pd.DataFrame(list(expenses), columns=CSV_COLUMNS)
    frame["type"] = frame["type"].fillna("expense")
    frame = frame.loc[frame["type"].eq("expense")].copy()
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="coerce")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
    return frame


def incomes_dataframe(incomes: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    """Build a typed DataFrame for income records, including empty records."""
    frame = pd.DataFrame(list(incomes), columns=INCOME_COLUMNS)
    frame["type"] = frame["type"].fillna("income")
    frame = frame.loc[frame["type"].eq("income")].copy()
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="coerce")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
    return frame


def _month_records(frame: pd.DataFrame, month: str) -> pd.DataFrame:
    """Return valid records belonging to the requested month."""
    return frame.loc[
        frame["date"].notna() & frame["date"].dt.strftime("%Y-%m").eq(month)
    ].copy()


def calculate_savings_percentage(total_income: float, total_expenses: float) -> float:
    """Return savings as a percentage of income, or zero when income is absent."""
    if total_income <= 0:
        return 0.0
    return (total_income - total_expenses) / total_income * 100


def calculate_highest_expense_days(daily_spending: pd.Series) -> dict[str, float]:
    """Return all dates tied for the highest total daily expense."""
    if daily_spending.empty:
        return {}
    highest = daily_spending.max()
    return {
        str(date): float(amount)
        for date, amount in daily_spending[daily_spending.eq(highest)].items()
    }


def financial_summary(
    month: str,
    expenses: Iterable[Mapping[str, Any]] | None = None,
    incomes: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, float | str]:
    """Calculate monthly income, expenses, savings, and savings percentage."""
    selected_month = validate_month(month)
    expense_records = load_expenses() if expenses is None else list(expenses)
    income_records = load_income() if incomes is None else list(incomes)
    month_expenses = _month_records(expenses_dataframe(expense_records), selected_month)
    month_income = _month_records(incomes_dataframe(income_records), selected_month)
    total_expenses = float(month_expenses["amount"].sum())
    total_income = float(month_income["amount"].sum())
    savings = total_income - total_expenses
    return {
        "month": selected_month,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "current_balance": savings,
        "savings": savings,
        "savings_percentage": calculate_savings_percentage(
            total_income,
            total_expenses,
        ),
    }


def monthly_statement(
    month: str | None = None,
    expenses: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Print and return monthly, category, and weekly expense totals."""
    selected_month = (
        validate_month(month) if month is not None else prompt_for_month()
    )
    records = load_expenses() if expenses is None else list(expenses)
    month_frame = _month_records(expenses_dataframe(records), selected_month)
    category_totals = calculate_category_totals(month_frame.to_dict("records"))
    daily_totals = month_frame.groupby(month_frame["date"].dt.strftime("%Y-%m-%d"))[
        "amount"
    ].sum()
    weekly_totals = month_frame.groupby(month_frame["date"].dt.to_period("W"))[
        "amount"
    ].sum()
    average_daily_spend = (
        float(daily_totals.mean()) if not daily_totals.empty else 0.0
    )
    result: dict[str, Any] = {
        "month": selected_month,
        "total": float(month_frame["amount"].sum()),
        "expense_count": int(month_frame["id"].nunique()),
        "average_daily_spend": average_daily_spend,
        "category_totals": category_totals,
        "daily_totals": {
            str(day): float(amount) for day, amount in daily_totals.items()
        },
        "weekly_totals": {
            str(week): float(amount) for week, amount in weekly_totals.items()
        },
        "expenses": month_frame.assign(
            date=month_frame["date"].dt.strftime("%Y-%m-%d")
        ).to_dict("records"),
    }

    print_heading(f"Monthly Expense Report | {selected_month}")
    print(f"Total expenses: {result['total']:.2f}")
    print(f"Number of expenses: {result['expense_count']}")
    print(f"Average daily spend: {average_daily_spend:.2f}")
    if not result["expense_count"]:
        print("No expenses are recorded for this month.")
        return result
    print("\nCategory-wise report:")
    for category, total in sorted(category_totals.items()):
        print(f"  {category:<18} {total:>10.2f}")
    print("\nWeekly spending:")
    for week, total in result["weekly_totals"].items():
        print(f"  {week:<25} {total:>10.2f}")
    return result


def analyze_spending(
    month: str | None = None,
    expenses: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Analyze monthly categories, weeks, daily averages, high days, and top three."""
    selected_month = validate_month(month) if month is not None else prompt_for_month()
    records = load_expenses() if expenses is None else list(expenses)
    month_frame = _month_records(expenses_dataframe(records), selected_month)
    category_totals = (
        month_frame.groupby("category")["amount"]
        .sum()
        .sort_values(ascending=False)
    )
    daily_totals = month_frame.groupby(month_frame["date"].dt.strftime("%Y-%m-%d"))[
        "amount"
    ].sum()
    weekly_totals = month_frame.groupby(month_frame["date"].dt.to_period("W"))[
        "amount"
    ].sum()
    active_days = int(month_frame["date"].dt.normalize().nunique())

    result: dict[str, Any] = {
        "month": selected_month,
        "monthly_total": float(month_frame["amount"].sum()),
        "category_spending": {
            str(category): float(amount) for category, amount in category_totals.items()
        },
        "weekly_spending": {
            str(week): float(amount) for week, amount in weekly_totals.items()
        },
        "average_daily_spend": (
            float(daily_totals.mean()) if not daily_totals.empty else 0.0
        ),
        "active_days": active_days,
        "highest_expense_days": calculate_highest_expense_days(daily_totals),
        "top_spending_categories": {
            str(category): float(amount)
            for category, amount in category_totals.head(3).items()
        },
    }

    print_heading(f"Spending Analysis | {selected_month}")
    print(f"Monthly total: {result['monthly_total']:.2f}")
    print(f"Average spend per active day: {result['average_daily_spend']:.2f}")
    print(f"Active spending days: {active_days}")
    if category_totals.empty:
        print("No expenses are recorded for this month.")
        return result
    print("\nSpending by category:")
    for category, total in category_totals.items():
        print(f"  {category:<18} {total:>10.2f}")
    print("\nSpending by week:")
    for week, total in weekly_totals.items():
        print(f"  {str(week):<25} {total:>10.2f}")
    print("\nHighest-expense day(s):")
    for date, total in result["highest_expense_days"].items():
        print(f"  {date}: {total:.2f}")
    print("\nTop spending categories:")
    for category, total in result["top_spending_categories"].items():
        print(f"  {category}: {total:.2f}")
    return result


def export_monthly_csv(
    month: str | None = None,
    expenses: Iterable[Mapping[str, Any]] | None = None,
    export_dir: Path = EXPORTS_DIR,
) -> Path:
    """Export all monthly expense fields as an Excel-friendly UTF-8 CSV."""
    selected_month = validate_month(month) if month is not None else prompt_for_month()
    records = load_expenses() if expenses is None else list(expenses)
    month_frame = _month_records(expenses_dataframe(records), selected_month)
    month_frame["date"] = month_frame["date"].dt.strftime("%Y-%m-%d")
    export_path = Path(export_dir) / f"expense_statement_{selected_month}.csv"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    month_frame.loc[:, CSV_COLUMNS].to_csv(
        export_path,
        index=False,
        encoding="utf-8-sig",
    )
    print_success(f"Monthly statement exported to {export_path.resolve()}.")
    return export_path
