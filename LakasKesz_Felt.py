import sqlite3
import pandas as pd
import numpy as np
import math
import random
from dataclasses import dataclass
from functools import lru_cache
from collections import deque
from typing import Dict, List, Tuple, Any, Optional, Set

from Table import tablakezelo

# =========================================================
# BASIC SETUP
# =========================================================

DB_PATH = "populacio.db"

data = tablakezelo(DB_PATH, "Szimulacio")
data.create_table()
data.create_sratio_table()
data.create_aratio_table()
data.create_lakasfel_table("Lakasfeltoltes")
data.reset_table()

# City and household aggregate tables
helytab = pd.read_sql_query("SELECT * FROM TelepulesOsszegzett", data.conn)
laktab = pd.read_sql_query("SELECT * FROM LakasOsszegzett", data.conn)

# Drop old household tables if they exist
with sqlite3.connect(DB_PATH) as conn_drop:
    cur_d = conn_drop.cursor()
    cur_d.execute("PRAGMA foreign_keys=OFF;")
    cur_d.execute("DROP TABLE IF EXISTS lakasfel_tag;")
    cur_d.execute("DROP TABLE IF EXISTS LakasEpitő;")
    conn_drop.commit()

# =========================================================
# UTILS
# =========================================================

def _as_int(x, default=0) -> int:
    try:
        if pd.isna(x):
            return default
        return int(round(float(x)))
    except Exception:
        return default

# Real age totals from population table (by city *name*)
def valoskor(nev: str) -> Dict[str, int]:
    """
    Return age bins <15, 15-29, 30-64, 65+ from Szimuláció for given city name.
    """
    q = """SELECT COUNT(*)
           FROM Szimuláció 
           WHERE TRIM(Lakhely) = ? AND CAST(Kor AS INTEGER) BETWEEN ? AND ?;"""
    conn = data.conn
    fi  = conn.execute(q, (nev, 0, 14)).fetchone()[0]
    fe  = conn.execute(q, (nev, 15, 29)).fetchone()[0]
    ko  = conn.execute(q, (nev, 30, 64)).fetchone()[0]
    ido = conn.execute(q, (nev, 65, 200)).fetchone()[0]
    return {"<15": fi, "15-29": fe, "30-64": ko, "65+": ido}

def m6_kiszam_multinom(avg_size, H6_count, min_size: int = 6, seed: int = 1234) -> Dict[int, int]:
    """
    Split '6+ személyes háztartás' into concrete sizes >= min_size.
    avg_size ~ average household size for 6+ group.
    Returns {size: number_of_households}.
    """
    H = _as_int(H6_count, 0)
    if H <= 0:
        return {}

    if pd.isna(avg_size):
        avg = float(min_size)
    else:
        avg = float(avg_size)
    if avg < min_size:
        avg = float(min_size)

    target_total = avg * H
    base_total = min_size * H
    extra = int(round(target_total - base_total))

    if extra <= 0:
        return {min_size: H}

    rng = np.random.default_rng(seed)
    sizes = np.full(H, min_size, dtype=int)
    # distribute "extra" persons randomly over the H households
    draws = rng.multinomial(extra, np.full(H, 1.0 / H))
    sizes += draws

    vals, counts = np.unique(sizes, return_counts=True)
    return {int(v): int(c) for v, c in zip(vals, counts)}

# =========================================================
# REGION-BASED AGE SPLITTING FOR INSTITUTIONS
# (only to get NON-INSTITUTION age totals, no individual weighting)
# =========================================================

REG_AGE_COLS = {
    "<15":   "Kor0_14",
    "15-29": "Kor15_29",
    "30-64": "Kor30_64",
    "65+":   "Kor65_plusz",
}

REG_AGE_CACHE: Dict[Tuple[str, str], Dict[str, float]] = {}

def get_region_age_shares(megye: str, tipus: str) -> Dict[str, float]:
    key = (megye, tipus)
    if key in REG_AGE_CACHE:
        return REG_AGE_CACHE[key]

    sub = helytab[(helytab["Vármegye"] == megye) & (helytab["Településtípus"] == tipus)]
    if sub.empty:
        REG_AGE_CACHE[key] = {b: 0.25 for b in ["<15", "15-29", "30-64", "65+"]}
        return REG_AGE_CACHE[key]

    totals = {}
    for bin_key, colname in REG_AGE_COLS.items():
        if colname not in sub.columns:
            totals[bin_key] = 0.0
        else:
            totals[bin_key] = float(sub[colname].sum())

    T = sum(totals.values())
    if T <= 0:
        REG_AGE_CACHE[key] = {b: 0.25 for b in ["<15", "15-29", "30-64", "65+"]}
        return REG_AGE_CACHE[key]

    shares = {b: totals[b] / T for b in ["<15", "15-29", "30-64", "65+"]}
    REG_AGE_CACHE[key] = shares
    return shares

def _split_inst_by_age_from_region(
    obs_age: Dict[str, int],
    inst_count: int,
    region_shares: Dict[str, float]
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Given observed age totals (obs_age) and number of institutional persons,
    return (inst_age, noninst_age), both per age bin.

    This is the ONLY place where regional age structure is used as a weight.
    Individual people are NOT weighted by any ad-hoc scores.
    """
    if inst_count <= 0:
        return {b: 0 for b in obs_age}, dict(obs_age)

    total_city = sum(obs_age.values())
    if total_city <= 0:
        inst_age = {"<15": 0, "15-29": 0, "30-64": inst_count, "65+": 0}
        noninst_age = {b: 0 for b in inst_age}
        return inst_age, noninst_age

    # expected regional composition
    exp = {b: region_shares.get(b, 0.0) * total_city for b in obs_age}
    diff = {b: max(0.0, obs_age[b] - exp[b]) for b in obs_age}
    excess_sum = sum(diff.values())

    inst_age_float = {}
    if excess_sum <= 0:
        for b in obs_age:
            inst_age_float[b] = region_shares.get(b, 0.25) * inst_count
    else:
        for b in obs_age:
            inst_age_float[b] = (diff[b] / excess_sum) * inst_count

    inst_floor = {b: int(math.floor(inst_age_float[b])) for b in inst_age_float}
    rem = {b: inst_age_float[b] - inst_floor[b] for b in inst_age_float}
    missing = inst_count - sum(inst_floor.values())
    if missing > 0:
        order = sorted(rem.keys(), key=lambda k: rem[k], reverse=True)
        for b in order[:missing]:
            inst_floor[b] += 1

    inst_age = inst_floor
    noninst_age = {}
    for b in obs_age:
        v = obs_age[b] - inst_age[b]
        if v < 0:
            v = 0
        noninst_age[b] = v

    # tiny rounding correction if needed
    lost = inst_count - sum(inst_age.values())
    if lost != 0:
        target_bin = max(obs_age.keys(), key=lambda k: obs_age[k])
        inst_age[target_bin] += lost
        noninst_age[target_bin] = max(0, obs_age[target_bin] - inst_age[target_bin])

    return inst_age, noninst_age

# =========================================================
# EXPECTED HOUSEHOLD DISTRIBUTION (USING NON-INSTIT POP)
# =========================================================

def varhatoeloszlas(row: pd.Series) -> Dict[str, Any]:
    """
    Build a dict with household size counts, NON-INSTITUTION age totals and labour totals
    for one city row from LakasOsszegzett.
    """
    varos = row["Helység megnevezése"]

    # --- Household size distribution (H1..H12) ---
    H1 = _as_int(row.get("1 személyes háztartás", 0))
    H2 = _as_int(row.get("2 személyes háztartás", 0))
    H3 = _as_int(row.get("3 személyes háztartás", 0))
    H4 = _as_int(row.get("4 személyes háztartás", 0))
    H5 = _as_int(row.get("5 személyes háztartás", 0))
    H6plus = _as_int(row.get("6+ személyes háztartás", 0))

    # Use the institution/homeless-corrected multiplier
    avg6 = row.get("Hat+ személyes háztartás szorzo (int./hajl. korrigált)", 6)

    H6_dict = m6_kiszam_multinom(avg6, H6plus, 6)
    H6 = H6_dict.get(6, 0)
    H7 = H6_dict.get(7, 0)
    H8 = H6_dict.get(8, 0)
    H9 = H6_dict.get(9, 0)
    H10 = H6_dict.get(10, 0)
    H11 = H6_dict.get(11, 0)
    H12 = H6_dict.get(12, 0)

    # --- Institutional count from laktab (census) ---
    inst_count = _as_int(row.get("Intézeti háztartásban élő személy", 0), 0)

    # --- Observed age totals from Szimuláció ---
    obs_age = valoskor(varos)  # {"<15":..., ...}

    # --- Find region info in TelepulesOsszegzett ---
    hely_row = helytab[helytab["Helység megnevezése"] == varos]
    if hely_row.empty:
        region_shares = {b: 0.25 for b in ["<15", "15-29", "30-64", "65+"]}
    else:
        hr = hely_row.iloc[0]
        megye = str(hr["Vármegye"])
        tipus = str(hr["Településtípus"])
        region_shares = get_region_age_shares(megye, tipus)

    # Regional weighting ONLY to split inst vs non-inst by age
    inst_age, noninst_age = _split_inst_by_age_from_region(obs_age, inst_count, region_shares)
    kor0_14 = noninst_age["<15"]
    kor15_29 = noninst_age["15-29"]
    kor30_64 = noninst_age["30-64"]
    kor65p = noninst_age["65+"]

    # --- Labour totals from city-level household counts (already private households only) ---
    dolg = (
        0 * _as_int(row.get("Nincs foglalkoztatott a háztartásban", 0)) +
        1 * _as_int(row.get("1 foglalkoztatott személy van a háztartásban", 0)) +
        2 * _as_int(row.get("2 foglalkoztatott személy van a háztartásban", 0)) +
        3 * _as_int(row.get("3 vagy több foglalkoztatott személy van a háztartásban", 0))
    )
    munkanel = (
        0 * _as_int(row.get("Nincs munkanélküli személy a háztartásban", 0)) +
        1 * _as_int(row.get("1 munkanélküli személy van a háztartásban", 0)) +
        2 * _as_int(row.get("2 munkanélküli személy van a háztartásban", 0)) +
        3 * _as_int(row.get("3 vagy több munkanélküli személy van a háztartásban", 0))
    )
    inak = (
        0 * _as_int(row.get("Nincs ellátásban részesülő inaktív személy a háztartásban", 0)) +
        1 * _as_int(row.get("1 ellátásban részesülő inaktív személy van a háztartásban", 0)) +
        2 * _as_int(row.get("2 ellátásban részesülő inaktív személy van a háztartásban", 0)) +
        3 * _as_int(row.get("3 vagy több ellátásban részesülő inaktív személy van a háztartásban", 0))
    )
    elt = (
        0 * _as_int(row.get("Nincs eltartott személy van a háztartásban", 0)) +
        1 * _as_int(row.get("1 eltartott személy van a háztartásban", 0)) +
        2 * _as_int(row.get("2 eltartott személy van a háztartásban", 0)) +
        3 * _as_int(row.get("3 vagy több eltartott személy van a háztartásban", 0))
    )

    adatok = {
        "Lakhely": varos,
        "H1": H1,
        "H2": H2,
        "H3": H3,
        "H4": H4,
        "H5": H5,
        "H6": H6,
        "H7": H7,
        "H8": H8,
        "H9": H9,
        "H10": H10,
        "H11": H11,
        "H12": H12,
        "H6+ szorzo (int./hajl. korrigált)": float(avg6) if not pd.isna(avg6) else 6.0,
        "Kor0-14": kor0_14,
        "Kor15-29": kor15_29,
        "Kor30-64": kor30_64,
        "Kor65+": kor65p,
        "Foglalkoztatott": dolg,
        "Munkanélküli": munkanel,
        "Inaktív": inak,
        "Eltartott": elt,
        "InstCount": inst_count,
        "ObsAge_<15": obs_age["<15"],
        "ObsAge_15-29": obs_age["15-29"],
        "ObsAge_30-64": obs_age["30-64"],
        "ObsAge_65+": obs_age["65+"],
    }
    return adatok

# =========================================================
# AGE TEMPLATE BUILDING
# =========================================================

@lru_cache(maxsize=None)
def enumerate_age_splits(size: int) -> List[Tuple[int, int, int, int]]:
    """
    All 4-tuples (n_0-14, n_15-29, n_30-64, n_65+) summing to 'size'.
    """
    out = []
    for a in range(size + 1):
        for b in range(size - a + 1):
            for c in range(size - a - b + 1):
                d = size - a - b - c
                out.append((a, b, c, d))
    return out

@dataclass
class AgeTemplateFit:
    counts: Dict[Tuple[int, Tuple[int, int, int, int]], int]
    achieved: Dict[str, int]
    log: List[str]

def fit_age_templates(
    H_by_size: Dict[int, int],
    age_totals: Dict[str, int],
    max_iter: int = 200,
    tol: float = 1e-6
) -> AgeTemplateFit:
    """
    Fractional weights over all (size, age-split) combos, then normalized & rounded.
    """
    types: List[Tuple[int, Tuple[int, int, int, int]]] = []
    for size, Hs in H_by_size.items():
        if Hs <= 0:
            continue
        for split in enumerate_age_splits(size):
            types.append((size, split))

    if not types:
        raise ValueError("No households to fit (H_by_size is empty or all zero).")

    T = sum(age_totals.values())
    if T <= 0:
        raise ValueError("Total population is zero for this city (age_totals sum to 0).")

    p = np.array([
        age_totals['<15'] / T,
        age_totals['15-29'] / T,
        age_totals['30-64'] / T,
        age_totals['65+'] / T,
    ], dtype=float)

    # Initial weights
    w = np.ones(len(types), dtype=float)
    for i, (size, split) in enumerate(types):
        coeff = math.factorial(size)
        for k in split:
            coeff /= math.factorial(k)
        w[i] = max(coeff * np.prod(p ** np.array(split)), 1e-14)

    # Normalize for each size
    for size, Hs in H_by_size.items():
        idxs = [j for j, (sz, _) in enumerate(types) if sz == size]
        s = w[idxs].sum()
        if s > 0:
            w[idxs] *= (Hs / s)

    def implied_age(wvec: np.ndarray) -> np.ndarray:
        tot = np.zeros(4, dtype=float)
        for val, (_, split) in zip(wvec, types):
            tot += val * np.array(split, dtype=float)
        return tot

    target_age = np.array([
        age_totals['<15'],
        age_totals['15-29'],
        age_totals['30-64'],
        age_totals['65+'],
    ], dtype=float)

    # IPF-like refinement
    for _ in range(max_iter):
        cur = implied_age(w)
        if np.allclose(cur, target_age, atol=tol, rtol=0):
            break
        scale = np.divide(target_age, cur, out=np.ones_like(cur), where=(cur > 0))
        new_w = []
        for val, (_, split) in zip(w, types):
            svec = np.array(split, dtype=float)
            if svec.sum() == 0:
                new_w.append(val)
                continue
            factor = float((svec / svec.sum() * scale).sum())
            new_w.append(val * factor)
        w = np.array(new_w, dtype=float)
        # renormalize within each size
        for size, Hs in H_by_size.items():
            idxs = [j for j, (sz, _) in enumerate(types) if sz == size]
            s = w[idxs].sum()
            if s > 0:
                w[idxs] *= (Hs / s)

    # Round
    w_floor = np.floor(w).astype(int)
    remainder = w - w_floor
    counts: Dict[Tuple[int, Tuple[int, int, int, int]], int] = {}
    for i, key in enumerate(types):
        counts[key] = w_floor[i]

    # Ensure household counts per size
    for size, Hs in H_by_size.items():
        idxs = [j for j, (sz, _) in enumerate(types) if sz == size]
        have = int(sum(w_floor[j] for j in idxs))
        deficit = Hs - have
        if deficit > 0:
            order = sorted(idxs, key=lambda j: remainder[j], reverse=True)
            for j in order[:deficit]:
                counts[types[j]] += 1

    # Achieved age totals
    ach = np.zeros(4, dtype=int)
    for (size, split), c in counts.items():
        ach += c * np.array(split, dtype=int)
    achieved = {
        '<15': int(ach[0]),
        '15-29': int(ach[1]),
        '30-64': int(ach[2]),
        '65+': int(ach[3]),
    }

    log = [f"Target ages: {age_totals}", f"Achieved ages: {achieved}"]
    return AgeTemplateFit(counts=counts, achieved=achieved, log=log)

def expand_age_templates_to_rows(
    lakhely_id: Any,
    counts: Dict[Tuple[int, Tuple[int, int, int, int]], int],
    start_household_id: int = 0
) -> pd.DataFrame:
    """
    One row per household with its size and age split.
    """
    rows = []
    hid = int(start_household_id)
    for (size, split), c in counts.items():
        for _ in range(int(c)):
            rows.append({
                "LakhelyID": int(lakhely_id),
                "HáztartásID": hid,
                "size": int(size),
                "n_lt15": int(split[0]),
                "n_15_29": int(split[1]),
                "n_30_64": int(split[2]),
                "n_65p": int(split[3]),
            })
            hid += 1
    return pd.DataFrame(rows)

# =========================================================
# LABOUR SPREAD (no inactive_other)
# =========================================================

@dataclass
class LabourSpread:
    templates: pd.DataFrame
    shaved: Dict[str, int]
    log: List[str]

def spread_labour_totals_no_inactive(
    templates: pd.DataFrame,
    labour_totals: Dict[str, int]
) -> LabourSpread:
    """
    Allocate labour categories (emp, unemp, inact_benefit, dependent) over households.
    """
    log: List[str] = []
    df = templates.copy()
    df["n_emp"] = 0
    df["n_unemp"] = 0
    df["n_inact_benefit"] = 0
    df["n_dep"] = 0

    pop_total = int(df["size"].sum())
    tgt_emp = int(labour_totals.get("emp", 0))
    tgt_un = int(labour_totals.get("unemp", 0))
    tgt_inb = int(labour_totals.get("inact_benefit", 0))

    tgt_dep = pop_total - (tgt_emp + tgt_un + tgt_inb)

    df["work_cap"] = df[["n_15_29", "n_30_64", "n_65p"]].sum(axis=1)
    df["child_cap"] = df["n_lt15"]

    def allocate(category: str, target: int, cap_col: str) -> int:
        if target <= 0:
            return 0
        cap = df[cap_col].to_numpy(dtype=int)
        total_cap = int(cap.sum())
        if total_cap <= 0:
            return 0
        frac = target * (cap / total_cap)
        base = np.floor(frac).astype(int)
        placed = base.copy()
        rem = target - int(base.sum())
        if rem > 0:
            order = np.argsort(-(frac - base))
            for j in order[:rem]:
                placed[j] += 1
        placed = np.minimum(placed, cap)
        df[f"n_{category}"] += placed
        df[cap_col] = (df[cap_col] - placed).clip(lower=0)
        return int(placed.sum())

    got_emp = allocate("emp", tgt_emp, "work_cap")
    got_un = allocate("unemp", tgt_un, "work_cap")
    got_inb = allocate("inact_benefit", tgt_inb, "work_cap")

    shave = {
        "emp": tgt_emp - got_emp,
        "unemp": tgt_un - got_un,
        "inact_benefit": tgt_inb - got_inb,
    }
    tgt_dep2 = tgt_dep + sum(max(0, v) for v in shave.values())

    _ = allocate("dep", min(tgt_dep2, int(df["child_cap"].sum())), "child_cap")

    df["leftover"] = df["size"] - df[["n_emp", "n_unemp", "n_inact_benefit", "n_dep"]].sum(axis=1)
    _ = allocate("dep", tgt_dep2 - int(df["n_dep"].sum()), "leftover")

    df["leftover"] = df["size"] - df[["n_emp", "n_unemp", "n_inact_benefit", "n_dep"]].sum(axis=1)
    leftover_total = int(df["leftover"].sum())
    if leftover_total != 0:
        _ = allocate("dep", leftover_total, "leftover")

    shaved_totals = {k: int(max(0, v)) for k, v in shave.items()}
    return LabourSpread(
        templates=df.drop(columns=["work_cap", "child_cap", "leftover"]),
        shaved=shaved_totals,
        log=log
    )

@dataclass
class TemplateBuild:
    templates: pd.DataFrame
    logs: List[str]

def build_household_templates_for_city(
    lakhely_id: Any,
    H_by_size: Dict[int, int],
    age_totals: Dict[str, int],
    labour_totals: Dict[str, int],
    start_household_id: int = 0
) -> TemplateBuild:
    logs: List[str] = []

    age_fit = fit_age_templates(H_by_size, age_totals)
    logs += [f"[AGE] {m}" for m in age_fit.log]

    tmpl_age = expand_age_templates_to_rows(
        lakhely_id=lakhely_id,
        counts=age_fit.counts,
        start_household_id=start_household_id
    )

    lab = spread_labour_totals_no_inactive(tmpl_age, labour_totals)
    logs += [f"[LAB] {m}" for m in lab.log]
    if any(v > 0 for v in lab.shaved.values()):
        logs.append(f"[LAB] Shaved (moved to dependent): {lab.shaved}")

    return TemplateBuild(templates=lab.templates, logs=logs)

# =========================================================
# ASSIGN PEOPLE TO PRIVATE HOUSEHOLDS
# =========================================================

CITY_COL = "LakhelyID"
PEOPLE_TABLE = "Szimuláció"
ID_COL = "LakosID"
AGE_COL = "Kor"
LABOUR_COL = "Munkaviszony"

TEMPLATES_TABLE = "LakasEpitő"
LINK_TABLE = "lakasfel_tag"

AGE_BINS = ["<15", "15-29", "30-64", "65+"]
LABOUR_CATS = ["emp", "unemp", "inact_benefit", "dependent"]

def _age_bin_from_value(v: Any) -> str:
    if pd.isna(v):
        return "<15"
    try:
        a = int(v)
        if a < 15:
            return "<15"
        if a < 30:
            return "15-29"
        if a < 65:
            return "30-64"
        return "65+"
    except Exception:
        s = str(v).strip().replace("–", "-").replace(" ", "")
        if s in ("0-14", "0–14", "<15"):
            return "<15"
        if s in ("15-29", "15–29"):
            return "15-29"
        if s in ("30-64", "30–64"):
            return "30-64"
        if s in ("65+", "65plus"):
            return "65+"
        return "30-64"

def _labour_cat_from_value(v: Any, age_bin: str) -> str:
    s = ("" if pd.isna(v) else str(v)).strip().lower()
    if "foglalk" in s or "employed" in s:
        return "emp"
    if "munkanélk" in s or "munka nelk" in s or "unemploy" in s:
        return "unemp"
    if "nyugd" in s or "ellátás" in s or "benef" in s:
        return "inact_benefit"
    if "eltartott" in s or "dependent" in s:
        return "dependent"
    if "tanul" in s or "diák" in s or "student" in s:
        return "dependent"

    if age_bin == "<15":
        return "dependent"
    if age_bin == "65+":
        return "inact_benefit"
    return "unemp"

def make_supply_queues(
    conn: sqlite3.Connection,
    lakhely_id: Any,
    chunksize: int = 200_000,
) -> Dict[Tuple[str, str], deque[int]]:
    """
    Build queues of ALL people by (age_bin, labour_cat) for this city.

    No exclusions here. We first fill private households,
    then leftover people (if any) will be sent to the institution.
    """
    queues: Dict[Tuple[str, str], deque[int]] = {
        (a, l): deque() for a in AGE_BINS for l in LABOUR_CATS
    }
    sql = f'SELECT "{ID_COL}", "{AGE_COL}", "{LABOUR_COL}" FROM {PEOPLE_TABLE} WHERE "{CITY_COL}" = ?'
    for chunk in pd.read_sql_query(sql, conn, params=(lakhely_id,), chunksize=chunksize):
        for _, r in chunk.iterrows():
            pid = int(r[ID_COL])
            ageb = _age_bin_from_value(r[AGE_COL])
            lab = _labour_cat_from_value(r[LABOUR_COL], ageb)
            queues[(ageb, lab)].append(pid)

    # Shuffle within each queue for randomness
    rnd = random.Random(int(lakhely_id) ^ 0x5A17)
    for key in queues:
        q = list(queues[key])
        rnd.shuffle(q)
        queues[key] = deque(q)
    return queues

ELIGIBLE_AGE_FOR = {
    "emp": ["15-29", "30-64", "65+"],
    "unemp": ["15-29", "30-64", "65+"],
    "inact_benefit": ["15-29", "30-64", "65+"],
    "dependent": ["<15", "15-29", "30-64", "65+"],
}

LABOUR_AGE_PRIORITY = {
    "emp": ["30-64", "15-29", "65+"],
    "unemp": ["15-29", "30-64", "65+"],
    "inact_benefit": ["65+", "30-64", "15-29"],
    "dependent": ["<15", "15-29", "30-64", "65+"],
}

AGE_FALLBACKS = {
    "<15": ["15-29", "30-64", "65+"],
    "15-29": ["30-64", "65+"],
    "30-64": ["15-29", "65+"],
    "65+": ["30-64", "15-29"],
}

def normalize_labour_targets_to_size(row: pd.Series) -> Tuple[Dict[str, int], List[str]]:
    logs: List[str] = []
    size = int(row["size"])
    L = {
        "emp": int(row["n_emp"]),
        "unemp": int(row["n_unemp"]),
        "inact_benefit": int(row["n_inact_benefit"]),
        "dependent": int(row["n_dep"]),
    }
    diff = size - sum(L.values())
    if diff > 0:
        L["dependent"] += diff
        logs.append(f"Filled +{diff} into dependent.")
    elif diff < 0:
        over = -diff
        for k in ["dependent", "inact_benefit", "unemp", "emp"]:
            if over <= 0:
                break
            cut = min(L[k], over)
            if cut > 0:
                L[k] -= cut
                over -= cut
                logs.append(f"Reduced {k} by {cut}.")
        if over > 0:
            raise ValueError("Cannot normalize labour to size (negative capacity).")
    return L, logs

def plan_age_lab_allocation_no_inactive(row: pd.Series) -> Tuple[Dict[Tuple[str, str], int], List[str]]:
    logs: List[str] = []
    A = {
        "<15": int(row["n_lt15"]),
        "15-29": int(row["n_15_29"]),
        "30-64": int(row["n_30_64"]),
        "65+": int(row["n_65p"]),
    }
    L_in = {
        "emp": int(row.get("n_emp", 0)),
        "unemp": int(row.get("n_unemp", 0)),
        "inact_benefit": int(row.get("n_inact_benefit", 0)),
        "dependent": int(row.get("n_dep", 0)),
    }
    size = int(row["size"])
    if sum(L_in.values()) != size:
        L, llog = normalize_labour_targets_to_size(pd.Series({"size": size, **L_in}))
        logs += llog
    else:
        L = L_in

    alloc: Dict[Tuple[str, str], int] = {}

    # dependents first
    need = L["dependent"]
    for age in LABOUR_AGE_PRIORITY["dependent"]:
        if need <= 0:
            break
        take = min(need, A[age])
        if take > 0:
            alloc[(age, "dependent")] = alloc.get((age, "dependent"), 0) + take
            A[age] -= take
            need -= take
    L["dependent"] = need

    # workers
    for lab in ["emp", "unemp", "inact_benefit"]:
        need = L[lab]
        if need <= 0:
            continue
        for age in LABOUR_AGE_PRIORITY[lab]:
            if age not in ELIGIBLE_AGE_FOR[lab] or need <= 0:
                continue
            take = min(need, A[age])
            if take > 0:
                alloc[(age, lab)] = alloc.get((age, lab), 0) + take
                A[age] -= take
                need -= take
        L[lab] = need
        if L[lab] > 0:
            logs.append(f"Spilled {L[lab]} from {lab} to dependent (age capacity).")
            L["dependent"] += L[lab]
            L[lab] = 0

    # remaining dependents
    need = L["dependent"]
    if need > 0:
        rem = sum(A.values())
        if rem < need:
            logs.append(f"Trim dependent from {need} to {rem} due to age slots.")
            need = rem
        for age in ["<15", "15-29", "30-64", "65+"]:
            if need <= 0:
                break
            if A[age] <= 0:
                continue
            take = min(need, A[age])
            alloc[(age, "dependent")] = alloc.get((age, "dependent"), 0) + take
            A[age] -= take
            need -= take

    return alloc, logs

def _pop_ids_no_inactive(
    queues: Dict[Tuple[str, str], deque],
    age_bin: str,
    lab: str,
    need: int,
    age_fallbacks: Dict[str, List[str]]
) -> List[int]:
    taken: List[int] = []

    q = queues.get((age_bin, lab))
    while q and need > 0 and q:
        taken.append(q.popleft())
        need -= 1
    if need == 0:
        return taken

    # same lab, other ages
    for fb_age in age_fallbacks.get(age_bin, []):
        if need == 0:
            break
        q = queues.get((fb_age, lab))
        while q and need > 0 and q:
            taken.append(q.popleft())
            need -= 1
    if need == 0:
        return taken

    orders = {
        "emp": ["unemp", "inact_benefit", "dependent"],
        "unemp": ["inact_benefit", "emp", "dependent"],
        "inact_benefit": ["unemp", "emp", "dependent"],
        "dependent": ["inact_benefit", "unemp", "emp"],
    }
    order = orders.get(lab, ["dependent"])

    # same age, other labour
    for fb_lab in order:
        if need == 0:
            break
        q = queues.get((age_bin, fb_lab))
        while q and need > 0 and q:
            taken.append(q.popleft())
            need -= 1
    if need == 0:
        return taken

    # other ages, other labour
    for fb_age in age_fallbacks.get(age_bin, []):
        if need == 0:
            break
        for fb_lab in order:
            if need == 0:
                break
            q = queues.get((fb_age, fb_lab))
            while q and need > 0 and q:
                taken.append(q.popleft())
                need -= 1

    return taken

def assign_people_to_templates_no_inactive(
    templates: pd.DataFrame,
    supply_queues: Dict[Tuple[str, str], deque[int]],
    lakhely_id: int
) -> Tuple[pd.DataFrame, List[str]]:
    logs: List[str] = []
    out_rows: List[Dict[str, Any]] = []

    order = np.argsort(-(templates["size"].to_numpy()))
    for idx in order:
        row = templates.iloc[idx]
        hid = int(row["HáztartásID"])
        plan, plogs = plan_age_lab_allocation_no_inactive(row)
        for s in plogs:
            logs.append(f"HZ {hid}: {s}")

        for (age, lab), need in plan.items():
            if need <= 0:
                continue
            picked = _pop_ids_no_inactive(
                queues=supply_queues,
                age_bin=age,
                lab=lab,
                need=int(need),
                age_fallbacks=AGE_FALLBACKS,
            )
            for pid in picked:
                out_rows.append({
                    "LakhelyID": lakhely_id,
                    "HáztartásID": str(hid),
                    "LakosID": pid,
                    "age_bin": age,
                    "labour_cat": lab,
                })
            miss = int(need) - len(picked)
            if miss > 0:
                logs.append(f"City {lakhely_id} HZ {hid}: shortage {miss} for ({age}, {lab}).")

    assignments = pd.DataFrame(out_rows)
    return assignments, logs

# =========================================================
# INSTITUTIONS: LEFTOVER PEOPLE → I_<LakhelyID>
# =========================================================

def build_institution_assignments(
    conn: sqlite3.Connection,
    lakhely_id: int,
    inst_ids: List[int],
) -> pd.DataFrame:
    """
    Build lakasfel_tag-style rows for institutional residents.

    HáztartásID is the string I_<LakhelyID>.
    Now, inst_ids is simply the set of people who were NOT assigned
    to any private household (the 'excess' people).
    """
    if not inst_ids:
        return pd.DataFrame(columns=["LakhelyID", "HáztartásID", "LakosID", "age_bin", "labour_cat"])

    sql = f"""
    SELECT LakosID, Kor, Munkaviszony
    FROM Szimuláció
    WHERE LakosID IN ({",".join(["?"] * len(inst_ids))})
    """
    people = pd.read_sql_query(sql, conn, params=inst_ids)
    if people.empty:
        return pd.DataFrame(columns=["LakhelyID", "HáztartásID", "LakosID", "age_bin", "labour_cat"])

    rows = []
    inst_hid = f"I_{lakhely_id}"

    for _, r in people.iterrows():
        pid = int(r["LakosID"])
        ageb = _age_bin_from_value(r["Kor"])
        lab = _labour_cat_from_value(r["Munkaviszony"], ageb)
        rows.append({
            "LakhelyID": lakhely_id,
            "HáztartásID": inst_hid,
            "LakosID": pid,
            "age_bin": ageb,
            "labour_cat": lab,
        })
    return pd.DataFrame(rows)

# =========================================================
# VALIDATION
# =========================================================

def validate_city(templates: pd.DataFrame, assignments: pd.DataFrame) -> Dict[str, Any]:
    plan_age = {
        "<15": int(templates["n_lt15"].sum()),
        "15-29": int(templates["n_15_29"].sum()),
        "30-64": int(templates["n_30_64"].sum()),
        "65+": int(templates["n_65p"].sum()),
    }
    asg_age = assignments["age_bin"].value_counts().to_dict()
    for k in plan_age:
        asg_age[k] = int(asg_age.get(k, 0))

    plan_lab = {
        "emp": int(templates["n_emp"].sum()),
        "unemp": int(templates["n_unemp"].sum()),
        "inact_benefit": int(templates["n_inact_benefit"].sum()),
        "dependent": int(templates["n_dep"].sum()),
    }
    asg_lab = assignments["labour_cat"].value_counts().to_dict()
    for k in plan_lab:
        asg_lab[k] = int(asg_lab.get(k, 0))

    return {
        "planned_people": int(templates["size"].sum()),
        "assigned_people": int(len(assignments)),
        "planned_age": plan_age,
        "assigned_age": asg_age,
        "planned_labour": plan_lab,
        "assigned_labour": asg_lab,
    }

# =========================================================
# DB SCHEMA AND PERSISTENCE
# =========================================================

def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {TEMPLATES_TABLE} (
        LakhelyID        INTEGER NOT NULL,
        HáztartásID      INTEGER NOT NULL UNIQUE,
        size             INTEGER NOT NULL,
        n_lt15           INTEGER NOT NULL,
        n_15_29          INTEGER NOT NULL,
        n_30_64          INTEGER NOT NULL,
        n_65p            INTEGER NOT NULL,
        n_emp            INTEGER NOT NULL,
        n_unemp          INTEGER NOT NULL,
        n_inact_benefit  INTEGER NOT NULL,
        n_dep            INTEGER NOT NULL
    )
    """)
    # HáztartásID TEXT here so we can store "I_<LakhelyID>" as well
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {LINK_TABLE} (
        LakhelyID   INTEGER NOT NULL,
        HáztartásID TEXT    NOT NULL,
        LakosID     INTEGER NOT NULL,
        age_bin     TEXT,
        labour_cat  TEXT,
        RunID       TEXT,
        PRIMARY KEY (LakosID, RunID)
    )
    """)
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_tag_haz ON {LINK_TABLE}(HáztartásID)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_tag_city ON {LINK_TABLE}(LakhelyID)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_pop_city ON {PEOPLE_TABLE}({CITY_COL})")
    conn.commit()

def persist_templates(conn: sqlite3.Connection, templates: pd.DataFrame):
    cols = [
        "LakhelyID",
        "HáztartásID",
        "size",
        "n_lt15",
        "n_15_29",
        "n_30_64",
        "n_65p",
        "n_emp",
        "n_unemp",
        "n_inact_benefit",
        "n_dep",
    ]
    templates[cols].to_sql(TEMPLATES_TABLE, conn, if_exists="append", index=False)

def persist_assignments(conn: sqlite3.Connection, assignments: pd.DataFrame, run_id: str):
    if assignments.empty:
        return
    df = assignments.copy()
    df["RunID"] = run_id
    df.to_sql(LINK_TABLE, conn, if_exists="append", index=False)

def assign_city(
    conn: sqlite3.Connection,
    lakhely_id: int,
    templates_city: pd.DataFrame,
):
    """
    Assign ALL people in this city to private households as far as possible.
    Leftover people will be detected later and sent to the institution.
    """
    queues = make_supply_queues(conn, lakhely_id)
    assignments, logs = assign_people_to_templates_no_inactive(templates_city, queues, lakhely_id)
    return assignments, logs

# =========================================================
# MAIN
# =========================================================

conn = sqlite3.connect(DB_PATH)
ensure_schema(conn)

all_templates = []
run_id = "run_v1"

for index, row in laktab.head(5).iterrows():   # remove .head(5) when ready
    lakhely_id = int(index) + 1
    hely = row.get("Helység megnevezése", lakhely_id)

    vege = varhatoeloszlas(row)

    H_by_size = {s: _as_int(vege.get(f"H{s}", 0), 0) for s in range(1, 13)}

    age_totals = {
        "<15": _as_int(vege.get("Kor0-14", 0)),
        "15-29": _as_int(vege.get("Kor15-29", 0)),
        "30-64": _as_int(vege.get("Kor30-64", 0)),
        "65+": _as_int(vege.get("Kor65+", 0)),
    }

    labour_totals = {
        "emp": _as_int(vege.get("Foglalkoztatott", 0)),
        "unemp": _as_int(vege.get("Munkanélküli", 0)),
        "inact_benefit": _as_int(vege.get("Inaktív", 0)),
        "dependent": _as_int(vege.get("Eltartott", 0)),
    }

    inst_count_target = _as_int(vege.get("InstCount", 0))

    # --- Build household templates for non-institution population ---
    start_household_id = lakhely_id * 1_000_000

    try:
        res = build_household_templates_for_city(
            lakhely_id=lakhely_id,
            H_by_size=H_by_size,
            age_totals=age_totals,
            labour_totals=labour_totals,
            start_household_id=start_household_id,
        )
    except Exception as e:
        print(f"❌ City {lakhely_id} ({hely}): template build failed -> {e}")
        continue

    print(f"\n✅ City {lakhely_id} ({hely}) — built {len(res.templates)} households")

    persist_templates(conn, res.templates)

    # --- Assign people to private households ---
    assignments_private, logs = assign_city(conn, lakhely_id, res.templates)

    # --- Compute leftover people (institutions) ---
    all_people_ids_df = pd.read_sql_query(
        f"SELECT LakosID FROM Szimuláció WHERE {CITY_COL} = ?",
        conn,
        params=(lakhely_id,),
    )
    all_ids = set(all_people_ids_df["LakosID"].astype(int).tolist())
    assigned_ids = set(assignments_private["LakosID"].astype(int).tolist())
    inst_ids = sorted(list(all_ids - assigned_ids))

    if inst_ids and inst_count_target:
        diff = len(inst_ids) - inst_count_target
        if abs(diff) > 5:
            print(
                f"⚠️ City {lakhely_id} ({hely}): leftover_for_inst={len(inst_ids)}, "
                f"census_inst={inst_count_target}, diff={diff}"
            )

    # Build institution assignments (I_<LakhelyID>) for lakasfel_tag
    inst_assignments = build_institution_assignments(conn, lakhely_id, inst_ids)

    # Combine household + institutional assignments into one
    all_assign = pd.concat([assignments_private, inst_assignments], ignore_index=True)

    summary = validate_city(res.templates, assignments_private)
    persist_assignments(conn, all_assign, run_id=run_id)

    print(
        f"City {lakhely_id} ({hely}) – planned (private) {summary['planned_people']} "
        f"vs assigned_to_households {summary['assigned_people']} "
        f"+ inst {len(inst_assignments)}"
    )

    all_templates.append(res.templates.assign(_CityName=str(hely)))

templates_all = pd.concat(all_templates, ignore_index=True) if all_templates else pd.DataFrame()
print("\n=== Combined template shape:", templates_all.shape, "===")

conn.close()
data.close()