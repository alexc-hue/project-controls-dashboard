# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and version numbers
follow [Semantic Versioning](https://semver.org/).

## [1.2.2] - 2026-11-23

Bug-fix release. The console report, `assets/report.md` and the charts are unchanged on the sample
data.

### Fixed

- EVM guards in `project_summary`, matching the module's NaN-not-inf rule: a CPI of 0 (EV 0 with AC
  above 0) gives NaN for EAC, ETC and VAC instead of inf and -inf; a BAC of 0 gives NaN percent
  complete instead of inf and a RuntimeWarning; and once AC reaches BAC, TCPI is NaN instead of a
  negative number that read as an easy target.
- Status matching ignores case and surrounding whitespace. A " closed" risk used to count as open
  and could be flagged as overdue, and an "approved" or "pending" change dropped out of the change
  totals. `load_risk_register` and `load_change_register` now write the known statuses (Open,
  Mitigating, Closed, Approved, Pending, Rejected) in their usual form; any other status is only
  trimmed.
- `money()` printed a small negative amount such as -0.4 as `-$0`. It now prints `$0`.
- The `forecast_completion_date` docstring said it stretches the remaining planned duration. It
  stretches the whole planned duration from project start (planned duration / SPI), which is what
  the code has always done.

### Added

- Tests for each fix above.

## [1.2.1] - 2026-11-12

Maintenance release. The only output change is the report headline's punctuation.

### Changed

- The report headline reads "PROJECT STATUS REPORT, as of <period>" (console) and
  "Project Status Report, as of <period>" (report.md), with a comma where a long dash was.
  Nothing else in the output changed.
- `pytest>=9.0.3` in `requirements-dev.txt` (was `>=7.0`).
- CI runs the tests on Python 3.11, 3.12, 3.13 and 3.14 (was 3.11 and 3.12).
- CI actions are updated (checkout v7.0.1, setup-python v7.1.0, codecov-action v7.1.1) and pinned
  to commit SHAs, not tags.
- README: the list of related repos is the same in all eight repos now. It names the six toolkit
  tools, then the two data center practice models separately.
- README: long dashes replaced with plain punctuation.
- `.gitignore` also covers `.env` files, ruff and coverage caches, build output and editor folders.

## [1.2.0] - 2026-09-28

Performance at larger sizes. Output is unchanged: the console report and report.md are byte-identical to the previous release on the sample data and on generated inputs, and every chart renders pixel-identical on the sample data, so no committed image changed. The only visible difference is on inputs larger than a chart's cap, where the chart now shows a subset and says so in its title.

### Added

- `benchmarks/size_test.py`, a hand-run size test: generates bigger inputs, runs the tool end to end
  and prints run time and peak memory. Not part of CI or the test suite.
- Measured size-test numbers in the README's Limitations section.
- Tests for the chart caps and for the point spreading against the previous loop.

### Changed

- The change and milestone charts show at most 30 items, and the risk matrix labels at most the 30
  highest-exposure risks (every risk is still plotted).
- Risk matrix points that share a cell are spread in one pass; positions are exactly as before.
  Registers of 10,000 entries each went from about 11 minutes to about 7 seconds.

## [1.1.0] - 2026-09-28

Checks and tests only. The tool's output is unchanged.

### Added

- A test that runs `dashboard.py` end to end on the sample data and checks the README's Result block against what it actually prints, so the README can't drift from the code.
- A check that the committed `assets/report.md` is exactly what the script regenerates.
- Regression tests for the code-review fixes already in 1.0.0: sign-first negative amounts, the forecast finish rounded to the nearest day, milestones with a missing date flagged rather than called Delayed, and markdown-safe free text.
- A test that pins the chart colors and styling shared across all six toolkit repos.
- ruff linting, run locally from `ruff.toml` and as its own CI job.
- CI now tests on Python 3.11 and 3.12, matching the "Python 3.11+" badge.
- `.gitattributes` keeps line endings consistent (LF) on every OS.

### Changed

- Import formatting in the tests, from the new lint rules. No behaviour change.

## [1.0.0] - 2026-09-13

First tagged release, marking the state of the repo before this changelog started. Earned value (SPI/CPI, EAC/ETC/VAC, TCPI), an SPI-based forecast finish, milestone tracking and risk register analysis, with charts and a markdown report. Includes the fixes from code review, a pytest suite and CI.

[1.2.2]: https://github.com/alexc-hue/project-controls-dashboard/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/alexc-hue/project-controls-dashboard/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/alexc-hue/project-controls-dashboard/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/alexc-hue/project-controls-dashboard/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/alexc-hue/project-controls-dashboard/releases/tag/v1.0.0
