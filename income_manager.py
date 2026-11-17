"""Terminal operations for recording and viewing income."""

from pathlib import Path
from typing import Any

from constants import EXPENSES_FILE
from file_handler import (
    load_income,
    load_transactions,
    next_transaction_id,
    save_json,
)
from terminal_ui import print_heading, print_success
from validations import prompt_for_amount, prompt_for_date


def add_income(file_path: Path = EXPENSES_FILE) -> dict[str, Any]:
    """Prompt for income details and append a uniquely identified record."""
    print_heading("Add Income")
    transactions = load_transactions(file_path)
    income = {
        "id": next_transaction_id(transactions),
        "type": "income",
        "amount": prompt_for_amount("Income amount: "),
        "date": prompt_for_date(),
        "source": input("Income source (for example, salary or allowance): ").strip(),
        "description": input("Description: ").strip(),
    }
    transactions.append(income)
    save_json(file_path, transactions)
    print_success(f"Income added with ID {income['id']}.")
    return income


def view_income(file_path: Path = EXPENSES_FILE) -> list[dict[str, Any]]:
    """Display saved income records and return them."""
    print_heading("Income Records")
    incomes = load_income(file_path)
    if not incomes:
        print("No income records are available yet.")
        return []
    print(f"{'ID':<12} {'DATE':<12} {'SOURCE':<20} {'AMOUNT':>12}  DESCRIPTION")
    print("-" * 76)
    for income in sorted(incomes, key=lambda item: (item["date"], str(item["id"]))):
        print(
            f"{str(income['id']):<12} {income['date']:<12} "
            f"{income['source']:<20} {float(income['amount']):>12.2f}  "
            f"{income['description']}"
        )
    return incomes
