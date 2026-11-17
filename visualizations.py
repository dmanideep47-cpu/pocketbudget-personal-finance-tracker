"""Presentation-ready monthly Matplotlib charts saved to the charts directory."""

from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib.pyplot as plt

from analytics import expenses_dataframe, incomes_dataframe
from budget_manager import _budget_entry
from constants import (
    CHART_BACKGROUND,
    CHART_COLORS,
    CHART_DPI,
    CHARTS_DIR,
    FIGURE_SIZE,
    GRID_COLOR,
    OVER_BUDGET_COLOR,
    TEXT_COLOR,
)
from file_handler import load_budgets, load_expenses, load_income
from terminal_ui import print_heading, print_success
from validations import prompt_for_month, validate_month

CHART_NAMES = (
    "category_pie_chart.png",
    "daily_spend_line_chart.png",
    "budget_vs_actual_chart.png",
    "monthly_category_bar_chart.png",
    "savings_summary_chart.png",
)


def _empty_chart(axis: Any, message: str) -> None:
    """Show an explanatory placeholder when a chart has no records."""
    axis.text(0.5, 0.5, message, ha="center", va="center", color=TEXT_COLOR)
    axis.set_xticks([])
    axis.set_yticks([])


def _add_bar_labels(axis: Any, bars: Any) -> None:
    """Add readable numeric labels above each bar."""
    for bar in bars:
        axis.annotate(
            f"{bar.get_height():.2f}",
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
        )


def _budget_values(
    month: str,
    budgets: Mapping[str, Any],
) -> dict[str, float]:
    """Return the month's category budget limits."""
    entry = _budget_entry(budgets, month)
    return {
        str(category): float(limit)
        for category, limit in entry.get("categories", {}).items()
    }


def show_charts(
    month: str | None = None,
    expenses: Iterable[Mapping[str, Any]] | None = None,
    incomes: Iterable[Mapping[str, Any]] | None = None,
    budgets: Mapping[str, Any] | None = None,
    charts_dir: Path = CHARTS_DIR,
    display: bool = True,
) -> list[Path]:
    """Save five monthly charts and display them when the backend allows it."""
    selected_month = validate_month(month) if month is not None else prompt_for_month()
    expense_records = load_expenses() if expenses is None else list(expenses)
    income_records = load_income() if incomes is None else list(incomes)
    budget_records = load_budgets() if budgets is None else budgets
    expense_frame = expenses_dataframe(expense_records)
    income_frame = incomes_dataframe(income_records)
    month_frame = expense_frame.loc[
        expense_frame["date"].notna()
        & expense_frame["date"].dt.strftime("%Y-%m").eq(selected_month)
    ].copy()
    income_month = income_frame.loc[
        income_frame["date"].notna()
        & income_frame["date"].dt.strftime("%Y-%m").eq(selected_month)
    ].copy()
    category_totals = month_frame.groupby("category")["amount"].sum().sort_values(
        ascending=False
    )
    daily_totals = month_frame.groupby(
        month_frame["date"].dt.strftime("%Y-%m-%d")
    )["amount"].sum()
    category_budgets = _budget_values(selected_month, budget_records)
    output_dir = Path(charts_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with plt.rc_context(
        {
            "figure.facecolor": CHART_BACKGROUND,
            "axes.facecolor": CHART_BACKGROUND,
            "axes.edgecolor": GRID_COLOR,
            "axes.labelcolor": TEXT_COLOR,
            "axes.titlecolor": TEXT_COLOR,
            "text.color": TEXT_COLOR,
            "xtick.color": TEXT_COLOR,
            "ytick.color": TEXT_COLOR,
            "grid.color": GRID_COLOR,
            "font.size": 10,
        }
    ):
        figures: list[Any] = []
        figure, axis = plt.subplots(figsize=FIGURE_SIZE)
        if category_totals.empty:
            _empty_chart(axis, f"No expenses recorded for {selected_month}")
        else:
            wedges, _, _ = axis.pie(
                category_totals.values,
                labels=None,
                colors=CHART_COLORS[: len(category_totals)],
                autopct=lambda percentage: (
                    f"{percentage:.1f}%" if percentage >= 5 else ""
                ),
                pctdistance=0.68,
                startangle=90,
                wedgeprops={"edgecolor": CHART_BACKGROUND, "linewidth": 1.5},
                textprops={"fontsize": 9, "color": TEXT_COLOR},
            )
            axis.axis("equal")
            total_spend = float(category_totals.sum())
            legend_labels = [
                f"{category} ({float(amount) / total_spend:.1%})"
                for category, amount in category_totals.items()
            ]
            axis.legend(
                wedges,
                legend_labels,
                title="Category",
                loc="center left",
                bbox_to_anchor=(1.0, 0.5),
                frameon=False,
                fontsize=9,
            )
        axis.set_title(f"Expense Distribution by Category | {selected_month}")
        figures.append(figure)

        figure, axis = plt.subplots(figsize=FIGURE_SIZE)
        if daily_totals.empty:
            _empty_chart(axis, f"No daily spending recorded for {selected_month}")
        else:
            x_positions = list(range(len(daily_totals)))
            axis.plot(
                x_positions,
                daily_totals.values,
                marker="o",
                linewidth=2.5,
                color=CHART_COLORS[0],
                label="Daily spend",
            )
            axis.fill_between(
                x_positions,
                daily_totals.values,
                0,
                color=CHART_COLORS[0],
                alpha=0.12,
            )
            axis.set_xticks(x_positions, daily_totals.index)
            axis.legend()
            axis.grid(axis="y", alpha=0.8)
            axis.tick_params(axis="x", labelrotation=45)
        axis.set_title(f"Daily Spending Trend | {selected_month}")
        axis.set_xlabel("Date")
        axis.set_ylabel("Amount")
        figures.append(figure)

        figure, axis = plt.subplots(figsize=FIGURE_SIZE)
        actual_by_category = (
            month_frame.groupby("category")["amount"].sum().to_dict()
        )
        comparison_categories = sorted(
            set(category_budgets) | set(actual_by_category)
        )
        if not comparison_categories:
            _empty_chart(axis, f"No budget or spending recorded for {selected_month}")
        else:
            category_limits = [
                category_budgets.get(category, 0.0)
                for category in comparison_categories
            ]
            category_actuals = [
                float(actual_by_category.get(category, 0.0))
                for category in comparison_categories
            ]
            positions = range(len(comparison_categories))
            width = 0.38
            budget_bars = axis.bar(
                [position - width / 2 for position in positions],
                category_limits,
                width,
                color=CHART_COLORS[0],
                label="Budget",
            )
            actual_colors = [
                OVER_BUDGET_COLOR
                if category in category_budgets and actual > limit
                else CHART_COLORS[2]
                for category, actual, limit in zip(
                    comparison_categories,
                    category_actuals,
                    category_limits,
                )
            ]
            actual_bars = axis.bar(
                [position + width / 2 for position in positions],
                category_actuals,
                width,
                color=actual_colors,
                label="Actual (red = over budget)",
            )
            axis.set_xticks(list(positions), comparison_categories)
            _add_bar_labels(axis, budget_bars)
            _add_bar_labels(axis, actual_bars)
            axis.legend()
            axis.grid(axis="y", alpha=0.8)
            axis.set_axisbelow(True)
        axis.set_title(f"Category Budget vs Actual | {selected_month}")
        axis.set_xlabel("Category")
        axis.set_ylabel("Amount")
        figures.append(figure)

        figure, axis = plt.subplots(figsize=FIGURE_SIZE)
        if category_totals.empty:
            _empty_chart(axis, f"No expenses recorded for {selected_month}")
        else:
            bar_colors = [
                OVER_BUDGET_COLOR
                if category in category_budgets
                and float(total) > category_budgets[category]
                else CHART_COLORS[index % len(CHART_COLORS)]
                for index, (category, total) in enumerate(category_totals.items())
            ]
            bars = axis.bar(
                category_totals.index,
                category_totals.values,
                color=bar_colors,
                label="Actual spending (red = over budget)",
            )
            _add_bar_labels(axis, bars)
            axis.legend()
            axis.grid(axis="y", alpha=0.8)
            axis.set_axisbelow(True)
            axis.tick_params(axis="x", labelrotation=30)
        axis.set_title(f"Monthly Spending by Category | {selected_month}")
        axis.set_xlabel("Category")
        axis.set_ylabel("Amount")
        figures.append(figure)

        figure, axis = plt.subplots(figsize=FIGURE_SIZE)
        total_income = float(income_month["amount"].sum())
        actual_total = float(month_frame["amount"].sum())
        savings = total_income - actual_total
        if total_income == 0 and actual_total == 0:
            _empty_chart(axis, f"No income or expenses recorded for {selected_month}")
        else:
            savings_color = CHART_COLORS[1] if savings >= 0 else OVER_BUDGET_COLOR
            bars = axis.bar(
                ["Income", "Expenses", "Savings"],
                [total_income, actual_total, savings],
                color=[CHART_COLORS[0], CHART_COLORS[2], savings_color],
                label="Amount",
            )
            _add_bar_labels(axis, bars)
            axis.axhline(0, color=GRID_COLOR, linewidth=1)
            axis.legend()
            axis.grid(axis="y", alpha=0.8)
            axis.set_axisbelow(True)
        axis.set_title(f"Income, Expenses and Savings | {selected_month}")
        axis.set_ylabel("Amount")
        figures.append(figure)

        paths = [output_dir / name for name in CHART_NAMES]
        for figure, path in zip(figures, paths):
            if path.name == CHART_NAMES[0]:
                figure.tight_layout(rect=(0, 0, 0.78, 1))
            else:
                figure.tight_layout()
            figure.savefig(path, dpi=CHART_DPI, facecolor=CHART_BACKGROUND)
        if display:
            plt.show()
        for figure in figures:
            plt.close(figure)

    print_heading(f"Charts | {selected_month}")
    for path in paths:
        print(f"Saved: {path.resolve()}")
    print_success("Charts saved successfully.")
    if not category_totals.empty and not display:
        print("Chart windows were disabled for this run.")
    return paths
