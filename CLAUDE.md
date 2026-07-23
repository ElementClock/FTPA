# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Principles

Start from first principles and the essence of the original requirements — not from convention or templates.

1. **Don't assume I know what I want.** When motivation or goals are unclear, stop and discuss.
2. **Always take the shortest path.** If the goal is clear but the path isn't the shortest, tell me and suggest a better way.
3. **Find root causes, don't apply patches.** Every decision must answer "why".
4. **Output the essentials.** Cut everything that doesn't change a decision.
5. **SRP (Single Responsibility)** — One function, one module, one reason to change.
6. **KISS / DRY / YAGNI** — Keep it simple, don't repeat yourself, only build what's needed now.
7. **High cohesion, low coupling** — Modules communicate through stable interfaces, not internal data.

## Commands

```bash
# Install
pip install -e .                          # Dev mode install
pip install -r requirements.txt           # Pinned deps
pip install -e ".[dev]"                   # With dev deps (pytest, black, flake8, mypy)

# Test
pytest                                    # All tests
pytest tests/test_unit.py -v              # Single test file
pytest -k test_name                       # Single test
pytest --cov=src/ftpa --cov-report=html    # Coverage (needs pytest-cov)

# Format & lint
black src/ tests/
flake8 src/ tests/
mypy src/ftpa/

# Run CLI
python -m ftpa.main --mode verify           # Quick file validation (default, 5 rows)
python -m ftpa.main --mode analysis         # Full pipeline: load → weight/CG → interactive plot
python -m ftpa.main --mode chunked          # Chunked reading (memory-friendly)
python -m ftpa.main --mode stats            # Statistical summary
python -m ftpa.main --mode interactive      # Interactive multi-signal viewer
python -m ftpa.main --gui                   # wxPython desktop GUI
python -m ftpa.main --gui --dry-run         # Validate GUI startup without window
ftpa                                        # Via installed script entry point
```

## Project Overview

FTPA (Flight Test Performance Analysis) is a Python toolkit for analyzing AG600 amphibious aircraft flight test telemetry data, ported from MATLAB. Data files are tab-separated TSVs up to ~879 MB, 173K rows × 470 columns, with time format `HH:MM:SS:mmm` at ~32 Hz.

## Architecture

The module is organized as a **layered pipeline** in `src/ftpa/`:

```
Data file (.txt/.zip)  →  data_loader.py  →  label_map.py  →  computing.py  →  statistics.py  →  plotting.py
                                                                    ↓
                                                              exporter.py / batch_processor.py
```

### Core modules

- **`data_loader.py`** — Reads all columns from TSV into `dict[str, np.ndarray]`, trims head/tail 50 rows, supports ZIP archives, caches results module-level.
- **`label_map.py`** — `LabelMap` class loads an Excel file mapping raw variable names ↔ Chinese labels, with four-direction lookup dictionaries.
- **`computing.py`** — `compute_total_weight_rel_cg()` interpolates fuel characteristic tables for weight/CG via moment-balance back-solving. `compute_fitted_circle_radius()` runs Taubin least-squares circle fitting on GPS tracks.
- **`statistics.py`** — Single/multi-variable statistics (start/end/min/max/range/mean/std), grouped stats, crossing analysis (threshold-triggered signal capture), takeoff/landing event detection (water-touchdown via RH=0).
- **`plotting.py`** — Multi-signal time series plots with matplotlib. Interactive mode has matplotlib widget controls (zoom, thresholds, crossing overlay lines). Auto-detects CJK fonts (Microsoft YaHei, SimHei, etc.) with fallback chain.
- **`time_utils.py`** — Converts between `HH:MM:SS:mmm`, float seconds, timedelta64.
- **`utils.py`** — `make_valid_name()` (MATLAB `makeValidName` equivalent), `column_to_field_name()`.
- **`exporter.py`** — Export to CSV, Parquet, HDF5, Excel, JSON.
- **`batch_processor.py`** — Glob-based multi-file processing with per-file weight/CG and stats comparison.

### GUI layer (`src/ftpa/gui/`)

Built with **wxPython** (three files): `app.py` main frame with wx.Notebook, `panels.py` (FileConfigPanel + ResultPanel with matplotlib canvas), `services.py` (preview/analysis runner in background thread via `wx.CallAfter`).

### CLI entry point (`main.py`)

Argparse dispatcher to modes (`verify`, `chunked`, `analysis`, `stats`, `interactive`, `--gui`). Smart `resolve_path()` searches project root, `data/`, `data/raw/`, and cwd.

### Project layout

- `src/ftpa/` — package source
- `tests/` — pytest unit tests + script-style integration tests
- `matlab/` — original MATLAB reference code (Param/, PlotFigure/, PrivateComputing/, PrivateStatistics/)
- `data/` — data and sample outputs

### Key details

- **Dependencies**: numpy, pandas, matplotlib, scipy, openpyxl, plotly, wxPython (not in requirements.txt — needs platform-specific wheel)
- **Default paths**: `DEFAULT_TXT_FILE` = project root / `FTPD-AG600-...txt`; `resolve_excel_path()` auto-discovers `data/参数名.xlsx` → project root
- **CJK font detection**: `plotting._configure_display_font()` tries Microsoft YaHei → SimHei → system fallback
- **Shared config** (`constants.py`): `BASE_WEIGHT=48487`, `BASE_REL_CG=25.28`, `BASE_OIL=6000.0`, `TRIM_HEAD=50`, `TRIM_TAIL=50`, `CHUNK_SIZE=10000`
- **MATLAB heritage**: Python code structure mirrors MATLAB files closely. `compute_total_weight_rel_cg` uses hardcoded 1007-aircraft fuel characteristics tables ported from MATLAB.
