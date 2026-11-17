"""Terminal-based expense management and reporting helpers."""

from pathlib import Path
from typing import Any, Callable

from constants import EXPENSES_FILE, NO_EXPENSES_MESSAGE
from file_handler import (
    load_expenses,
    load_transactions,
    next_transaction_id,
    save_json,
)
from terminal_ui import print_heading, print_success, print_warning
from validations import (
    prompt_for_amount,
    prompt_for_category,
    prompt_for_date,
    prompt_for_expense_id,
    prompt_for_payment_method,
    validate_category,
    validate_date,
    validate_payment_method,
    validate_positive_amount,
)


def _find_expense(
    expenses: list[dict[str, Any]],
    expense_id: int,
) -> dict[str, Any] | None:
    """Find one expense by its exact ID."""
    return next(
        (
            expense
            for expense in expenses
            if expense["type"] == "expense" and expense["id"] == expense_id
        ),
        None,
    )


def add_expense(file_path: Path = EXPENSES_FILE) -> dict[str, Any]:
    """Prompt for expense fields and save a uniquely identified expense."""
    print_heading("Add Expense")
    transactions = load_transactions(file_path)
    expense = {
        "id": next_transaction_id(transactions),
        "type": "expense",
        "amount": prompt_for_amount(),
        "category": prompt_for_category(),
        "date": prompt_for_date(),
        "description": input("Description: ").strip(),
        "payment_method": prompt_for_payment_method(),
    }
    transactions.append(expense)
    save_json(file_path, transactions)
    print_success(f"Expense added with ID {expense['id']}.")
    return expense


def view_expenses(file_path: Path = EXPENSES_FILE) -> list[dict[str, Any]]:
    """Display expenses in chronological order and return the loaded records."""
    print_heading("Expense Records")
    expenses = load_expenses(file_path)
    if not expenses:
        print(NO_EXPENSES_MESSAGE)
        return []

    print(
        f"{'ID':<12} {'DATE':<12} {'CATEGORY':<16} "
        f"{'AMOUNT':>12} {'PAYMENT':<14} DESCRIPTION"
    )
    print("-" * 76)
    for expense in sorted(expenses, key=lambda item: (item["date"], str(item["id"]))):
        print(
            f"{str(expense['id']):<12} {expense['date']:<12} "
            f"{expense['category']:<16} {float(expense['amount']):>12.2f} "
            f"{expense['payment_method']:<14} "
            f"{expense['description']}"
        )
    return expenses


def _prompt_replacement(
    label: str,
    current: Any,
    validator: Callable[[object], Any],
) -> Any:
    """Prompt for an optional replacement value and validate it when supplied."""
    response = input(f"{label} [{current}]: ").strip()
    while response:
        try:
            return validator(response)
        except ValueError as error:
            print_warning(str(error))
            response = input(f"Enter {label.lower()}: ").strip()
    return current


def edit_expense(file_path: Path = EXPENSES_FILE) -> bool:
    """Edit a selected expense while retaining fields left blank."""
    print_heading("Edit Expense")
    transactions = load_transactions(file_path)
    expense_id = prompt_for_expense_id("Expense ID to edit: ")
    expense = _find_expense(transactions, expense_id)
    if expense is None:
        print_warning("No expense was found with that ID.")
        return False

    print("Press Enter to keep the current value.")
    expense["amount"] = _prompt_replacement(
        "Amount", expense["amount"], validate_positive_amount
    )
    expense["category"] = _prompt_replacement(
        "Category", expense["category"], validate_category
    )
    expense["date"] = _prompt_replacement("Date", expense["date"], validate_date)
    expense["description"] = input(
        f"Description [{expense['description']}]: "
    ).strip() or expense["description"]
    expense["payment_method"] = _prompt_replacement(
        "Payment method", expense["payment_method"], validate_payment_method
    )
    save_json(file_path, transactions)
    print_success(f"Expense {expense_id} updated.")
    return True


def delete_expense(file_path: Path = EXPENSES_FILE) -> bool:
    """Ask for confirmation before deleting a selected expense."""
    print_heading("Delete Expense")
    transactions = load_transactions(file_path)
    expense_id = prompt_for_expense_id("Expense ID to delete: ")
    expense = _find_expense(transactions, expense_id)
    if expense is None:
        print_warning("No expense was found with that ID.")
        return False

    print(
        f"Delete {expense['category']} expense of "
        f"{float(expense['amount']):.2f} (ID {expense_id})?"
    )
    if input("Type 'yes' to confirm: ").strip().casefold() != "yes":
        print_warning("Deletion cancelled; no data was changed.")
        return False

    transactions.remove(expense)
    for next_id, transaction in enumerate(transactions, start=1):
        transaction["id"] = next_id
    save_json(file_path, transactions)
    print_success(f"Expense {expense_id} deleted.")
    return True


def search_expenses(file_path: Path = EXPENSES_FILE) -> list[dict[str, Any]]:
    """Search expenses by date, category, or description."""
    print_heading("Search Expenses")
    expenses = load_expenses(file_path)
    query = input("Enter a date, category, or description: ").strip().casefold()
    if not query:
        print_warning("Enter a search term.")
        return []
    matches = [
        expense
        for expense in expenses
        if query
        in " ".join(
            str(expense.get(field, ""))
            for field in ("date", "category", "description")
        ).casefold()
    ]
    if not matches:
        print("No matching expenses were found.")
        return []
    for expense in matches:
        print(
            f"{expense['date']} | {expense['category']} | "
            f"{float(expense['amount']):.2f} | {expense['description']} "
            f"| ID: {expense['id']}"
        )
    return matches
