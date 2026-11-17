"""Reusable input validation and retrying prompts for the terminal UI."""

import math
import re
from datetime import datetime
from typing import Callable, TypeVar

from constants import EXPENSE_CATEGORIES, PAYMENT_METHODS
from terminal_ui import print_warning

T = TypeVar("T")


def validate_positive_amount(value: object) -> float:
    """Convert input to a finite positive amount or raise ``ValueError``."""
    if isinstance(value, bool):
        raise ValueError("Amount must be a number, not a boolean.")
    try:
        amount = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Enter a number, such as 125.50.") from error
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Amount must be a positive number.")
    return amount


def validate_date(value: object) -> str:
    """Validate a real calendar date written exactly as YYYY-MM-DD."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Date must use YYYY-MM-DD format.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("Enter a real date in YYYY-MM-DD format.") from error
    return value


def validate_month(value: object) -> str:
    """Validate a real calendar month written exactly as YYYY-MM."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("Month must use YYYY-MM format.")
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError as error:
        raise ValueError("Enter a real month in YYYY-MM format.") from error
    return value


def validate_category(value: object) -> str:
    """Return a canonical allowed expense category or raise ``ValueError``."""
    if isinstance(value, str):
        for category in EXPENSE_CATEGORIES:
            if value.strip().casefold() == category.casefold():
                return category
    choices = ", ".join(sorted(EXPENSE_CATEGORIES))
    raise ValueError(f"Choose one of these categories: {choices}.")


def validate_payment_method(value: object) -> str:
    """Return a canonical allowed payment method or raise ``ValueError``."""
    if isinstance(value, str):
        for method in PAYMENT_METHODS:
            if value.strip().casefold() == method.casefold():
                return method
    raise ValueError(f"Payment method must be: {', '.join(PAYMENT_METHODS)}.")


def validate_expense_id(value: object) -> int:
    """Validate a positive integer transaction ID."""
    if isinstance(value, bool):
        raise ValueError("Expense ID must be a positive whole number.")
    try:
        expense_id = int(str(value).strip())
    except (TypeError, ValueError) as error:
        raise ValueError("Expense ID must be a positive whole number.") from error
    if expense_id <= 0 or str(value).strip() != str(expense_id):
        raise ValueError("Expense ID must be a positive whole number.")
    return expense_id


def prompt_validated(prompt: str, validator: Callable[[object], T]) -> T:
    """Repeat an input prompt until its validator accepts the response."""
    while True:
        try:
            return validator(input(prompt).strip())
        except ValueError as error:
            print_warning(str(error))


def prompt_for_amount(prompt: str = "Amount: ") -> float:
    """Prompt until the user enters a valid positive amount."""
    return prompt_validated(prompt, validate_positive_amount)


def prompt_for_date(prompt: str = "Date (YYYY-MM-DD): ") -> str:
    """Prompt until the user enters a valid calendar date."""
    return prompt_validated(prompt, validate_date)


def prompt_for_month(prompt: str = "Month (YYYY-MM): ") -> str:
    """Prompt until the user enters a valid calendar month."""
    return prompt_validated(prompt, validate_month)


def prompt_for_category(prompt: str = "Category: ") -> str:
    """Display categories and prompt until one is selected."""
    print("Categories: " + ", ".join(sorted(EXPENSE_CATEGORIES)))
    return prompt_validated(prompt, validate_category)


def prompt_for_payment_method(prompt: str = "Payment method: ") -> str:
    """Display supported payment methods and prompt until one is selected."""
    print("Payment methods: " + ", ".join(PAYMENT_METHODS))
    return prompt_validated(prompt, validate_payment_method)


def prompt_for_expense_id(prompt: str = "Expense ID: ") -> int:
    """Prompt until a non-empty expense ID is supplied."""
    return prompt_validated(prompt, validate_expense_id)
