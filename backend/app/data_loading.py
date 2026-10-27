"""Read the saved CSVs into typed DataFrames.

The paths are arguments, never constants, so the pure logic stays free of file paths
(AGENTS.md rule 6) and tests can point at fixtures. Phase 4's server reuses these
functions rather than re-inventing dtype handling, so the two cannot drift apart.

Both files are produced by backend/scripts/fetch_data.py and hold the RAW feeds: the
decision 0004 hold is not applied and the hindcast rows are still present. Applying
either belongs to forecast_selection.py, where it is tested.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Elexon returns whole MW, and fetch_data.py asserts the columns are integral. Reading
# them as int64 rather than float keeps a missing value loud instead of silently
# becoming NaN.
_ELEXON_TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"


def _parse_utc(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        frame[column] = pd.to_datetime(frame[column], format=_ELEXON_TIMESTAMP, utc=True)
    return frame


def load_actuals(path: str | Path) -> pd.DataFrame:
    """Metered wind generation, half-hourly. Columns: target_time, generation_mw."""
    frame = pd.read_csv(path, dtype={"generation_mw": "int64"})
    frame = _parse_utc(frame, ["target_time"])
    return frame.sort_values("target_time", kind="stable").reset_index(drop=True)


def load_forecasts(path: str | Path) -> pd.DataFrame:
    """Raw hourly wind forecasts. Columns: target_time, publish_time, generation_mw."""
    frame = pd.read_csv(path, dtype={"generation_mw": "int64"})
    frame = _parse_utc(frame, ["target_time", "publish_time"])
    return frame.sort_values(["target_time", "publish_time"], kind="stable").reset_index(drop=True)
