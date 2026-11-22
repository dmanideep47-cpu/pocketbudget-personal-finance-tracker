"""Unit tests for validation, transaction storage, budgets, and reporting."""

import csv
import json
from pathlib import Path
from typing import Callable, Iterator

import pandas as pd
import pytest

import budget_manager
from advisor import financial_advisor
from analytics import (
    calculate_highest_expense_days,
    calculate_savings_percentage,
    export_monthly_csv,
    financial_summary,
    monthly_statement,
)
from budget_manager import (
    calculate_budget_left,
    calculate_category_totals,
    check_over_budget,
    set_budget,
    show_budget_status,
)
from constants import MENU_OPTIONS
from expense_manager import (
    add_expense,
    delete_expense,
    edit_expense,
    search_expenses,
    view_expenses,
)
from file_handler import (
    DataFileError,
    load_expenses,
    load_income,
    load_json,
    load_transactions,
    save_json,
)
from income_manager import add_income, view_income
from terminal_ui import display_menu
from validations import (
    validate_category,
    validate_date,
    validate_expense_id,
    validate_month,
    validate_payment_method,
    validate_positive_amount,
)
from visualizations import CHART_NAMES, show_charts

SAMPLE_EXPENSES = [
    {
        "id": 1,
        "type": "expense",
        "amount": 25.0,
        "category": "Food",
        "date": "2026-04-02",
        "description": "Lunch, cafe",
        "payment_method": "UPI",
    },
    {
        "id": 2,
        "type": "expense",
        "amount": 50.0,
        "category": "Travel",
        "date": "2026-04-02",
        "description": "Bus pass",
        "payment_method": "Card",
    },
    {
        "id": 3,
        "type": "expense",
        "amount": 10.0,
        "category": "Food",
        "date": "2026-05-01",
        "description": "Breakfast",
        "payment_method": "Cash",
    },
]


def _mock_input(answers: Iterator[str]) -> Callable[[str], str]:
    """Create an input replacement that prints prompts and returns test answers."""

    def read_input(prompt: str = "") -> str:
        """Display a terminal prompt and return the next predetermined answer."""
        print(prompt, end="")
        return next(answers)

    return read_input


def test_validate_positive_amount_accepts_and_rejects_values() -> None:
    """Positive finite numbers pass; invalid and negative amounts fail."""
    assert validate_positive_amount("12.50") == 12.5
    for value in ("0", "-1", "abc", "nan", "inf", True):
        with pytest.raises(ValueError):
            validate_positive_amount(value)


def test_validate_date_checks_format_and_calendar_value() -> None:
    """ISO dates are accepted and malformed or impossible dates are rejected."""
    assert validate_date("2026-04-09") == "2026-04-09"
    for value in ("09-04-2026", "2026-02-30", "2026-4-09"):
        with pytest.raises(ValueError):
            validate_date(value)


def test_validate_month_checks_format_and_calendar_value() -> None:
    """Calendar months accept YYYY-MM only."""
    assert validate_month("2026-04") == "2026-04"
    for value in ("2026-13", "2026-4", "04-2026"):
        with pytest.raises(ValueError):
            validate_month(value)


def test_validate_category_checks_allowed_set() -> None:
    """Category matching is case-insensitive but rejects unknown values."""
    assert validate_category("food") == "Food"
    with pytest.raises(ValueError):
        validate_category("Pets")


def test_validate_payment_method_checks_allowed_methods() -> None:
    """Only supported payment methods are accepted."""
    assert validate_payment_method("upi") == "UPI"
    with pytest.raises(ValueError):
        validate_payment_method("PhonePe")


def test_validate_expense_id_requires_positive_integer() -> None:
    """Transaction IDs must be positive whole numbers."""
    assert validate_expense_id("1") == 1
    for value in ("", "0", "-1", "1.5", "bad"):
        with pytest.raises(ValueError):
            validate_expense_id(value)


def test_category_totals_filter_expenses_and_group_by_category() -> None:
    """Category totals combine expense records without counting income."""
    records = SAMPLE_EXPENSES + [
        {
            "id": 4,
            "type": "income",
            "amount": 1000,
            "date": "2026-04-01",
            "source": "Work",
            "description": "Pay",
        }
    ]
    totals = calculate_category_totals(records)
    assert totals == {"Food": 35.0, "Travel": 50.0}


def test_budget_left_and_over_budget_for_category_budgets() -> None:
    """Monthly and per-category remaining balances use direct month maps."""
    budgets = {"2026-04": {"Food": 20.0, "Travel": 50.0}}
    assert calculate_budget_left("2026-04", SAMPLE_EXPENSES, budgets) == -5.0
    assert calculate_budget_left("2026-04", SAMPLE_EXPENSES, budgets, "Food") == -5.0
    assert check_over_budget("2026-04", SAMPLE_EXPENSES, budgets)
    assert check_over_budget("2026-04", SAMPLE_EXPENSES, budgets, "Food")
    assert not check_over_budget("2026-04", SAMPLE_EXPENSES, budgets, "Education")


def test_savings_percentage_handles_income_and_missing_income() -> None:
    """Savings percentage uses net savings and safely handles zero income."""
    assert calculate_savings_percentage(1000, 750) == 25.0
    assert calculate_savings_percentage(0, 10) == 0.0


def test_validation_rejects_non_string_calendar_values() -> None:
    """Calendar validators reject non-string values instead of coercing them."""
    for value in (None, 20260409, True, ""):
        with pytest.raises(ValueError):
            validate_date(value)
    for value in (None, 202604, True, ""):
        with pytest.raises(ValueError):
            validate_month(value)


def test_savings_percentage_can_be_negative_when_expenses_exceed_income() -> None:
    """A deficit is represented as a negative savings percentage."""
    assert calculate_savings_percentage(1000, 1250) == -25.0


def test_budget_boundary_is_not_over_budget_until_spending_exceeds_limit() -> None:
    """Spending exactly at a configured limit is within budget."""
    expenses = [
        {
            "id": 1,
            "type": "expense",
            "amount": 100.0,
            "category": "Food",
            "date": "2026-04-10",
            "description": "Groceries",
            "payment_method": "UPI",
        }
    ]
    budgets = {"2026-04": {"Food": 100.0}}
    assert calculate_budget_left("2026-04", expenses, budgets, "Food") == 0.0
    assert not check_over_budget("2026-04", expenses, budgets, "Food")


def test_highest_expense_days_returns_ties_and_handles_empty_series() -> None:
    """All days tied for highest spend are returned, or empty when no data."""
    spending = pd.Series(
        [25.0, 75.0, 75.0],
        index=["2026-04-01", "2026-04-02", "2026-04-03"],
    )
    assert calculate_highest_expense_days(spending) == {
        "2026-04-02": 75.0,
        "2026-04-03": 75.0,
    }
    assert calculate_highest_expense_days(pd.Series(dtype=float)) == {}


def test_load_json_initializes_missing_file(tmp_path: Path) -> None:
    """A missing file is initialized in the temporary directory."""
    data_file = tmp_path / "nested" / "expenses.json"
    assert load_json(data_file, []) == []
    assert json.loads(data_file.read_text(encoding="utf-8")) == []


def test_load_json_reports_corruption_without_overwriting(tmp_path: Path) -> None:
    """Corrupt JSON is reported and left untouched for recovery."""
    data_file = tmp_path / "expenses.json"
    data_file.write_text("{invalid", encoding="utf-8")
    with pytest.raises(DataFileError):
        load_json(data_file, [])
    assert data_file.read_text(encoding="utf-8") == "{invalid"


def test_legacy_transactions_migrate_to_required_schema_and_backup(tmp_path: Path) -> None:
    """Old string IDs and missing type fields migrate with a recoverable backup."""
    data_file = tmp_path / "expenses.json"
    legacy = [
        {
            "id": "old-id",
            "amount": 30,
            "category": "Food",
            "date": "2026-04-01",
            "description": "Snack",
            "payment_method": "Cash",
        }
    ]
    data_file.write_text(json.dumps(legacy), encoding="utf-8")

    transactions = load_transactions(data_file)

    assert transactions[0]["id"] == 1
    assert transactions[0]["type"] == "expense"
    assert json.loads(data_file.with_suffix(".json.bak").read_text(encoding="utf-8")) == legacy


def test_duplicate_ids_are_reassigned_without_losing_records(tmp_path: Path) -> None:
    """Loading duplicate IDs assigns a fresh sequential ID to later records."""
    data_file = tmp_path / "expenses.json"
    duplicate_records = [dict(SAMPLE_EXPENSES[0]), dict(SAMPLE_EXPENSES[0])]
    data_file.write_text(json.dumps(duplicate_records), encoding="utf-8")

    records = load_transactions(data_file)

    assert [record["id"] for record in records] == [1, 2]
    assert len(load_expenses(data_file)) == 2


def test_save_json_creates_backup_before_overwriting(tmp_path: Path) -> None:
    """The previous JSON content is preserved in a sibling backup."""
    data_file = tmp_path / "expenses.json"
    save_json(data_file, [{"version": 1}])
    save_json(data_file, [{"version": 2}])
    backup = data_file.with_suffix(".json.bak")
    assert json.loads(data_file.read_text(encoding="utf-8")) == [{"version": 2}]
    assert json.loads(backup.read_text(encoding="utf-8")) == [{"version": 1}]


def test_add_expense_retries_invalid_inputs_and_saves_typed_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expense entry retries invalid amount/payment and stores the schema."""
    data_file = tmp_path / "expenses.json"
    save_json(data_file, [])
    answers = iter(
        ["zero", "12.5", "food", "2026-04-04", "Lunch", "PhonePe", "UPI"]
    )
    monkeypatch.setattr("builtins.input", _mock_input(answers))

    expense = add_expense(data_file)

    assert expense == {
        "id": 1,
        "type": "expense",
        "amount": 12.5,
        "category": "Food",
        "date": "2026-04-04",
        "description": "Lunch",
        "payment_method": "UPI",
    }
    assert load_expenses(data_file) == [expense]
    assert (tmp_path / "expenses.json.bak").exists()


def test_edit_and_confirmed_delete_preserve_transaction_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Editing and deleting an expense leave other transaction types intact."""
    data_file = tmp_path / "expenses.json"
    records = [
        dict(SAMPLE_EXPENSES[0]),
        {
            **SAMPLE_EXPENSES[1],
            "id": 2,
            "description": "Second expense",
        },
        {
            "id": 3,
            "type": "income",
            "amount": 100,
            "date": "2026-04-01",
            "source": "Work",
            "description": "Pay",
        },
    ]
    save_json(data_file, records)
    edit_answers = iter(["1", "40", "", "", "", ""])
    monkeypatch.setattr("builtins.input", _mock_input(edit_answers))
    assert edit_expense(data_file)
    assert load_income(data_file)[0]["id"] == 3
    assert load_expenses(data_file)[0]["amount"] == 40

    delete_answers = iter(["1", "yes"])
    monkeypatch.setattr("builtins.input", _mock_input(delete_answers))
    assert delete_expense(data_file)
    assert [record["id"] for record in load_expenses(data_file)] == [1]
    assert load_income(data_file)[0]["id"] == 2
    assert [
        record["id"] for record in load_transactions(data_file)
    ] == [1, 2]


def test_search_and_view_expenses_use_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Search matches supported fields and list view returns saved records."""
    data_file = tmp_path / "expenses.json"
    save_json(data_file, [dict(SAMPLE_EXPENSES[0]), dict(SAMPLE_EXPENSES[1])])
    monkeypatch.setattr("builtins.input", _mock_input(iter(["cafe"])))

    matches = search_expenses(data_file)
    records = view_expenses(data_file)

    assert [record["id"] for record in matches] == [1]
    assert len(records) == 2


def test_income_shares_expense_file_and_uses_next_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Income records use type=income and share the unique transaction sequence."""
    data_file = tmp_path / "expenses.json"
    save_json(data_file, [dict(SAMPLE_EXPENSES[0])])
    answers = iter(["1200", "2026-04-01", "Part-time work", "April payment"])
    monkeypatch.setattr("builtins.input", _mock_input(answers))

    income = add_income(data_file)

    assert income["id"] == 2
    assert income["type"] == "income"
    assert len(load_expenses(data_file)) == 1
    assert load_income(data_file) == [income]
    assert view_income(data_file) == [income]


def test_category_budget_input_retries_and_writes_direct_month_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid categories are retried and budgets use the requested JSON shape."""
    budgets_file = tmp_path / "budgets.json"
    answers = iter(["2026-04", "unknown", "food", "75"])
    monkeypatch.setattr("builtins.input", _mock_input(answers))

    assert set_budget(budgets_path=budgets_file) == 75
    assert json.loads(budgets_file.read_text(encoding="utf-8")) == {
        "2026-04": {"Food": 75.0}
    }


def test_budget_status_reports_category_and_total_overspending(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Budget-status output includes category and aggregate over-budget amounts."""
    monkeypatch.setattr(budget_manager, "load_expenses", lambda: SAMPLE_EXPENSES)
    monkeypatch.setattr(
        budget_manager,
        "load_budgets",
        lambda: {"2026-04": {"Food": 20, "Travel": 50}},
    )
    monkeypatch.setattr("builtins.input", _mock_input(iter(["2026-04"])))

    show_budget_status()

    output = capsys.readouterr().out
    assert "Overall budget exceeded" in output
    assert "Food budget exceeded" in output


def test_monthly_financial_summary_and_advisor_apply_rules() -> None:
    """Monthly income, savings, spending thresholds, and category alerts are correct."""
    incomes = [
        {
            "id": 4,
            "type": "income",
            "amount": 1000,
            "date": "2026-04-01",
            "source": "Work",
            "description": "Pay",
        }
    ]
    expenses = [
        {
            **SAMPLE_EXPENSES[0],
            "id": 1,
            "amount": 450,
            "date": "2026-04-02",
            "description": "Groceries",
        },
        {
            **SAMPLE_EXPENSES[1],
            "id": 2,
            "amount": 400,
            "category": "Food",
            "date": "2026-04-03",
            "description": "Dinner",
        },
    ]
    summary = financial_summary("2026-04", expenses, incomes)
    advice = financial_advisor(
        "2026-04",
        expenses,
        incomes,
        {"2026-04": {"Food": 700}},
    )

    assert summary["total_income"] == 1000
    assert summary["total_expenses"] == 850
    assert summary["current_balance"] == 150
    assert summary["savings"] == 150
    assert summary["savings_percentage"] == 15
    assert advice["highest_spending_category"] == "Food"
    assert advice["over_budget_categories"] == ["Food"]
    assert any("80%" in suggestion for suggestion in advice["suggestions"])
    assert any("20%" in suggestion for suggestion in advice["suggestions"])


def test_monthly_reports_handle_empty_months() -> None:
    """Empty months return zero totals and empty category breakdowns."""
    statement = monthly_statement("2026-04", [])
    summary = financial_summary("2026-04", [], [])
    assert statement["total"] == 0
    assert statement["expense_count"] == 0
    assert statement["category_totals"] == {}
    assert summary["total_income"] == 0
    assert summary["total_expenses"] == 0


def test_monthly_report_includes_average_daily_spend(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Monthly report returns and prints the mean spend across active days."""
    statement = monthly_statement("2026-04", SAMPLE_EXPENSES)
    output = capsys.readouterr().out
    assert statement["average_daily_spend"] == 75
    assert "Average daily spend: 75.00" in output


def test_csv_export_contains_required_columns_and_month_only(
    tmp_path: Path,
) -> None:
    """CSV includes every specified field and only the selected month's data."""
    export_path = export_monthly_csv("2026-04", SAMPLE_EXPENSES, tmp_path)
    with export_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert list(rows[0]) == [
        "id",
        "type",
        "amount",
        "category",
        "date",
        "description",
        "payment_method",
    ]
    assert len(rows) == 2
    assert rows[0]["description"] == "Lunch, cafe"
    assert all(row["date"].startswith("2026-04") for row in rows)


def test_all_five_charts_save_for_empty_and_populated_months(tmp_path: Path) -> None:
    """All charts are saved for both empty and populated data without real IO."""
    empty_paths = show_charts(
        "2026-04", [], [], {}, tmp_path / "empty", display=False
    )
    filled_paths = show_charts(
        "2026-04",
        SAMPLE_EXPENSES,
        [],
        {"2026-04": {"Food": 20, "Travel": 80}},
        tmp_path / "filled",
        display=False,
    )
    assert [path.name for path in empty_paths] == list(CHART_NAMES)
    assert [path.name for path in filled_paths] == list(CHART_NAMES)
    assert all(path.exists() and path.stat().st_size > 1000 for path in empty_paths)
    assert all(path.exists() and path.stat().st_size > 1000 for path in filled_paths)


def test_main_menu_matches_required_choices_and_labels(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Menu labels and ordering match the required terminal interface."""
    from main import _menu_actions

    display_menu()
    output = capsys.readouterr().out
    assert output.splitlines() == [
        "========== POCKETBUDGET ==========",
        "1. Add Expense",
        "2. View Expenses",
        "3. Edit Expense",
        "4. Delete Expense",
        "5. Search Expenses",
        "6. Add Income",
        "7. Set Monthly Budget",
        "8. Check Budget Status",
        "9. Monthly Expense Report",
        "10. Spending Analysis",
        "11. Export Monthly Statement to CSV",
        "12. Show Charts",
        "13. Financial Advisor",
        "0. Exit",
        "==================================",
    ]
    assert set(_menu_actions()) == set(MENU_OPTIONS) - {"0"}


def test_invalid_menu_choice_warns_and_returns_to_menu(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An invalid choice is warned about before the menu accepts Exit."""
    import main

    answers = iter(["not a choice", "0"])
    monkeypatch.setattr(main, "ensure_storage", lambda: None)
    monkeypatch.setattr("builtins.input", _mock_input(answers))

    main.run_menu()

    output = capsys.readouterr().out
    assert "Invalid menu choice" in output
    assert "Goodbye" in output
