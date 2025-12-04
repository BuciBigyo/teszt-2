#!/usr/bin/env python3
"""
analysis_plots.py

Utility script to check consistency of the synthetic population
against census tables and produce diagnostic plots.

- Settlement-level marginals: sex, age, education, labour
- Household size distribution (census vs templates vs final)
- Household-level age structure (templates vs final, private households)

Extended version:
- Computes error statistics (MAE, RMSE, MAPE, Pearson r)
- Computes percentage differences per city
- Produces additional plots (scatter vs 45-degree line, percent-diff histograms, etc.)
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =========================================================
# CONFIG
# =========================================================

DB_PATH = "populacio.db"
OUTDIR = Path("figures")
OUTDIR.mkdir(exist_ok=True, parents=True)

# If None -> process all settlements
# If a list of ints -> only these LakhelyID values (from Finishing_step) will be processed
CITY_FILTER = None  # Example for testing
# Examples:
# CITY_FILTER = None              # all cities
# CITY_FILTER = [1]               # only first city
# CITY_FILTER = [12, 45, 102]     # arbitrary list of LakhelyID


# =========================================================
# SMALL HELPERS
# =========================================================

def _safe_int(x, default=0) -> int:
    try:
        if pd.isna(x):
            return default
        return int(round(float(x)))
    except Exception:
        return default


def _compute_error_stats(orig: pd.Series, sim: pd.Series) -> dict:
    """
    Compute error statistics between original and simulated counts.

    Returns dict with:
      - mae: mean absolute percentage difference (%, ignores orig=0)
      - rmse: root mean squared error in counts
      - mape: same as mae (kept for backwards compatibility)
      - r: Pearson correlation coefficient
    """
    o = np.asarray(orig, dtype=float)
    s = np.asarray(sim, dtype=float)
    diff = s - o

    # mask for non-zero originals
    mask = o != 0

    # MAE as percentage
    if np.any(mask):
        mae = np.mean(np.abs(diff[mask] / o[mask])) * 100.0
        mape = mae
    else:
        mae = np.nan
        mape = np.nan

    # RMSE still in absolute counts
    rmse = np.sqrt(np.mean(diff ** 2))

    # Pearson correlation
    if np.all(o == o[0]) or np.all(s == s[0]):
        r = np.nan
    else:
        r = float(np.corrcoef(o, s)[0, 1])

    return {"mae": mae, "rmse": rmse, "mape": mape, "r": r}

def _add_percentage_diff(df: pd.DataFrame, col_orig: str, col_sim: str, col_pct: str):
    """
    Add percentage difference column to df:
      pct_diff = 100 * (sim - orig) / orig
    If orig == 0, set 0.0 to avoid inf/nan explosions.
    """
    denom = df[col_orig].replace(0, np.nan)
    pct = 100.0 * (df[col_sim] - df[col_orig]) / denom
    df[col_pct] = pct.fillna(0.0)


def load_telepules(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load TelepulesOsszegzett with a clean 'Lakhely' column."""
    helytab = pd.read_sql_query("SELECT * FROM TelepulesOsszegzett", conn)

    # Fix possible trailing space in 90+ column
    if "90+ koru " in helytab.columns and "90+ koru" not in helytab.columns:
        helytab = helytab.rename(columns={"90+ koru ": "90+ koru"})

    helytab["Lakhely"] = helytab["Helység megnevezése"].astype(str).str.strip()
    return helytab


def get_allowed_lakhely(conn: sqlite3.Connection):
    """
    If CITY_FILTER is not None, return the list of Lakhely names
    corresponding to those LakhelyID values in Finishing_step.
    Otherwise return None (meaning: no restriction).
    """
    if CITY_FILTER is None:
        return None

    city_map = pd.read_sql_query(
        "SELECT DISTINCT LakhelyID, TRIM(Lakhely) AS Lakhely FROM Finishing_step",
        conn,
    )
    allowed = city_map[city_map["LakhelyID"].isin(CITY_FILTER)]["Lakhely"].tolist()
    print("CITY_FILTER active, restricting to settlements:", allowed)
    return allowed


# =========================================================
# 1) SEX PER CITY
# =========================================================

def analyse_sex(conn: sqlite3.Connection, helytab: pd.DataFrame, allowed_lakhely=None):
    print("\n=== SEX PER CITY ===")

    sex_cols_city = ["Ferfi", "No"]

    orig_sex = helytab[["Lakhely"] + sex_cols_city].copy()

    sim_sex = pd.read_sql_query(
        """
        SELECT TRIM(Lakhely) AS Lakhely,
               Nem,
               COUNT(*) AS Count
        FROM Finishing_step
        GROUP BY TRIM(Lakhely), Nem
        """,
        conn,
    )

    # Restrict to selected settlements if filter is active
    if allowed_lakhely is not None:
        sim_sex = sim_sex[sim_sex["Lakhely"].isin(allowed_lakhely)]

    sim_pivot = sim_sex.pivot(index="Lakhely", columns="Nem", values="Count").fillna(0)

    # Ensure both sexes exist as columns
    for col in ["Férfi", "Nő"]:
        if col not in sim_pivot.columns:
            sim_pivot[col] = 0

    # Map simulated column names to city labels
    sim_pivot = sim_pivot.rename(columns={"Férfi": "Ferfi", "Nő": "No"})
    sim_pivot.reset_index(inplace=True)

    sex_check = orig_sex.merge(
        sim_pivot,
        on="Lakhely",
        how="left",
        suffixes=("_orig", "_sim")
    ).fillna(0)

    # Differences, percentages, stats and plots
    abs_diffs = {}
    pct_diffs = {}

    for col in sex_cols_city:
        col_orig = f"{col}_orig"
        col_sim = f"{col}_sim"
        diff_col = f"{col}_diff"
        pct_col = f"{col}_pct_diff"

        sex_check[diff_col] = sex_check[col_sim] - sex_check[col_orig]
        _add_percentage_diff(sex_check, col_orig, col_sim, pct_col)

        abs_diffs[col] = sex_check[diff_col].abs()
        pct_diffs[col] = sex_check[pct_col]

        stats = _compute_error_stats(sex_check[col_orig], sex_check[col_sim])
        print(print(
            f"[SEX] {col}: "
            f"MAE={stats['mae']:.2f}%, RMSE={stats['rmse']:.2f}, "
            f"MAPE={stats['mape']:.2f}%, r={stats['r']:.3f}"
        ))  
        print(f"         Max abs diff: {abs_diffs[col].max()}")

    # Plot histograms of absolute differences
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, col in zip(axes, sex_cols_city):
        ax.hist(abs_diffs[col], bins=20)
        ax.set_title(f"Absolute diff in {col} per city")
        ax.set_xlabel("Absolute difference")
        ax.set_ylabel("Number of settlements")
    fig.suptitle("Settlement-level sex differences (simulated vs census)")
    fig.tight_layout()
    fig.savefig(OUTDIR / "sex_diff_hist.pdf", dpi=150)
    plt.close(fig)

    # Histogram of percentage differences
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, col in zip(axes, sex_cols_city):
        ax.hist(pct_diffs[col], bins=30)
        ax.set_title(f"Percent diff in {col} per city")
        ax.set_xlabel("Percent difference (%)")
        ax.set_ylabel("Number of settlements")
    fig.suptitle("Settlement-level sex percentage differences (sim vs census)")
    fig.tight_layout()
    fig.savefig(OUTDIR / "sex_pct_diff_hist.pdf", dpi=150)
    plt.close(fig)

    # Scatter plot census vs simulated for total population
    sex_check["Lakos_orig"] = sex_check["Ferfi_orig"] + sex_check["No_orig"]
    sex_check["Lakos_sim"] = sex_check["Ferfi_sim"] + sex_check["No_sim"]

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(sex_check["Lakos_orig"], sex_check["Lakos_sim"], alpha=0.5, s=10)
    max_val = max(sex_check["Lakos_orig"].max(), sex_check["Lakos_sim"].max())
    ax.plot([0, max_val], [0, max_val], linestyle="--")
    ax.set_xlabel("Census total population")
    ax.set_ylabel("Simulated total population")
    ax.set_title("Total population per settlement (census vs simulated)")
    fig.tight_layout()
    fig.savefig(OUTDIR / "sex_total_pop_scatter.pdf", dpi=150)
    plt.close(fig)

    return sex_check


# =========================================================
# 2) AGE PER CITY (10-YEAR BINS)
# =========================================================

def analyse_age(conn: sqlite3.Connection, helytab: pd.DataFrame, allowed_lakhely=None):
    print("\n=== AGE PER CITY (10-YEAR BINS) ===")

    age_cols_city = [
        "0-9 koru",
        "10-19 koru",
        "20-29 koru",
        "30-39 koru",
        "40-49 koru",
        "50-59 koru",
        "60-69 koru",
        "70-79 koru",
        "80-89 koru",
        "90+ koru",
    ]

    # Some datasets might miss some columns; ensure presence with 0s
    for col in age_cols_city:
        if col not in helytab.columns:
            helytab[col] = 0

    orig_age = helytab[["Lakhely"] + age_cols_city].copy()

    sim_age = pd.read_sql_query(
        """
        SELECT
          TRIM(Lakhely) AS Lakhely,
          CASE
            WHEN CAST(Kor AS INTEGER) BETWEEN 0  AND 9  THEN '0-9 koru'
            WHEN CAST(Kor AS INTEGER) BETWEEN 10 AND 19 THEN '10-19 koru'
            WHEN CAST(Kor AS INTEGER) BETWEEN 20 AND 29 THEN '20-29 koru'
            WHEN CAST(Kor AS INTEGER) BETWEEN 30 AND 39 THEN '30-39 koru'
            WHEN CAST(Kor AS INTEGER) BETWEEN 40 AND 49 THEN '40-49 koru'
            WHEN CAST(Kor AS INTEGER) BETWEEN 50 AND 59 THEN '50-59 koru'
            WHEN CAST(Kor AS INTEGER) BETWEEN 60 AND 69 THEN '60-69 koru'
            WHEN CAST(Kor AS INTEGER) BETWEEN 70 AND 79 THEN '70-79 koru'
            WHEN CAST(Kor AS INTEGER) BETWEEN 80 AND 89 THEN '80-89 koru'
            ELSE '90+ koru'
          END AS AgeRange,
          COUNT(*) AS Count
        FROM Finishing_step
        GROUP BY TRIM(Lakhely), AgeRange
        """,
        conn,
    )

    if allowed_lakhely is not None:
        sim_age = sim_age[sim_age["Lakhely"].isin(allowed_lakhely)]

    sim_age_pivot = sim_age.pivot(index="Lakhely", columns="AgeRange", values="Count").fillna(0)

    # Ensure all age categories exist as columns
    for col in age_cols_city:
        if col not in sim_age_pivot.columns:
            sim_age_pivot[col] = 0

    sim_age_pivot.reset_index(inplace=True)

    age_check = orig_age.merge(
        sim_age_pivot,
        on="Lakhely",
        how="left",
        suffixes=("_orig", "_sim")
    ).fillna(0)

    diff_cols = []
    pct_cols = []
    for col in age_cols_city:
        col_orig = f"{col}_orig"
        col_sim = f"{col}_sim"
        diff_col = f"{col}_diff"
        pct_col = f"{col}_pct_diff"
        age_check[diff_col] = age_check[col_sim] - age_check[col_orig]
        _add_percentage_diff(age_check, col_orig, col_sim, pct_col)
        diff_cols.append(diff_col)
        pct_cols.append(pct_col)

        stats = _compute_error_stats(age_check[col_orig], age_check[col_sim])
        print(
            f"[AGE] {col}: MAE={stats['mae']:.2f}%, RMSE={stats['rmse']:.2f}, "
            f"MAPE={stats['mape']:.2f}%, r={stats['r']:.3f}"
            
        )
        print(f"       Max abs diff: {age_check[diff_col].abs().max()}")

    # Total absolute age diff per city
    age_check["total_abs_age_diff"] = age_check[diff_cols].abs().sum(axis=1)
    print("Max total abs age diff per city:",
          age_check["total_abs_age_diff"].max())

    # Plot histogram of total absolute age diff per city
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(age_check["total_abs_age_diff"], bins=30)
    ax.set_title("Total absolute age difference per city (10-year bins)")
    ax.set_xlabel("Total |difference| over all age bins")
    ax.set_ylabel("Number of settlements")
    fig.tight_layout()
    fig.savefig(OUTDIR / "age_total_abs_diff_hist.pdf", dpi=150)
    plt.close(fig)

    # Mean abs diff per age bin (bar plot)
    mean_abs = age_check[diff_cols].abs().mean(axis=0)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(age_cols_city, mean_abs.values)
    ax.set_xticklabels(age_cols_city, rotation=45, ha="right")
    ax.set_ylabel("Mean absolute difference")
    ax.set_title("Mean absolute age difference per 10-year bin")
    fig.tight_layout()
    fig.savefig(OUTDIR / "age_mean_abs_diff_per_bin.pdf", dpi=150)
    plt.close(fig)

    # Mean percent diff per age bin (bar plot)
    mean_pct = age_check[pct_cols].mean(axis=0)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(age_cols_city, mean_pct.values)
    ax.set_xticklabels(age_cols_city, rotation=45, ha="right")
    ax.set_ylabel("Mean percent difference (%)")
    ax.set_title("Mean percent age difference per 10-year bin")
    fig.tight_layout()
    fig.savefig(OUTDIR / "age_mean_pct_diff_per_bin.pdf", dpi=150)
    plt.close(fig)

    return age_check


# =========================================================
# 3) EDUCATION PER CITY
#    (Using Szimuláció, where 'Oktatás' lives)
# =========================================================

def analyse_education(conn: sqlite3.Connection, helytab: pd.DataFrame, allowed_lakhely=None):
    print("\n=== EDUCATION PER CITY ===")

    edu_cols_city = [
        "Nincs 8 ált.",
        "8 általános",
        "Szakmai okl",
        "Érettségi",
        "Diploma/Oklevél",
        "7 évesnél fiatalabb",
    ]

    for col in edu_cols_city:
        if col not in helytab.columns:
            helytab[col] = 0

    orig_edu = helytab[["Lakhely"] + edu_cols_city].copy()

    sim_edu = pd.read_sql_query(
        """
        SELECT TRIM(Lakhely) AS Lakhely,
               Oktatás,
               COUNT(*) AS Count
        FROM Szimulació
        GROUP BY TRIM(Lakhely), Oktatás
        """,
        conn,
    )

    if allowed_lakhely is not None:
        sim_edu = sim_edu[sim_edu["Lakhely"].isin(allowed_lakhely)]

    sim_edu_pivot = sim_edu.pivot(index="Lakhely", columns="Oktatás", values="Count").fillna(0)

    # Ensure all education categories exist as columns
    for col in edu_cols_city:
        if col not in sim_edu_pivot.columns:
            sim_edu_pivot[col] = 0

    sim_edu_pivot.reset_index(inplace=True)

    edu_check = orig_edu.merge(
        sim_edu_pivot,
        on="Lakhely",
        how="left",
        suffixes=("_orig", "_sim")
    ).fillna(0)

    diff_cols = []
    pct_cols = []
    for col in edu_cols_city:
        col_orig = f"{col}_orig"
        col_sim = f"{col}_sim"
        diff_col = f"{col}_diff"
        pct_col = f"{col}_pct_diff"
        edu_check[diff_col] = edu_check[col_sim] - edu_check[col_orig]
        _add_percentage_diff(edu_check, col_orig, col_sim, pct_col)
        diff_cols.append(diff_col)
        pct_cols.append(pct_col)

        stats = _compute_error_stats(edu_check[col_orig], edu_check[col_sim])
        print(
            f"[EDU] {col}: MAE={stats['mae']:.2f}%, RMSE={stats['rmse']:.2f}, "
            f"MAPE={stats['mape']:.2f}%, r={stats['r']:.3f}"
        )
        print(f"      Max abs diff: {edu_check[diff_col].abs().max()}")

    edu_check["total_abs_edu_diff"] = edu_check[diff_cols].abs().sum(axis=1)
    print("Max total abs education diff per city:",
          edu_check["total_abs_edu_diff"].max())

    # Histogram of total abs diff
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(edu_check["total_abs_edu_diff"], bins=30)
    ax.set_title("Total absolute education difference per city")
    ax.set_xlabel("Total |difference| over all education categories")
    ax.set_ylabel("Number of settlements")
    fig.tight_layout()
    fig.savefig(OUTDIR / "edu_total_abs_diff_hist.pdf", dpi=150)
    plt.close(fig)

    # Mean abs diff per education category
    mean_abs = edu_check[diff_cols].abs().mean(axis=0)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(edu_cols_city, mean_abs.values)
    ax.set_xticklabels(edu_cols_city, rotation=45, ha="right")
    ax.set_ylabel("Mean absolute difference")
    ax.set_title("Mean absolute education difference per category")
    fig.tight_layout()
    fig.savefig(OUTDIR / "edu_mean_abs_diff_per_cat.pdf", dpi=150)
    plt.close(fig)

    # Mean percent diff per education category
    mean_pct = edu_check[pct_cols].mean(axis=0)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(edu_cols_city, mean_pct.values)
    ax.set_xticklabels(edu_cols_city, rotation=45, ha="right")
    ax.set_ylabel("Mean percent difference (%)")
    ax.set_title("Mean percent education difference per category")
    fig.tight_layout()
    fig.savefig(OUTDIR / "edu_mean_pct_diff_per_cat.pdf", dpi=150)
    plt.close(fig)

    return edu_check


# =========================================================
# 4) LABOUR STATUS PER CITY
#    Targets from LakasOsszegzett (household categories)
#    vs final labour_cat in Finishing_step
# =========================================================

def compute_labour_targets(conn: sqlite3.Connection, allowed_lakhely=None) -> pd.DataFrame:
    """
    Reconstruct approximate person-level labour totals from LakasOsszegzett.
    Assumes the usual 0/1/2/'3 or more' pattern and 3 persons for '3+'.
    """
    laktab = pd.read_sql_query("SELECT * FROM LakasOsszegzett", conn)
    laktab["Lakhely"] = laktab["Helység megnevezése"].astype(str).str.strip()

    if allowed_lakhely is not None:
        laktab = laktab[laktab["Lakhely"].isin(allowed_lakhely)]

    rows = []
    for _, row in laktab.iterrows():
        lakhely = row["Lakhely"]

        # Employed
        dolg = (
            0 * _safe_int(row.get("Nincs foglalkoztatott a háztartásban", 0)) +
            1 * _safe_int(row.get("1 foglalkoztatott személy van a háztartásban", 0)) +
            2 * _safe_int(row.get("2 foglalkoztatott személy van a háztartásban", 0)) +
            3 * _safe_int(row.get("3 vagy több foglalkoztatott személy van a háztartásban", 0))
        )
        # Unemployed
        munkanel = (
            0 * _safe_int(row.get("Nincs munkanélküli személy a háztartásban", 0)) +
            1 * _safe_int(row.get("1 munkanélküli személy van a háztartásban", 0)) +
            2 * _safe_int(row.get("2 munkanélküli személy van a háztartásban", 0)) +
            3 * _safe_int(row.get("3 vagy több munkanélküli személy van a háztartásban", 0))
        )
        # Inactive with benefits
        inak = (
            0 * _safe_int(row.get("Nincs ellátásban részesülő inaktív személy a háztartásban", 0)) +
            1 * _safe_int(row.get("1 ellátásban részesülő inaktív személy van a háztartásban", 0)) +
            2 * _safe_int(row.get("2 ellátásban részesülő inaktív személy van a háztartásban", 0)) +
            3 * _safe_int(row.get("3 vagy több ellátásban részesülő inaktív személy van a háztartásban", 0))
        )
        # Dependents
        elt = (
            0 * _safe_int(row.get("Nincs eltartott személy van a háztartásban", 0)) +
            1 * _safe_int(row.get("1 eltartott személy van a háztartásban", 0)) +
            2 * _safe_int(row.get("2 eltartott személy van a háztartásban", 0)) +
            3 * _safe_int(row.get("3 vagy több eltartott személy van a háztartásban", 0))
        )

        rows.append({
            "Lakhely": lakhely,
            "emp_target": dolg,
            "unemp_target": munkanel,
            "inact_benefit_target": inak,
            "dependent_target": elt,
        })

    return pd.DataFrame(rows)


def analyse_labour(conn: sqlite3.Connection, allowed_lakhely=None):
    print("\n=== LABOUR STATUS PER CITY ===")

    targets = compute_labour_targets(conn, allowed_lakhely=allowed_lakhely)

    # Simulated labour totals from Finishing_step (labour_cat)
    sim_lab = pd.read_sql_query(
        """
        SELECT TRIM(Lakhely) AS Lakhely,
               labour_cat,
               COUNT(*) AS Count
        FROM Finishing_step
        GROUP BY TRIM(Lakhely), labour_cat
        """,
        conn,
    )

    if allowed_lakhely is not None:
        sim_lab = sim_lab[sim_lab["Lakhely"].isin(allowed_lakhely)]

    sim_pivot = sim_lab.pivot(index="Lakhely", columns="labour_cat", values="Count").fillna(0)

    # Ensure all labour categories exist
    for col in ["emp", "unemp", "inact_benefit", "dependent"]:
        if col not in sim_pivot.columns:
            sim_pivot[col] = 0

    sim_pivot.reset_index(inplace=True)

    labour_check = targets.merge(sim_pivot, on="Lakhely", how="left").fillna(0)

    cats = ["emp", "unemp", "inact_benefit", "dependent"]
    diff_cols = []
    pct_cols = []
    for cat in cats:
        tcol = f"{cat}_target"
        scol = cat
        dcol = f"{cat}_diff"
        pctcol = f"{cat}_pct_diff"
        labour_check[dcol] = labour_check[scol] - labour_check[tcol]
        _add_percentage_diff(labour_check, tcol, scol, pctcol)
        diff_cols.append(dcol)
        pct_cols.append(pctcol) 
        avg_target = labour_check[tcol].mean()
        stats = _compute_error_stats(labour_check[tcol], labour_check[scol])
        if avg_target > 0:
            rel_mae = 100.0 * stats["mae"] / avg_target
        else:
            rel_mae = np.nan

        print(
            f"[LAB] {cat}: "
            f"mean target per city = {avg_target:.2f}, "
            f"MAE = {stats['mae']:.2f} "
            f"({rel_mae:.1f}% of mean), "
            f"RMSE = {stats['rmse']:.2f}, "
            f"MAPE = {stats['mape']:.2f}%, "
            f"r = {stats['r']:.3f}"
        )
        print(f"      Max abs diff: {labour_check[dcol].abs().max()}")

    labour_check["total_abs_labour_diff"] = labour_check[diff_cols].abs().sum(axis=1)
    print("Max total abs labour diff per city:",
          labour_check["total_abs_labour_diff"].max())

    # Histogram of total abs labour diff
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(labour_check["total_abs_labour_diff"], bins=30)
    ax.set_title("Total absolute labour difference per city")
    ax.set_xlabel("Total |difference| over labour categories")
    ax.set_ylabel("Number of settlements")
    fig.tight_layout()
    fig.savefig(OUTDIR / "labour_total_abs_diff_hist.pdf", dpi=150)
    plt.close(fig)

    # Mean abs diff per category (bar)
    mean_abs = labour_check[diff_cols].abs().mean(axis=0)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(cats, mean_abs.values)
    ax.set_ylabel("Mean absolute difference")
    ax.set_title("Mean absolute labour difference per category")
    fig.tight_layout()
    fig.savefig(OUTDIR / "labour_mean_abs_diff_per_cat.pdf", dpi=150)
    plt.close(fig)

    # Mean percent diff per category (bar)
    mean_pct = labour_check[pct_cols].mean(axis=0)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(cats, mean_pct.values)
    ax.set_ylabel("Mean percent difference (%)")
    ax.set_title("Mean percent labour difference per category")
    fig.tight_layout()
    fig.savefig(OUTDIR / "labour_mean_pct_diff_per_cat.pdf", dpi=150)
    plt.close(fig)

    return labour_check


# =========================================================
# 5) HOUSEHOLD SIZE DISTRIBUTION
#    LakasOsszegzett vs LakasEpitő (templates / final)
# =========================================================

def analyse_household_sizes(conn: sqlite3.Connection, allowed_lakhely=None):
    print("\n=== HOUSEHOLD SIZE DISTRIBUTION ===")

    # Census household sizes
    laktab = pd.read_sql_query("SELECT * FROM LakasOsszegzett", conn)
    laktab["Lakhely"] = laktab["Helység megnevezése"].astype(str).str.strip()

    if allowed_lakhely is not None:
        laktab = laktab[laktab["Lakhely"].isin(allowed_lakhely)]

    size_cols_census = [
        "1 személyes háztartás",
        "2 személyes háztartás",
        "3 személyes háztartás",
        "4 személyes háztartás",
        "5 személyes háztartás",
        "6+ személyes háztartás",
    ]
    for col in size_cols_census:
        if col not in laktab.columns:
            laktab[col] = 0

    orig_sizes = laktab[["Lakhely"] + size_cols_census].copy()

    # Template household sizes from LakasEpitő (one row per household)
    tmpl = pd.read_sql_query("SELECT LakhelyID, HáztartásID, size FROM LakasEpitő", conn)

    # Map LakhelyID -> Lakhely using Finishing_step
    city_map = pd.read_sql_query(
        "SELECT DISTINCT LakhelyID, TRIM(Lakhely) AS Lakhely FROM Finishing_step",
        conn,
    )
    if allowed_lakhely is not None:
        city_map = city_map[city_map["Lakhely"].isin(allowed_lakhely)]

    tmpl = tmpl.merge(city_map, on="LakhelyID", how="left")

    # Drop rows without Lakhely (in case some templates don't appear in Finishing_step)
    tmpl = tmpl.dropna(subset=["Lakhely"])

    # Count households by size per Lakhely
    size_counts = (
        tmpl
        .groupby(["Lakhely", "size"])["HáztartásID"]
        .nunique()
        .rename("Count")
        .reset_index()
    )

    # Convert to wide (sizes as columns)
    size_pivot = size_counts.pivot(index="Lakhely", columns="size", values="Count").fillna(0)

    # Build 1..5 and 6+ from template sizes
    tmpl_sizes = pd.DataFrame({"Lakhely": size_pivot.index}).reset_index(drop=True)
    for s in range(1, 6):
        col_name = f"{s} személyes háztartás"
        oszlop = size_pivot.get(s, pd.Series(0, index=size_pivot.index))
        tmpl_sizes[col_name] = oszlop.values.astype(int)

    # 6+ as sum over size >= 6
    six_plus = size_pivot[[c for c in size_pivot.columns if c >= 6]].sum(axis=1)
    tmpl_sizes["6+ személyes háztartás"] = six_plus.values.astype(int)

    # Merge with orig and compute diffs
    size_check = orig_sizes.merge(
        tmpl_sizes,
        on="Lakhely",
        how="left",
        suffixes=("_orig", "_sim"),
    ).fillna(0)

    diff_cols = []
    pct_cols = []
    for col in size_cols_census:
        col_orig = f"{col}_orig"
        col_sim = f"{col}_sim"
        dcol = f"{col}_diff"
        pctcol = f"{col}_pct_diff"
        size_check[dcol] = size_check[col_sim] - size_check[col_orig]
        _add_percentage_diff(size_check, col_orig, col_sim, pctcol)
        diff_cols.append(dcol)
        pct_cols.append(pctcol)

        stats = _compute_error_stats(size_check[col_orig], size_check[col_sim])
        print(
            f"[HHSIZE] {col}: MAE={stats['mae']:.2f}%, RMSE={stats['rmse']:.2f}, "
            f"MAPE={stats['mape']:.2f}%, r={stats['r']:.3f}"
        )
        print(f"         Max abs diff: {size_check[dcol].abs().max()}")

    size_check["total_abs_hhsize_diff"] = size_check[diff_cols].abs().sum(axis=1)
    print("Max total abs household-size diff per city:",
          size_check["total_abs_hhsize_diff"].max())

    # Histogram of total abs diff
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(size_check["total_abs_hhsize_diff"], bins=30)
    ax.set_title("Total absolute household-size difference per city")
    ax.set_xlabel("Total |difference| over household size categories")
    ax.set_ylabel("Number of settlements")
    fig.tight_layout()
    fig.savefig(OUTDIR / "hhsize_total_abs_diff_hist.pdf", dpi=150)
    plt.close(fig)

    # Mean percent diff per household size category
    mean_pct = size_check[pct_cols].mean(axis=0)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(size_cols_census, mean_pct.values)
    ax.set_xticklabels(size_cols_census, rotation=45, ha="right")
    ax.set_ylabel("Mean percent difference (%)")
    ax.set_title("Mean percent household-size difference per category")
    fig.tight_layout()
    fig.savefig(OUTDIR / "hhsize_mean_pct_diff_per_cat.pdf", dpi=150)
    plt.close(fig)

    # Compare NATIONAL total household-size distribution (stacked bar)
    total_orig = orig_sizes[size_cols_census].sum(axis=0)
    total_sim = tmpl_sizes[size_cols_census].sum(axis=0)

    x = np.arange(len(size_cols_census))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(x - width / 2, total_orig.values, width, label="Census")
    ax.bar(x + width / 2, total_sim.values, width, label="Simulated")
    ax.set_xticks(x)
    ax.set_xticklabels(size_cols_census, rotation=45, ha="right")
    ax.set_ylabel("Number of households (national total)")
    ax.set_title("National household-size distribution: census vs simulated")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTDIR / "hhsize_national_census_vs_sim.pdf", dpi=150)
    plt.close(fig)

    return size_check


# =========================================================
# 6) HOUSEHOLD-LEVEL AGE STRUCTURE
#    LakasEpitő age bins vs Finishing_step age_bin
# =========================================================

def analyse_household_age_structure(conn: sqlite3.Connection, allowed_lakhely=None):
    """
    Compare, for each private household (non-institution):
    - template age composition (n_lt15, n_15_29, n_30_64, n_65p from LakasEpitő)
    - simulated age composition from Finishing_step.age_bin

    Uses the 4 broad bins: <15, 15-29, 30-64, 65+.
    """

    print("\n=== HOUSEHOLD-LEVEL AGE STRUCTURE (PRIVATE HOUSEHOLDS) ===")

    # Load templates with age-bin counts
    tmpl = pd.read_sql_query(
        "SELECT LakhelyID, HáztartásID, size, n_lt15, n_15_29, n_30_64, n_65p FROM LakasEpitő",
        conn,
    )

    # Map LakhelyID -> Lakhely using Finishing_step
    city_map = pd.read_sql_query(
        "SELECT DISTINCT LakhelyID, TRIM(Lakhely) AS Lakhely FROM Finishing_step",
        conn,
    )
    if allowed_lakhely is not None:
        city_map = city_map[city_map["Lakhely"].isin(allowed_lakhely)]

    tmpl = tmpl.merge(city_map, on="LakhelyID", how="left")
    tmpl = tmpl.dropna(subset=["Lakhely"])

    # Restrict to selected settlements if filter is active
    if allowed_lakhely is not None:
        tmpl = tmpl[tmpl["Lakhely"].isin(allowed_lakhely)]

    # Keep only private households (exclude "I_" institutional IDs)
    tmpl["HáztartásID_str"] = tmpl["HáztartásID"].astype(str)
    tmpl_priv = tmpl[~tmpl["HáztartásID_str"].str.startswith("I_")].copy()

    # Rename template columns to *_target
    tmpl_age = tmpl_priv[[
        "Lakhely", "HáztartásID", "size",
        "n_lt15", "n_15_29", "n_30_64", "n_65p"
    ]].copy()
    tmpl_age = tmpl_age.rename(columns={
        "n_lt15": "<15_target",
        "n_15_29": "15-29_target",
        "n_30_64": "30-64_target",
        "n_65p": "65+_target",
    })

    # Simulated per-household age counts from Finishing_step
    sim_age_hh = pd.read_sql_query(
        """
        SELECT
          LakhelyID,
          TRIM(Lakhely) AS Lakhely,
          HáztartásID,
          age_bin,
          COUNT(*) AS Count
        FROM Finishing_step
        GROUP BY LakhelyID, TRIM(Lakhely), HáztartásID, age_bin
        """,
        conn,
    )

    if allowed_lakhely is not None:
        sim_age_hh = sim_age_hh[sim_age_hh["Lakhely"].isin(allowed_lakhely)]

    # Restrict to private households here as well
    sim_age_hh["HáztartásID_str"] = sim_age_hh["HáztartásID"].astype(str)
    sim_age_hh = sim_age_hh[~sim_age_hh["HáztartásID_str"].str.startswith("I_")]

    # Pivot to wide: one row per (Lakhely, HáztartásID), columns = age_bin
    sim_age_wide = sim_age_hh.pivot_table(
        index=["Lakhely", "HáztartásID"],
        columns="age_bin",
        values="Count",
        fill_value=0,
        aggfunc="sum",
    ).reset_index()

    # Ensure all 4 bins exist
    for col in ["<15", "15-29", "30-64", "65+"]:
        if col not in sim_age_wide.columns:
            sim_age_wide[col] = 0

    # Rename simulated columns to *_sim
    sim_age_wide = sim_age_wide.rename(columns={
        "<15": "<15_sim",
        "15-29": "15-29_sim",
        "30-64": "30-64_sim",
        "65+": "65+_sim",
    })

    # Align dtypes for merge key
    tmpl_age["HáztartásID"] = tmpl_age["HáztartásID"].astype("int64")
    sim_age_wide["HáztartásID"] = sim_age_wide["HáztartásID"].astype("int64")

    # Merge templates with simulated age structure
    hh_age = tmpl_age.merge(
        sim_age_wide,
        on=["Lakhely", "HáztartásID"],
        how="left"
    ).fillna(0)

    # Compute diff columns and total abs diff per household
    age_bins = ["<15", "15-29", "30-64", "65+"]
    diff_cols = []
    per_capita_cols = []
    for b in age_bins:
        tcol = f"{b}_target"
        scol = f"{b}_sim"
        dcol = f"{b}_diff"
        hh_age[dcol] = hh_age[scol] - hh_age[tcol]
        diff_cols.append(dcol)

    # total abs diff per HH
    hh_age["total_abs_age_diff"] = hh_age[diff_cols].abs().sum(axis=1)
    # per-capita mismatch (normalised by HH size)
    hh_age["per_capita_age_diff"] = hh_age["total_abs_age_diff"] / hh_age["size"].replace(0, np.nan)

    # Summary stats
    print("Number of private households with age info:", len(hh_age))
    print("Max total abs age diff per household:",
          hh_age["total_abs_age_diff"].max())
    print("Mean total abs age diff per household:",
          hh_age["total_abs_age_diff"].mean())
    print("Mean per-capita age diff per household:",
          hh_age["per_capita_age_diff"].mean())

    # Histogram of household-level total abs age diff
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(hh_age["total_abs_age_diff"], bins=30)
    ax.set_title("Total absolute age-bin difference per household (private)")
    ax.set_xlabel("Total |difference| over 4 broad age bins")
    ax.set_ylabel("Number of households")
    fig.tight_layout()
    fig.savefig(OUTDIR / "hh_age_total_abs_diff_hist.pdf", dpi=150)
    plt.close(fig)

    # Histogram of per-capita mismatch
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(hh_age["per_capita_age_diff"].dropna(), bins=30)
    ax.set_title("Per-capita age-bin mismatch per household (private)")
    ax.set_xlabel("Total |difference| / household size")
    ax.set_ylabel("Number of households")
    fig.tight_layout()
    fig.savefig(OUTDIR / "hh_age_per_capita_diff_hist.pdf", dpi=150)
    plt.close(fig)

    # Mean mismatch by household size
    size_summary = (
        hh_age.groupby("size")["total_abs_age_diff"]
        .mean()
        .reset_index()
        .sort_values("size")
    )
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(size_summary["size"].astype(str), size_summary["total_abs_age_diff"].values)
    ax.set_xlabel("Household size (template size)")
    ax.set_ylabel("Mean total abs age-bin difference")
    ax.set_title("Mean household age mismatch by household size")
    fig.tight_layout()
    fig.savefig(OUTDIR / "hh_age_mean_abs_diff_by_size.pdf", dpi=150)
    plt.close(fig)

    return hh_age


# =========================================================
# MAIN
# =========================================================

def main():
    conn = sqlite3.connect(DB_PATH)

    # Determine which settlement names we keep, based on LakhelyID filter
    allowed_lakhely = get_allowed_lakhely(conn)

    # Load TelepulesOsszegzett and (optionally) restrict to selected settlements
    helytab_full = load_telepules(conn)
    if allowed_lakhely is not None:
        helytab = helytab_full[helytab_full["Lakhely"].isin(allowed_lakhely)].copy()
    else:
        helytab = helytab_full

    # 1) Sex
    sex_check = analyse_sex(conn, helytab, allowed_lakhely=allowed_lakhely)

    # 2) Age (10-year bins)
    age_check = analyse_age(conn, helytab, allowed_lakhely=allowed_lakhely)

    # 3) Education
    edu_check = analyse_education(conn, helytab, allowed_lakhely=allowed_lakhely)

    # 4) Labour
    labour_check = analyse_labour(conn, allowed_lakhely=allowed_lakhely)

    # 5) Household sizes
    hhsize_check = analyse_household_sizes(conn, allowed_lakhely=allowed_lakhely)

    # 6) Household-level age structure (new)
    hh_age_check = analyse_household_age_structure(conn, allowed_lakhely=allowed_lakhely)

    conn.close()
    print("\nAll analyses completed. Figures saved to:", OUTDIR)


if __name__ == "__main__":
    main()