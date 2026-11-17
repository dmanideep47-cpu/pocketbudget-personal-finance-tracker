"""Generate PocketBudget documentation images from real functions and demo data."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Iterable
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analytics import analyze_spending, export_monthly_csv, monthly_statement
from budget_manager import show_budget_status
from constants import CHART_COLORS
from expense_manager import add_expense
from file_handler import (
    load_budgets,
    load_expenses,
    load_income,
    load_transactions,
    save_json,
)
from terminal_ui import display_menu
from visualizations import CHART_NAMES, show_charts

DEMO_MONTH = "2026-04"
DEMO_TRANSACTIONS: list[dict[str, Any]] = [
    {
        "id": 1,
        "type": "expense",
        "amount": 45.0,
        "category": "Food",
        "date": "2026-04-01",
        "description": "Groceries",
        "payment_method": "Card",
    },
    {
        "id": 2,
        "type": "expense",
        "amount": 20.0,
        "category": "Travel",
        "date": "2026-04-02",
        "description": "Bus fare",
        "payment_method": "UPI",
    },
    {
        "id": 3,
        "type": "expense",
        "amount": 25.0,
        "category": "Food",
        "date": "2026-04-03",
        "description": "Lunch",
        "payment_method": "Cash",
    },
    {
        "id": 4,
        "type": "expense",
        "amount": 220.0,
        "category": "Bills",
        "date": "2026-04-05",
        "description": "Monthly phone and internet",
        "payment_method": "UPI",
    },
    {
        "id": 5,
        "type": "expense",
        "amount": 130.0,
        "category": "Shopping",
        "date": "2026-04-08",
        "description": "Running shoes",
        "payment_method": "Card",
    },
    {
        "id": 6,
        "type": "expense",
        "amount": 32.0,
        "category": "Food",
        "date": "2026-04-09",
        "description": "Lunch with classmates",
        "payment_method": "UPI",
    },
    {
        "id": 7,
        "type": "expense",
        "amount": 75.0,
        "category": "Education",
        "date": "2026-04-11",
        "description": "Course materials",
        "payment_method": "Card",
    },
    {
        "id": 8,
        "type": "expense",
        "amount": 90.0,
        "category": "Entertainment",
        "date": "2026-04-13",
        "description": "Cinema tickets",
        "payment_method": "UPI",
    },
    {
        "id": 9,
        "type": "expense",
        "amount": 35.0,
        "category": "Health",
        "date": "2026-04-16",
        "description": "Pharmacy",
        "payment_method": "Cash",
    },
    {
        "id": 10,
        "type": "expense",
        "amount": 55.0,
        "category": "Food",
        "date": "2026-04-18",
        "description": "Weekend groceries",
        "payment_method": "Card",
    },
    {
        "id": 11,
        "type": "expense",
        "amount": 55.0,
        "category": "Shopping",
        "date": "2026-04-20",
        "description": "Notebook and supplies",
        "payment_method": "Cash",
    },
    {
        "id": 12,
        "type": "expense",
        "amount": 22.0,
        "category": "Travel",
        "date": "2026-04-22",
        "description": "Train fare",
        "payment_method": "UPI",
    },
    {
        "id": 13,
        "type": "expense",
        "amount": 20.0,
        "category": "Others",
        "date": "2026-04-26",
        "description": "Stationery",
        "payment_method": "Cash",
    },
    {
        "id": 14,
        "type": "income",
        "amount": 1500.0,
        "date": "2026-04-01",
        "source": "Part-time work",
        "description": "April salary",
    },
    {
        "id": 15,
        "type": "income",
        "amount": 300.0,
        "date": "2026-04-15",
        "source": "Scholarship",
        "description": "Monthly scholarship",
    },
]
DEMO_BUDGETS: dict[str, dict[str, float]] = {
    DEMO_MONTH: {
        "Food": 180.0,
        "Travel": 60.0,
        "Shopping": 150.0,
        "Education": 50.0,
        "Bills": 200.0,
        "Entertainment": 60.0,
        "Health": 40.0,
        "Others": 10.0,
    }
}
SCREENSHOT_NAMES = (
    "main-menu.png",
    "add-expense.png",
    "error-handling.png",
    "budget-status.png",
    "monthly-report.png",
    "spending-analysis.png",
    "csv-export.png",
    "pytest-passed.png",
    "github-repository.png",
)
CHART_SCREENSHOT_NAMES = (
    "category-pie-chart.png",
    "daily-spend-line-chart.png",
    "budget-vs-actual-chart.png",
    "monthly-category-bar-chart.png",
    "savings-summary-chart.png",
)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _scripted_input(responses: Iterable[str]) -> Callable[[str], str]:
    """Return an input function that echoes demo responses like a real terminal."""
    iterator = iter(responses)

    def read_response(prompt: str = "") -> str:
        """Print the prompt and next scripted response, then return that response."""
        try:
            response = next(iterator)
        except StopIteration as error:
            raise RuntimeError("The screenshot demo ran out of scripted input.") from error
        print(f"{prompt}{response}")
        return response

    return read_response


def _capture_terminal(action: Callable[[], object]) -> str:
    """Capture the actual stdout produced by a PocketBudget operation."""
    output = StringIO()
    with redirect_stdout(output):
        action()
    return _redact_local_paths(output.getvalue())


def _redact_local_paths(text: str) -> str:
    """Replace personal and temporary machine paths in documentation output."""
    replacements = (
        (tempfile.gettempdir(), "<temp>"),
        (str(PROJECT_ROOT), "<PocketBudget>"),
        (str(Path.home()), "~"),
    )
    for local_path, replacement in replacements:
        text = text.replace(local_path, replacement)
        text = text.replace(local_path.replace("\\", "/"), replacement)
    return text


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a readable monospaced or sans-serif system font with safe fallbacks."""
    windows_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    candidates = (
        windows_fonts / ("consolab.ttf" if bold else "consola.ttf"),
        windows_fonts / ("courbd.ttf" if bold else "cour.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/Library/Fonts/Courier New.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _wrap_terminal_text(text: str, width: int = 122) -> list[str]:
    """Remove ANSI color codes and wrap captured output to a fixed terminal width."""
    cleaned = ANSI_ESCAPE.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
    wrapped: list[str] = []
    for line in cleaned.split("\n"):
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(
            textwrap.wrap(
                line,
                width=width,
                break_long_words=True,
                break_on_hyphens=False,
                subsequent_indent="   ",
            )
        )
    return wrapped


def render_terminal_screenshot(
    filename: str,
    title: str,
    terminal_text: str,
) -> Path:
    """Render captured application stdout inside a Windows Terminal-style frame."""
    # The frame is Windows-specific; captured stdout remains the source of truth.
    screenshot_dir = PROJECT_ROOT / "docs" / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    output_path = screenshot_dir / filename

    # Keep the terminal presentation separate from application output. The text
    # below the title bar is always captured from the real PocketBudget functions.
    width = 1600
    scale = 2
    margin = 24
    title_bar_height = 58
    padding_top = 28
    line_height = 31
    body_lines = _wrap_terminal_text(terminal_text, width=116)
    content_height = max(300, padding_top + max(1, len(body_lines)) * line_height + 24)
    height = margin * 2 + title_bar_height + content_height

    image = Image.new("RGB", (width * scale, height * scale), "#0C0C0C")
    draw = ImageDraw.Draw(image)
    panel = (
        margin * scale,
        margin * scale,
        (width - margin) * scale,
        (height - margin) * scale,
    )
    draw.rounded_rectangle(
        panel,
        radius=9 * scale,
        fill="#0C0C0C",
        outline="#343434",
        width=1 * scale,
    )

    # Windows Terminal tab/title bar. No macOS traffic-light controls.
    title_bottom = panel[1] + title_bar_height * scale
    draw.rounded_rectangle(
        (panel[0], panel[1], panel[2], title_bottom),
        radius=9 * scale,
        fill="#202020",
    )
    draw.rectangle(
        (panel[0], panel[1] + 28 * scale, panel[2], title_bottom),
        fill="#202020",
    )

    # Small PowerShell app tile.
    icon_left = (margin + 16) * scale
    icon_top = (margin + 17) * scale
    icon_size = 23 * scale
    draw.rounded_rectangle(
        (icon_left, icon_top, icon_left + icon_size, icon_top + icon_size),
        radius=4 * scale,
        fill="#2675C9",
    )
    icon_font = _load_font(14 * scale, bold=True)
    draw.text(
        (icon_left + 3 * scale, icon_top + 1 * scale),
        ">_",
        font=icon_font,
        fill="#FFFFFF",
    )

    title_font = _load_font(15 * scale)
    draw.text(
        ((margin + 48) * scale, (margin + 18) * scale),
        "Windows PowerShell",
        font=title_font,
        fill="#F3F3F3",
    )
    draw.text(
        ((margin + 285) * scale, (margin + 14) * scale),
        "×",
        font=_load_font(22 * scale),
        fill="#D0D0D0",
    )
    draw.text(
        ((margin + 350) * scale, (margin + 12) * scale),
        "+",
        font=_load_font(24 * scale),
        fill="#E5E5E5",
    )
    draw.text(
        ((width - margin - 160) * scale, (margin + 17) * scale),
        "—    □    ×",
        font=_load_font(17 * scale),
        fill="#D8D8D8",
    )

    body_font = _load_font(16 * scale)
    text_x = (margin + 22) * scale
    text_y = (margin + title_bar_height + padding_top) * scale
    for line in body_lines:
        draw.text(
            (text_x, text_y),
            line,
            font=body_font,
            fill="#E6E6E6",
        )
        text_y += line_height * scale

    resampling = getattr(Image, "Resampling", Image)
    image = image.resize((width, height), resample=resampling.LANCZOS)
    image.save(output_path, format="PNG", optimize=True)
    return output_path

def render_repository_preview() -> Path:
    """Draw a GitHub-inspired repository illustration without browser capture."""
    screenshot_dir = PROJECT_ROOT / "docs" / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    output_path = screenshot_dir / "github-repository.png"
    width, height = 1800, 1220
    image = Image.new("RGB", (width, height), "#0D1117")
    draw = ImageDraw.Draw(image)
    regular = _load_font(22)
    small = _load_font(17)
    bold = _load_font(28, bold=True)
    mono = _load_font(19)

    draw.rectangle((0, 0, width, 72), fill="#161B22")
    draw.text((46, 22), "GitHub", font=bold, fill="#F0F6FC")
    draw.text((170, 27), "Explore     Topics     Marketplace", font=small, fill="#C9D1D9")
    draw.text((width - 520, 27), "Locally generated repository preview", font=small, fill="#8B949E")

    draw.text((72, 118), "PocketBudget", font=bold, fill="#58A6FF")
    draw.text(
        (72, 164),
        "Personal Expense Tracker and Budget Advisor",
        font=regular,
        fill="#E6EDF3",
    )
    draw.text(
        (72, 205),
        "A modular Python terminal app for expenses, budgets, reports, and financial insights.",
        font=small,
        fill="#8B949E",
    )
    draw.rounded_rectangle((72, 248, 1728, 298), radius=12, fill="#161B22", outline="#30363D")
    draw.text((96, 263), "Topics:", font=small, fill="#8B949E")
    topic_x = 190
    for topic in ("python", "cli", "budget-tracker", "pandas", "matplotlib", "pytest"):
        topic_width = int(draw.textlength(topic, font=small)) + 30
        draw.rounded_rectangle(
            (topic_x, 258, topic_x + topic_width, 288),
            radius=12,
            fill="#1F3A5F",
        )
        draw.text((topic_x + 15, 263), topic, font=small, fill="#79C0FF")
        topic_x += topic_width + 12

    left, top, right, bottom = 72, 332, 775, 1146
    draw.rounded_rectangle((left, top, right, bottom), radius=10, fill="#0D1117", outline="#30363D", width=2)
    draw.rectangle((left, top, right, top + 58), fill="#161B22")
    draw.text((left + 24, top + 17), "Repository files", font=small, fill="#E6EDF3")
    tree = (
        "PocketBudget/",
        "|-- main.py",
        "|-- constants.py",
        "|-- validations.py",
        "|-- file_handler.py",
        "|-- expense_manager.py",
        "|-- budget_manager.py",
        "|-- analytics.py",
        "|-- visualizations.py",
        "|-- advisor.py",
        "|-- income_manager.py",
        "|-- terminal_ui.py",
        "|-- data/ (.gitkeep; JSON created at runtime)",
        "|-- exports/",
        "|-- charts/",
        "|-- tests/test_pocketbudget.py",
        "|-- scripts/generate_screenshots.py",
        "|-- docs/screenshots/",
        "|-- README.md",
        "`-- LICENSE",
    )
    y = top + 86
    for line in tree:
        draw.text((left + 28, y), line, font=mono, fill="#C9D1D9")
        y += 33

    readme_left, readme_top, readme_right, readme_bottom = 812, 332, 1728, 1146
    draw.rounded_rectangle(
        (readme_left, readme_top, readme_right, readme_bottom),
        radius=10,
        fill="#0D1117",
        outline="#30363D",
        width=2,
    )
    draw.rectangle(
        (readme_left, readme_top, readme_right, readme_top + 58),
        fill="#161B22",
    )
    draw.text((readme_left + 24, readme_top + 17), "README.md  |  Preview", font=small, fill="#E6EDF3")
    readme_lines = (
        ("PocketBudget", bold, "#E6EDF3"),
        ("Personal Expense Tracker and Budget Advisor", regular, "#C9D1D9"),
        ("", small, "#C9D1D9"),
        ("Track every purchase. Plan each month. Spend with confidence.", regular, "#58A6FF"),
        ("", small, "#C9D1D9"),
        ("A terminal-first personal finance project built with Python.", small, "#C9D1D9"),
        ("", small, "#C9D1D9"),
        ("FEATURES", bold, "#E6EDF3"),
        ("- Expense and income tracking with JSON persistence", small, "#C9D1D9"),
        ("- Category budgets, monthly reports, and a financial advisor", small, "#C9D1D9"),
        ("- Pandas analysis and Excel-friendly CSV exports", small, "#C9D1D9"),
        ("- Five Matplotlib charts with clear budget comparisons", small, "#C9D1D9"),
        ("- Isolated pytest suite and locally generated documentation images", small, "#C9D1D9"),
        ("", small, "#C9D1D9"),
        ("QUICK START", bold, "#E6EDF3"),
        ("python -m pip install -r requirements.txt", mono, "#7EE787"),
        ("python main.py", mono, "#7EE787"),
        ("python -m pytest -v", mono, "#7EE787"),
        ("", small, "#C9D1D9"),
        ("Terminal interface only - no GUI, web app, or database.", small, "#8B949E"),
        ("Generated illustration; not a GitHub browser screenshot.", small, "#8B949E"),
    )
    y = readme_top + 86
    for text, font, color in readme_lines:
        draw.text((readme_left + 28, y), text, font=font, fill=color)
        y += 36 if font is bold else 31

    image.save(output_path, format="PNG", optimize=True)
    return output_path


def generate_screenshots() -> list[Path]:
    """Create all terminal screenshots and charts from isolated demo records."""
    screenshot_dir = PROJECT_ROOT / "docs" / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    with tempfile.TemporaryDirectory(prefix="pocketbudget-demo-") as temporary_dir:
        temporary_root = Path(temporary_dir)
        transaction_file = temporary_root / "data" / "expenses.json"
        budget_file = temporary_root / "data" / "budgets.json"
        save_json(transaction_file, DEMO_TRANSACTIONS)
        save_json(budget_file, DEMO_BUDGETS)
        load_transactions(transaction_file)
        expenses = load_expenses(transaction_file)
        incomes = load_income(transaction_file)
        budgets = load_budgets(budget_file)

        generated.append(
            render_terminal_screenshot(
                "main-menu.png",
                "Main Menu",
                _capture_terminal(display_menu),
            )
        )

        add_demo_file = temporary_root / "add-expense.json"
        save_json(add_demo_file, [])
        add_output = _capture_terminal(
            lambda: _add_expense_with_input(
                add_demo_file,
                ["18.50", "Food", "2026-04-27", "Coffee and a sandwich", "UPI"],
            )
        )
        generated.append(
            render_terminal_screenshot("add-expense.png", "Add Expense", add_output)
        )

        error_demo_file = temporary_root / "error-expense.json"
        save_json(error_demo_file, [])
        error_output = _capture_terminal(
            lambda: _add_expense_with_input(
                error_demo_file,
                [
                    "abc",
                    "18.50",
                    "Food",
                    "2026-04-27",
                    "Coffee and a sandwich",
                    "UPI",
                ],
            )
        )
        generated.append(
            render_terminal_screenshot(
                "error-handling.png",
                "Input Validation",
                error_output,
            )
        )

        with (
            patch("budget_manager.load_expenses", return_value=expenses),
            patch("budget_manager.load_budgets", return_value=budgets),
            patch("builtins.input", side_effect=_scripted_input([DEMO_MONTH])),
        ):
            budget_output = _capture_terminal(show_budget_status)
        generated.append(
            render_terminal_screenshot(
                "budget-status.png",
                "Budget Status",
                budget_output,
            )
        )

        report_output = _capture_terminal(
            lambda: monthly_statement(DEMO_MONTH, expenses)
        )
        generated.append(
            render_terminal_screenshot(
                "monthly-report.png",
                "Monthly Expense Report",
                report_output,
            )
        )

        analysis_output = _capture_terminal(
            lambda: analyze_spending(DEMO_MONTH, expenses)
        )
        generated.append(
            render_terminal_screenshot(
                "spending-analysis.png",
                "Spending Analysis",
                analysis_output,
            )
        )

        export_directory = temporary_root / "exports"
        export_output = _capture_terminal(
            lambda: _export_and_preview(
                DEMO_MONTH,
                expenses,
                export_directory,
            )
        )
        generated.append(
            render_terminal_screenshot(
                "csv-export.png",
                "Monthly CSV Export",
                export_output,
            )
        )

        pytest_output = _run_pytest()
        generated.append(
            render_terminal_screenshot(
                "pytest-passed.png",
                "Automated Tests",
                pytest_output,
            )
        )

        temporary_charts = temporary_root / "charts"
        _capture_terminal(
            lambda: show_charts(
                DEMO_MONTH,
                expenses,
                incomes,
                budgets,
                temporary_charts,
                display=False,
            )
        )
        for source_name, target_name in zip(CHART_NAMES, CHART_SCREENSHOT_NAMES):
            source_path = temporary_charts / source_name
            if not source_path.is_file():
                raise FileNotFoundError(f"Expected chart was not generated: {source_path}")
            target_path = screenshot_dir / target_name
            shutil.copyfile(source_path, target_path)
            generated.append(target_path)

    generated.append(render_repository_preview())
    expected_names = set(SCREENSHOT_NAMES + CHART_SCREENSHOT_NAMES)
    generated_names = {path.name for path in generated}
    if generated_names != expected_names:
        missing = sorted(expected_names - generated_names)
        unexpected = sorted(generated_names - expected_names)
        raise RuntimeError(
            f"Screenshot set mismatch; missing={missing}, unexpected={unexpected}"
        )
    print(f"Generated {len(generated)} documentation images in {screenshot_dir}.")
    for path in generated:
        print(f"  {path.name} ({path.stat().st_size:,} bytes)")
    return generated


def _add_expense_with_input(file_path: Path, responses: list[str]) -> None:
    """Run the actual expense workflow with deterministic demo input."""
    with patch("builtins.input", side_effect=_scripted_input(responses)):
        add_expense(file_path)


def _export_and_preview(
    month: str,
    expenses: list[dict[str, Any]],
    export_directory: Path,
) -> None:
    """Export a real demo CSV and append its contents to captured terminal output."""
    output = export_monthly_csv(month, expenses, export_directory)
    print("\nCSV preview:")
    with output.open("r", encoding="utf-8-sig") as csv_file:
        for line_number, line in enumerate(csv_file):
            if line_number == 6:
                print("...")
                break
            print(line.rstrip("\n"))


def _run_pytest() -> str:
    """Run the project's actual pytest command and return its complete output."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = _redact_local_paths(
        "$ python -m pytest -v\n" + result.stdout + result.stderr
    )
    if result.returncode != 0:
        raise RuntimeError(
            "The screenshot test run failed. Output follows:\n" + output
        )
    return output


if __name__ == "__main__":
    generate_screenshots()
