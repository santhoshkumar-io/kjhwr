"""Error measures for the day-ahead wind forecast.

Decision 0005 fixes the four headline measures and the sign convention; decision 0006
adds the bias-corrected set and explains why it exists.

Every function returns `n`, the number of points it was computed over. Coverage must
never be invisible: at high hours-ahead settings a large share of points is legitimately
missing, and a metric quoted without its `n` hides that from the buyer.

Pure functions only: Series and DataFrames in, plain dicts out. No I/O (AGENTS.md
rule 6). Rows with a missing error are dropped from every calculation rather than
filled (rule 3).
"""

from __future__ import annotations

import pandas as pd

P90 = 0.9

# Decision 0006: a buyer sizing a safety margin wants the unpredictable part of the
# miss, because the predictable offset can simply be subtracted before buying.
BIAS_CORRECTED_KEYS = ("mae", "rmse", "bias", "p90")


def percentile_nearest_rank(sorted_values: pd.Series, quantile: float = P90) -> float:
    """The nearest-rank percentile: an observed value, never an interpolated one.

    Decision 0005 specifies this method. It matters: on the January data the P90 of the
    absolute error is 4,189 MW by nearest rank and 4,196.8 MW by linear interpolation,
    which is what numpy and pandas do by default.

    Nearest rank is used because the number carries a plain-English claim - "9 times out
    of 10 the forecast missed by less than this" - and that reads as a promise about
    errors which actually occurred. An interpolated value sits between two real
    observations and is true of neither.

    `sorted_values` must already be sorted ascending.
    """
    count = len(sorted_values)
    if count == 0:
        raise ValueError("cannot take a percentile of no values")
    index = int(quantile * (count - 1))
    return float(sorted_values.iloc[index])


def error_metrics(errors: pd.Series) -> dict:
    """The four measures from decision 0005, plus n.

    `errors` is forecast minus actual, so a positive bias means the forecast ran high.
    Missing values are dropped, not filled.
    """
    clean = pd.Series(errors).dropna()
    count = len(clean)
    if count == 0:
        return {"n": 0, "mae": None, "rmse": None, "bias": None, "p90": None}

    absolute = clean.abs()
    return {
        "n": count,
        "mae": float(absolute.mean()),
        "rmse": float((clean**2).mean() ** 0.5),
        "bias": float(clean.mean()),
        "p90": percentile_nearest_rank(absolute.sort_values().reset_index(drop=True)),
    }


def bias_corrected_metrics(errors: pd.Series) -> dict:
    """The same four measures with the in-range mean bias removed (decision 0006).

    The bias is computed over whatever range and mode the user selected, never
    hardcoded, and is returned as `bias_used` so the page can show what was subtracted.

    After correction the mean bias is zero by construction, so it is reported as 0.0
    rather than omitted - a reader comparing the two panels should see why.
    """
    clean = pd.Series(errors).dropna()
    if len(clean) == 0:
        return {"n": 0, "mae": None, "rmse": None, "bias": None, "p90": None, "bias_used": None}

    bias = float(clean.mean())
    corrected = error_metrics(clean - bias)
    corrected["bias_used"] = bias
    return corrected


def metrics_by_lead_time_bucket(series: pd.DataFrame, width_hours: int = 6) -> list[dict]:
    """Error grouped by how far ahead the chosen forecast was published.

    Buckets are `width_hours` wide and labelled by their inclusive lower bound. On the
    January data in deadline mode, lead times run 14.5 to 38.0 hours, so 6-hour buckets
    give five groups.

    **Do not use this to answer "does the forecast get worse the earlier it is made?"
    on a deadline-mode series.** In deadline mode the cutoff is fixed at 11:00 the day
    before, so one run serves each delivery day and lead time is determined by hour of
    day - they correlate at 0.9993 on the real data. Bucketing by lead time then just
    relabels overnight-versus-daytime wind behaviour, and it even slopes the wrong way.

    To isolate staleness, sweep `hours` in hours_ahead mode and compare whole series;
    that holds the hour-of-day mix constant. See test_january_golden.py, which pins both
    the confounding and the correct sweep.

    This breakdown remains useful for hours_ahead series and for showing the spread of
    lead times a given mode actually produces.
    """
    usable = series.dropna(subset=["error_mw", "lead_time_hours"])
    if usable.empty:
        return []

    bucket_start = (usable["lead_time_hours"] // width_hours * width_hours).astype(int)
    out = []
    for start, group in usable.groupby(bucket_start, sort=True):
        row = error_metrics(group["error_mw"])
        row["lead_time_from_hours"] = int(start)
        row["lead_time_to_hours"] = int(start) + width_hours
        out.append(row)
    return out


def metrics_by_hour_of_day(series: pd.DataFrame) -> list[dict]:
    """Error grouped by the UTC hour of the delivery half-hour.

    Answers "is the forecast worse at particular times of day", which a buyer can act on
    by shaping their safety margin across the day rather than applying one flat number.
    """
    usable = series.dropna(subset=["error_mw"])
    if usable.empty:
        return []

    out = []
    for hour, group in usable.groupby(usable["target_time"].dt.hour, sort=True):
        row = error_metrics(group["error_mw"])
        row["hour_utc"] = int(hour)
        out.append(row)
    return out


def worst_days(series: pd.DataFrame, k: int = 5) -> list[dict]:
    """The k delivery days with the highest MAE, worst first.

    Ranked by MAE rather than bias, because a day the forecast got wrong in both
    directions is still a bad day for a buyer.
    """
    usable = series.dropna(subset=["error_mw"])
    if usable.empty:
        return []

    out = []
    for day, group in usable.groupby(usable["target_time"].dt.date, sort=True):
        row = error_metrics(group["error_mw"])
        row["day"] = day.isoformat()
        out.append(row)

    out.sort(key=lambda row: row["mae"], reverse=True)
    return out[:k]


def summarise(series: pd.DataFrame, lead_time_bucket_hours: int = 6) -> dict:
    """Everything Screen 2 needs, from one series.

    Keeps the raw and bias-corrected sets side by side, as decision 0006 requires: the
    raw numbers stay primary because they are what the feeds actually say, and the
    corrected ones sit beside them clearly labelled.
    """
    errors = series["error_mw"]
    return {
        "raw": error_metrics(errors),
        "bias_corrected": bias_corrected_metrics(errors),
        "points_requested": int(len(series)),
        "points_matched": int(pd.Series(errors).notna().sum()),
        "forecast_below_actual": int((pd.Series(errors).dropna() < 0).sum()),
        "by_lead_time": metrics_by_lead_time_bucket(series, lead_time_bucket_hours),
        "by_hour_of_day": metrics_by_hour_of_day(series),
        "worst_days": worst_days(series),
    }
