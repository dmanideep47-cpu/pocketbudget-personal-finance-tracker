"""Safe JSON storage, legacy migration, and backups for PocketBudget data."""

import json
import logging
import math
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from constants import BUDGETS_FILE, DATA_DIR, EXPENSES_FILE
from validations import validate_category, validate_date, validate_month

LOGGER = logging.getLogger(__name__)
EXPENSE_REQUIRED_FIELDS = {
    "id",
    "type",
    "amount",
    "category",
    "date",
    "description",
    "payment_method",
}
INCOME_REQUIRED_FIELDS = {"id", "type", "amount", "date", "description", "source"}


class DataFileError(RuntimeError):
    """Report a data file that cannot safely be read or validated."""


def ensure_storage() -> None:
    """Create missing JSON files and validate/migrate stored transactions."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for file_path, default_value in (
        (EXPENSES_FILE, []),
        (BUDGETS_FILE, {}),
    ):
        if not file_path.exists():
            save_json(file_path, default_value)
    load_transactions()
    load_budgets()


def load_json(file_path: Path, default_value: Any) -> Any:
    """Load JSON, or initialize a missing file without replacing bad data."""
    path = Path(file_path)
    try:
        with path.open("r", encoding="utf-8") as data_file:
            return json.load(data_file)
    except FileNotFoundError:
        LOGGER.warning("Data file %s was missing; initializing it.", path)
        save_json(path, default_value)
        return default_value
    except json.JSONDecodeError as error:
        LOGGER.exception("Corrupted JSON in %s.", path)
        raise DataFileError(
            f"{path.name} contains invalid JSON. It was not overwritten; "
            f"restore a valid file or inspect {path.with_suffix(path.suffix + '.bak')}."
        ) from error
    except OSError as error:
        LOGGER.exception("Could not read data file %s.", path)
        raise DataFileError(f"Could not read {path}: {error}") from error


def save_json(file_path: Path, data: Any) -> None:
    """Atomically save JSON and back up the previous file before replacing it."""
    path = Path(file_path)
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(
                data,
                temporary_file,
                indent=4,
                ensure_ascii=False,
                allow_nan=False,
            )
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        if path.exists():
            backup_path = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup_path)
        os.replace(temporary_path, path)
    except (OSError, TypeError, ValueError):
        LOGGER.exception("Could not safely save data file %s.", path)
        raise
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                LOGGER.exception("Could not remove temporary file %s.", temporary_path)
                raise


def _normalize_transactions(records: Any, file_path: Path) -> list[dict[str, Any]]:
    """Migrate older transaction records and enforce the shared numeric ID space."""
    if not isinstance(records, list):
        raise DataFileError(f"{file_path.name} must contain a JSON list.")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise DataFileError(
                f"Transaction {index + 1} in {file_path.name} must be an object."
            )
        item = dict(record)
        item.setdefault("type", "expense")
        transaction_type = item.get("type")
        if transaction_type not in {"expense", "income"}:
            raise DataFileError(
                f"Transaction {index + 1} in {file_path.name} has an invalid type."
            )
        if transaction_type == "expense":
            item.setdefault("category", "Others")
            item.setdefault("payment_method", "Cash")
        else:
            item.setdefault("source", "Other")
        item.setdefault("description", "")

        record_id = item.get("id")
        if isinstance(record_id, int) and not isinstance(record_id, bool) and record_id > 0:
            if record_id not in seen_ids:
                seen_ids.add(record_id)
                normalized.append(item)
                continue
        normalized.append(item)

    next_id = max(seen_ids, default=0) + 1
    assigned: set[int] = set()
    for item in normalized:
        record_id = item.get("id")
        if (
            isinstance(record_id, int)
            and not isinstance(record_id, bool)
            and record_id > 0
            and record_id not in assigned
        ):
            assigned.add(record_id)
            continue
        while next_id in assigned:
            next_id += 1
        item["id"] = next_id
        assigned.add(next_id)
        next_id += 1
    return normalized


def _validate_transactions(
    transactions: list[dict[str, Any]],
    file_path: Path,
) -> None:
    """Reject invalid transaction fields, amounts, dates, and duplicate IDs."""
    seen_ids: set[int] = set()
    for index, transaction in enumerate(transactions):
        transaction_type = transaction["type"]
        required_fields = (
            EXPENSE_REQUIRED_FIELDS
            if transaction_type == "expense"
            else INCOME_REQUIRED_FIELDS
        )
        if not required_fields.issubset(transaction):
            raise DataFileError(
                f"Transaction {index + 1} in {file_path.name} is missing required fields."
            )
        record_id = transaction["id"]
        if (
            not isinstance(record_id, int)
            or isinstance(record_id, bool)
            or record_id <= 0
            or record_id in seen_ids
        ):
            raise DataFileError(
                f"Transaction {index + 1} in {file_path.name} has an invalid ID."
            )
        seen_ids.add(record_id)
        if isinstance(transaction["amount"], bool):
            raise DataFileError(
                f"Transaction {record_id} in {file_path.name} has an invalid amount."
            )
        try:
            amount = float(transaction["amount"])
        except (TypeError, ValueError) as error:
            raise DataFileError(
                f"Transaction {record_id} in {file_path.name} has an invalid amount."
            ) from error
        if not math.isfinite(amount) or amount <= 0:
            raise DataFileError(
                f"Transaction {record_id} in {file_path.name} must have a positive amount."
            )
        try:
            validate_date(transaction["date"])
            if transaction_type == "expense":
                validate_category(transaction["category"])
        except ValueError as error:
            raise DataFileError(
                f"Transaction {record_id} in {file_path.name} has invalid details: {error}"
            ) from error


def load_transactions(file_path: Path = EXPENSES_FILE) -> list[dict[str, Any]]:
    """Load, migrate, validate, and return all expense and income transactions."""
    path = Path(file_path)
    records = load_json(path, [])
    transactions = _normalize_transactions(records, path)
    _validate_transactions(transactions, path)
    if transactions != records:
        LOGGER.info("Migrating legacy transaction data in %s.", path)
        save_json(path, transactions)
    return transactions


def load_expenses(file_path: Path = EXPENSES_FILE) -> list[dict[str, Any]]:
    """Load transactions and return expense records only."""
    return [
        transaction
        for transaction in load_transactions(file_path)
        if transaction["type"] == "expense"
    ]


def next_transaction_id(transactions: list[dict[str, Any]]) -> int:
    """Return the next unique integer ID for a shared transaction list."""
    return max(
        (int(transaction["id"]) for transaction in transactions),
        default=0,
    ) + 1


def load_income(file_path: Path = EXPENSES_FILE) -> list[dict[str, Any]]:
    """Load transactions and return income records only."""
    return [
        transaction
        for transaction in load_transactions(file_path)
        if transaction["type"] == "income"
    ]


def load_budgets(file_path: Path = BUDGETS_FILE) -> dict[str, Any]:
    """Load and validate month-wise category budget data."""
    path = Path(file_path)
    budgets = load_json(path, {})
    if not isinstance(budgets, dict):
        raise DataFileError(f"{path.name} must contain a JSON dictionary.")
    for month, category_budgets in budgets.items():
        try:
            validate_month(month)
        except ValueError as error:
            raise DataFileError(f"Budget month {month!r} is invalid.") from error
        if not isinstance(category_budgets, dict):
            raise DataFileError(f"Budgets for {month} must be a category dictionary.")
        for category, amount in category_budgets.items():
            try:
                validate_category(category)
                numeric_amount = float(amount)
            except (TypeError, ValueError) as error:
                raise DataFileError(
                    f"Budget for {category!r} in {month} is invalid."
                ) from error
            if not math.isfinite(numeric_amount) or numeric_amount <= 0:
                raise DataFileError(
                    f"Budget for {category!r} in {month} must be positive."
                )
    return budgets
