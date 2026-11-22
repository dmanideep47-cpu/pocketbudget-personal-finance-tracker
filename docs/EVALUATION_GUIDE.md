# PocketBudget — Demonstration and Evaluation Guide

This guide provides a repeatable way to demonstrate the application during a
practical examination or project review. The sample amounts below are
illustrative only. Use a clean copy of the project data so demonstration
records do not mix with personal records.

## 1. What the project solves

Small daily purchases are easy to overlook. PocketBudget provides a local
place to record income and expenses, assign monthly category limits, identify
overspending, review savings, and export a monthly statement.

## 2. Learning objectives

After completing the project, a student should be able to explain how to:

- Decompose a Python application into focused modules.
- Validate user input and handle invalid or missing data.
- Persist structured records in JSON files.
- Use Pandas to group and summarize transaction data.
- Use Matplotlib to communicate financial information visually.
- Export structured data to CSV.
- Verify application behaviour with automated pytest tests.

## 3. Architecture at a glance

The terminal menu in `main.py` routes user choices to the expense, income,
budget, reporting, chart, and advisor modules. The manager modules validate
and prepare records. `file_handler.py` is responsible for local JSON storage,
including initialization, validation, migration, backup, and safe writes.
`analytics.py` uses Pandas for monthly calculations and CSV export.
`visualizations.py` creates the charts, while `advisor.py` applies
transparent rule-based checks to the monthly totals.

See the architecture and data-flow diagrams in the main README.

## 4. Suggested live demonstration

Start with an empty demonstration data folder or a separate working copy.

1. Run `python main.py` and introduce the numbered menu.
2. Add two or three expenses with different categories and payment methods.
3. Add one income record.
4. Set monthly limits for at least two categories.
5. Open budget status and point out actual spending, remaining budget, and
   any over-budget warning.
6. Open the monthly report and explain the total, transaction count,
   category-wise totals, and weekly totals.
7. Run spending analysis and explain the highest-spending day and top
   categories.
8. Generate the charts and identify what each chart communicates.
9. Export the monthly CSV and open it in a spreadsheet application.
10. Run `python -m pytest -v` to show the automated test suite.

Do not use private financial records in a classroom demonstration.

## 5. Important calculations

Let:

- (I) = total income recorded for the selected month.
- (E) = total expenses recorded for the selected month.
- (B_c) = budget limit for category (c).
- (A_c) = actual spending in category (c).

**Net savings / current balance**

`Savings = I - E`

**Savings percentage**

`Savings % = ((I - E) / I) × 100`, when `I > 0`.

When income is zero or absent, the application reports a zero savings
percentage to avoid division by zero.

**Category budget remaining**

`Remaining(c) = B_c - A_c`

A negative result means the category is over budget by the absolute value of
that result.

**Average daily spending**

The monthly report calculates the mean of daily totals over days that contain
at least one recorded expense. It is not an average over every calendar day
in the month.

## 6. Data design

The application uses two local JSON files:

- `data/expenses.json`: a list containing both expense and income records.
  The `type` field distinguishes the two record types, and transaction IDs
  are shared and unique.
- `data/budgets.json`: monthly keys containing category-to-limit mappings.

Expense records include an ID, type, amount, category, date, description, and
payment method. Income records include an ID, type, amount, date, source, and
description.

JSON is suitable for this small, single-user learning project because it is
human-readable and does not require a database server. It is not intended as a
multi-user or high-volume storage system.

## 7. Validation and reliability

The application checks positive finite amounts, calendar-valid dates,
month formats, supported categories, payment methods, and transaction IDs.
Invalid input is rejected and requested again. Missing data files are
initialized. Corrupt JSON is reported rather than silently replaced.
Existing data is backed up before a write, and updates use an atomic
replacement strategy.

## 8. Testing and continuous integration

Run the full suite locally:

```bash
python -m pip install -r requirements.txt
python -m compileall -q .
python -m pytest -v
```

The tests use temporary directories for storage and export operations so the
real project data is not overwritten. GitHub Actions also runs compilation
and pytest on Ubuntu and Windows with Python 3.12 for pushes and pull requests.

## 9. Common viva questions

**Why is JSON used instead of a database?**

JSON keeps this single-user educational application lightweight, readable,
and easy to run without server configuration. A relational database would be
more appropriate for concurrent users, larger datasets, and stronger query
requirements.

**Why use Pandas?**

Pandas provides reliable tabular operations such as filtering by month,
grouping by category or week, calculating totals, and preparing CSV exports.

**Why use Matplotlib?**

Matplotlib turns numerical summaries into charts that make category shares,
daily trends, budget comparisons, and savings easier to interpret.

**How are expenses separated from income?**

Both record types share a transaction file and unique ID sequence. A
`type` field identifies each record, and the reporting functions filter the
appropriate type before calculating totals.

**How does the application avoid destroying existing data?**

It validates loaded records, reports corrupt JSON, backs up an existing file,
and uses an atomic replacement for writes.

**Is the financial advisor AI?**

No. It is a transparent rule-based advisor. It checks budget overruns,
expense-to-income ratios, concentration in the largest spending category,
and a savings target. It does not train a machine-learning model or provide
professional financial advice.

## 10. Current limitations and future scope

The current version is terminal-based, local, and single-user. It does not
provide authentication, cloud synchronization, bank integration, recurring
payments, multi-currency conversion, or machine-learning predictions.
Reasonable future extensions include recurring transactions, configurable
currency formatting, savings goals, encrypted backups, and a database-backed
multi-user edition.

## 11. Submission checklist

- [ ] Confirm the project title and student/team details on the submitted report.
- [ ] Run the application from a clean project copy.
- [ ] Run compilation and all pytest tests.
- [ ] Verify the screenshots match the current application output.
- [ ] Demonstrate expense entry, income entry, budgets, reports, charts, and CSV.
- [ ] Explain the formulas, JSON structure, Pandas analysis, and limitations.
- [ ] Do not claim cloud, database, AI, or bank-integration features that are
      not implemented.
