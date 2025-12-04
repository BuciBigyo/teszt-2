#!/usr/bin/env python3
"""
finishing_steps_optimized.py

Final labour-category swapping + global consistency checks
for the synthetic population household assignment.
"""

import sqlite3
import pandas as pd
from collections import defaultdict
from typing import Any, Dict, List, Tuple

DB_PATH = "populacio.db"

PEOPLE_TABLE = "Szimulació"
ASSIGN_TABLE = "lakasfel_tag"
TEMPLATES_TABLE = "LakasEpitő"
FINAL_TABLE = "Finishing_step"

AGE_BINS = ["<15", "15-29", "30-64", "65+"]
LABOUR_CATS = ["emp", "unemp", "inact_benefit", "dependent"]


# =========================
# HELPERS FOR CATEGORIES
# =========================

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


def _safe_int(x, default=0) -> int:
    try:
        if pd.isna(x):
            return default
        return int(round(float(x)))
    except Exception:
        return default


# =========================
# FINAL TABLE HANDLING
# =========================

def ensure_final_table(conn: sqlite3.Connection):
    """
    Drop any existing Finishing_step table so we get a clean one
    with the full schema created automatically by pandas.to_sql.
    """
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {FINAL_TABLE}")
    conn.commit()


# =========================
# SWAPPING CORE
# =========================

def build_household_structures(
    df_city: pd.DataFrame,
    tmpl_city: pd.DataFrame
) -> Tuple[Dict[str, Dict[str, List[int]]], Dict[str, Dict[str, int]]]:
    """
    Build two structures for private households (NOT institutions):
    - hh_people[hid][lab_cat] = list of LakosID in that category.
    - hh_targets[hid][lab_cat] = target counts from templates.
    """
    hh_people: Dict[str, Dict[str, List[int]]] = {}
    hh_targets: Dict[str, Dict[str, int]] = {}

    df_priv = df_city[~df_city["HáztartásID"].astype(str).str.startswith("I_")].copy()
    if df_priv.empty:
        return hh_people, hh_targets

    # Actual people per household x labour_cat
    for _, r in df_priv.iterrows():
        hid = str(r["HáztartásID"])
        pid = int(r["LakosID"])
        lab = str(r["labour_cat"])
        if hid not in hh_people:
            hh_people[hid] = {c: [] for c in LABOUR_CATS}
        if lab not in hh_people[hid]:
            hh_people[hid][lab] = []
        hh_people[hid][lab].append(pid)

    # Target counts from templates
    for _, r in tmpl_city.iterrows():
        hid = str(r["HáztartásID"])
        if hid.startswith("I_"):
            continue
        hh_targets[hid] = {
            "emp": int(r["n_emp"]),
            "unemp": int(r["n_unemp"]),
            "inact_benefit": int(r["n_inact_benefit"]),
            "dependent": int(r["n_dep"]),
        }
        if hid not in hh_people:
            hh_people[hid] = {c: [] for c in LABOUR_CATS}

    return hh_people, hh_targets


def compute_deficit_surplus(
    hh_people: Dict[str, Dict[str, List[int]]],
    hh_targets: Dict[str, Dict[str, int]]
) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, int]]]:
    deficits: Dict[str, Dict[str, int]] = {}
    surplus: Dict[str, Dict[str, int]] = {}

    for hid, targ in hh_targets.items():
        deficits[hid] = {}
        surplus[hid] = {}
        ppl = hh_people.get(hid, {c: [] for c in LABOUR_CATS})
        for cat in LABOUR_CATS:
            actual = len(ppl.get(cat, []))
            target = int(targ.get(cat, 0))
            d = target - actual
            if d > 0:
                deficits[hid][cat] = d
                surplus[hid][cat] = 0
            elif d < 0:
                deficits[hid][cat] = 0
                surplus[hid][cat] = -d
            else:
                deficits[hid][cat] = 0
                surplus[hid][cat] = 0

    return deficits, surplus


def perform_swaps_for_category(
    cat: str,
    hh_people: Dict[str, Dict[str, List[int]]],
    hh_targets: Dict[str, Dict[str, int]],
    max_iter: int = 10_000
) -> int:
    swaps = 0
    iters = 0

    while iters < max_iter:
        iters += 1
        deficits, surplus = compute_deficit_surplus(hh_people, hh_targets)
        need_list = [(hid, d) for hid, dd in deficits.items() if (d := dd.get(cat, 0)) > 0]
        give_list = [(hid, s) for hid, ss in surplus.items() if (s := ss.get(cat, 0)) > 0]

        if not need_list or not give_list:
            break

        need_list.sort(key=lambda x: -x[1])
        give_list.sort(key=lambda x: -x[1])

        made_progress = False

        for need_hid, need_amt in need_list:
            if need_amt <= 0:
                continue

            for give_idx, (give_hid, give_amt) in enumerate(give_list):
                if give_amt <= 0 or give_hid == need_hid:
                    continue

                give_pool = hh_people[give_hid].get(cat, [])
                if not give_pool:
                    continue

                need_pool_other = []
                for other_cat in LABOUR_CATS:
                    if other_cat == cat:
                        continue
                    need_pool_other += hh_people[need_hid].get(other_cat, [])

                if not need_pool_other:
                    continue

                donor_id = give_pool.pop()
                outgoing_id = need_pool_other.pop()

                outgoing_cat = None
                for oc in LABOUR_CATS:
                    if oc == cat:
                        continue
                    if outgoing_id in hh_people[need_hid].get(oc, []):
                        outgoing_cat = oc
                        hh_people[need_hid][oc].remove(outgoing_id)
                        break

                if outgoing_cat is None:
                    # undo donor removal, nothing else changed
                    hh_people[give_hid][cat].append(donor_id)
                    continue

                # swap
                hh_people[need_hid][cat].append(donor_id)
                hh_people[give_hid][outgoing_cat].append(outgoing_id)

                swaps += 1
                made_progress = True
                give_list[give_idx] = (give_hid, give_amt - 1)
                break

            if not made_progress:
                continue

        if not made_progress:
            break

    return swaps


def run_swapping_for_city(
    df_city_raw: pd.DataFrame,
    tmpl_city: pd.DataFrame,
    lakhely_id: int
) -> pd.DataFrame:
    """
    df_city_raw: includes LakhelyID, HáztartásID, LakosID, age_bin, labour_cat,
                 plus ALL other columns from Szimuláció (Nem, Lakhely, etc.).
    Returns a DataFrame with the same person-level columns, but with possibly
    updated HáztartásID and labour_cat for private households.

    Optimised to avoid O(N²) lookups by precomputing LakosID -> age_bin.
    """
    if df_city_raw.empty:
        return df_city_raw.copy()

    base_cols = ["LakhelyID", "HáztartásID", "LakosID", "age_bin", "labour_cat"]
    extra_cols = [c for c in df_city_raw.columns if c not in base_cols]

    # Split institutions vs private households
    mask_inst = df_city_raw["HáztartásID"].astype(str).str.startswith("I_")
    df_inst = df_city_raw[mask_inst].copy()
    df_priv_all = df_city_raw[~mask_inst].copy()

    if df_priv_all.empty:
        # Only institutions -> keep as is
        return df_city_raw[base_cols + extra_cols].copy()

    # Build structures for swapping
    hh_people, hh_targets = build_household_structures(df_priv_all, tmpl_city)
    if not hh_people:
        return df_city_raw[base_cols + extra_cols].copy()

    # === BIG SPEEDUP: precompute age_bin per LakosID once ===
    age_bin_map = (
        df_city_raw[["LakosID", "age_bin"]]
        .drop_duplicates(subset="LakosID")
        .set_index("LakosID")["age_bin"]
        .to_dict()
    )

    # Person-level attributes from Szimuláció (for private households)
    df_city_attrs = df_city_raw[["LakosID"] + extra_cols].drop_duplicates(subset="LakosID")

    # Perform swaps
    total_swaps = 0
    for cat in LABOUR_CATS:
        s = perform_swaps_for_category(cat, hh_people, hh_targets)
        if s > 0:
            print(f"City {lakhely_id}: performed {s} swaps for category {cat}")
        total_swaps += s

    # Rebuild private assignments with new households + labour_cat
    rows_priv: List[Dict[str, Any]] = []
    for hid, cats in hh_people.items():
        for cat, pid_list in cats.items():
            for pid in pid_list:
                age_str = str(age_bin_map.get(pid, "<15"))
                rows_priv.append({
                    "LakhelyID": lakhely_id,
                    "HáztartásID": hid,
                    "LakosID": pid,
                    "age_bin": age_str,
                    "labour_cat": cat,
                })

    df_priv_final = pd.DataFrame(rows_priv)

    # Attach all original attributes
    df_priv_final = df_priv_final.merge(df_city_attrs, on="LakosID", how="left")

    # Institutions: keep all attributes untouched
    df_inst_final = df_inst[base_cols + extra_cols].copy()

    df_final = pd.concat([df_priv_final, df_inst_final], ignore_index=True)
    return df_final


# =========================
# QUICK CONSISTENCY CHECK
# =========================

def check_city_against_templates(df_out: pd.DataFrame, tmpl_city: pd.DataFrame, lakhely_id: int):
    """
    Print a quick comparison between templates and final assignments:
    - number of private households
    - age-bin totals
    - labour-category totals
    Institutions (I_<LakhelyID>) are excluded from the check.
    """
    # templates: private only
    tmpl_priv = tmpl_city[~tmpl_city["HáztartásID"].astype(str).str.startswith("I_")].copy()
    if tmpl_priv.empty:
        print(f"City {lakhely_id}: no private templates, skipping check.")
        return

    # planned household count
    planned_hh = tmpl_priv["HáztartásID"].nunique()

    planned_age = {
        "<15": int(tmpl_priv["n_lt15"].sum()),
        "15-29": int(tmpl_priv["n_15_29"].sum()),
        "30-64": int(tmpl_priv["n_30_64"].sum()),
        "65+": int(tmpl_priv["n_65p"].sum()),
    }
    planned_lab = {
        "emp": int(tmpl_priv["n_emp"].sum()),
        "unemp": int(tmpl_priv["n_unemp"].sum()),
        "inact_benefit": int(tmpl_priv["n_inact_benefit"].sum()),
        "dependent": int(tmpl_priv["n_dep"].sum()),
    }

    # final assignments: private only
    df_priv = df_out[~df_out["HáztartásID"].astype(str).str.startswith("I_")].copy()
    actual_hh = df_priv["HáztartásID"].nunique()

    actual_age_counts = df_priv["age_bin"].value_counts().to_dict()
    actual_age = {k: int(actual_age_counts.get(k, 0)) for k in planned_age.keys()}

    actual_lab_counts = df_priv["labour_cat"].value_counts().to_dict()
    actual_lab = {k: int(actual_lab_counts.get(k, 0)) for k in planned_lab.keys()}

    inst_count = df_out[df_out["HáztartásID"].astype(str).str.startswith("I_")].shape[0]

    print(f"\n--- City {lakhely_id} check (private households only) ---")
    print(f"Planned households: {planned_hh} | Actual households: {actual_hh}")
    print(f"Planned age totals:      {planned_age}")
    print(f"Actual age totals:       {actual_age}")
    print(f"Planned labour totals:   {planned_lab}")
    print(f"Actual labour totals:    {actual_lab}")
    print(f"Institution residents (I_<LakhelyID>): {inst_count}")


# =========================
# GLOBAL FINISHING CHECKS (OPTIMISED)
# =========================

def run_global_checks(conn: sqlite3.Connection):
    """
    Global consistency checks at the very end of the pipeline.

    Compares FINAL_TABLE (Finishing_step) against:
      - TelepulesOsszegzett: total pop, sex, age (0–9,10–19,...,90+)
      - LakasOsszegzett: household size distribution (1–5, 6+) and
        institutional residents ("Intézeti háztartásban élő személy").

    All heavy aggregations on FINAL_TABLE are done in SQL instead of
    loading the full table into pandas.
    """

    print("\n================ GLOBAL FINISHING CHECKS ================")

    # --- load reference tables
    helytab = pd.read_sql_query("SELECT * FROM TelepulesOsszegzett", conn)
    laktab = pd.read_sql_query("SELECT * FROM LakasOsszegzett", conn)

    # ------------------------------------------------------------------
    # 1) PERSON-LEVEL: TOTAL POPULATION & SEX PER SETTLEMENT
    # ------------------------------------------------------------------
    print("\n--- 1) Population & sex per settlement ---")

    sex_cols_city = ["Ferfi", "No"]

    orig_sex = helytab[["Helység megnevezése"] + sex_cols_city].copy()
    orig_sex.rename(columns={"Helység megnevezése": "Lakhely"}, inplace=True)
    orig_sex["Lakos"] = orig_sex["Ferfi"] + orig_sex["No"]

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
    sim_pivot = sim_sex.pivot(index="Lakhely", columns="Nem", values="Count").fillna(0)

    for col in ["Férfi", "Nő"]:
        if col not in sim_pivot.columns:
            sim_pivot[col] = 0

    sim_pivot = sim_pivot.rename(columns={"Férfi": "Ferfi", "Nő": "No"})
    sim_pivot["Lakos"] = sim_pivot["Ferfi"] + sim_pivot["No"]
    sim_pivot.reset_index(inplace=True)

    sex_check = orig_sex.merge(
        sim_pivot,
        on="Lakhely",
        how="left",
        suffixes=("_orig", "_sim"),
    ).fillna(0)

    for col in ["Ferfi", "No", "Lakos"]:
        col_orig = f"{col}_orig"
        col_sim = f"{col}_sim"
        sex_check[col + "_diff"] = sex_check[col_sim] - sex_check[col_orig]

    print(sex_check.head(10)[["Lakhely", "Ferfi_diff", "No_diff", "Lakos_diff"]])

    print("Max abs differences (all settlements):")
    for col in ["Ferfi", "No", "Lakos"]:
        dcol = col + "_diff"
        print(f"  {col}: {sex_check[dcol].abs().max()}")

    # ------------------------------------------------------------------
    # 2) PERSON-LEVEL: AGE BINS PER SETTLEMENT (0–9,...,90+)
    # ------------------------------------------------------------------
    print("\n--- 2) Age structure per settlement (0–9,...,90+) ---")

    if "90+ koru " in helytab.columns and "90+ koru" not in helytab.columns:
        helytab = helytab.rename(columns={"90+ koru ": "90+ koru"})

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

    orig_age = helytab[["Helység megnevezése"] + age_cols_city].copy()
    orig_age.rename(columns={"Helység megnevezése": "Lakhely"}, inplace=True)

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

    sim_age_pivot = sim_age.pivot(index="Lakhely", columns="AgeRange", values="Count").fillna(0)

    for col in age_cols_city:
        if col not in sim_age_pivot.columns:
            sim_age_pivot[col] = 0

    sim_age_pivot.reset_index(inplace=True)

    age_check = orig_age.merge(
        sim_age_pivot,
        on="Lakhely",
        how="left",
        suffixes=("_orig", "_sim"),
    ).fillna(0)

    for col in age_cols_city:
        col_orig = f"{col}_orig"
        col_sim = f"{col}_sim"
        age_check[col + "_diff"] = age_check[col_sim] - age_check[col_orig]

    print(age_check.head(5)[["Lakhely"] + [c for c in age_check.columns if c.endswith("_diff")]])

    print("Max abs age diff per category:")
    for col in age_cols_city:
        dcol = col + "_diff"
        print(f"  {col}: {age_check[dcol].abs().max()}")

    # ------------------------------------------------------------------
    # 3) PERSON-LEVEL: EMPLOYMENT STATUS PER SETTLEMENT
    # ------------------------------------------------------------------
    print("\n--- 3) Employment status per settlement ---")

    emp_cols_city = [
        "Foglalkoztatott",
        "Munkanélküli",
        "Ellátásban részesülő inaktív",
        "Eltartott",
    ]

    orig_emp = helytab[["Helység megnevezése"] + emp_cols_city].copy()
    orig_emp.rename(columns={"Helység megnevezése": "Lakhely"}, inplace=True)

    sim_emp = pd.read_sql_query(
        """
        SELECT
          TRIM(Lakhely) AS Lakhely,
          Munkaviszony,
          COUNT(*) AS Count
        FROM Finishing_step
        GROUP BY TRIM(Lakhely), Munkaviszony
        """,
        conn,
    )

    sim_emp_pivot = sim_emp.pivot(index="Lakhely", columns="Munkaviszony", values="Count").fillna(0)

    sim_name_map = {
        "Foglalkoztatott": "Foglalkoztatott",
        "Munkanélküli": "Munkanélküli",
        "Inaktív, ellátásban részesül": "Ellátásban részesülő inaktív",
        "Eltartott": "Eltartott",
    }

    sim_emp_renamed = sim_emp_pivot.copy()
    for sim_label, city_label in sim_name_map.items():
        if sim_label in sim_emp_renamed.columns:
            sim_emp_renamed = sim_emp_renamed.rename(columns={sim_label: city_label})

    for col in emp_cols_city:
        if col not in sim_emp_renamed.columns:
            sim_emp_renamed[col] = 0

    sim_emp_renamed.reset_index(inplace=True)

    emp_check = orig_emp.merge(
        sim_emp_renamed,
        on="Lakhely",
        how="left",
        suffixes=("_orig", "_sim"),
    ).fillna(0)

    for col in emp_cols_city:
        col_orig = f"{col}_orig"
        col_sim = f"{col}_sim"
        emp_check[col + "_diff"] = emp_check[col_sim] - emp_check[col_orig]

    print(emp_check.head(5)[["Lakhely"] + [c for c in emp_check.columns if c.endswith("_diff")]])

    print("Max abs employment diff per category:")
    for col in emp_cols_city:
        dcol = col + "_diff"
        print(f"  {col}: {emp_check[dcol].abs().max()}")

    # ------------------------------------------------------------------
    # 4) HOUSEHOLD-LEVEL: SIZE DISTRIBUTION & INSTITUTIONAL RESIDENTS
    # ------------------------------------------------------------------
    print("\n--- 4) Household size & institutional residents per settlement ---")

    size_cols_city = {
        1: "1 személyes háztartás",
        2: "2 személyes háztartás",
        3: "3 személyes háztartás",
        4: "4 személyes háztartás",
        5: "5 személyes háztartás",
        6: "6+ személyes háztartás",
    }

    orig_hh = laktab[
        ["Helység megnevezése"] + list(size_cols_city.values()) + ["Intézeti háztartásban élő személy"]
    ].copy()
    orig_hh.rename(columns={"Helység megnevezése": "Lakhely"}, inplace=True)

    # Private household sizes from SQL
    hh_sizes = pd.read_sql_query(
        """
        SELECT
          TRIM(Lakhely) AS Lakhely,
          HáztartásID,
          COUNT(*) AS size
        FROM Finishing_step
        WHERE HáztartásID NOT LIKE 'I_%'
        GROUP BY TRIM(Lakhely), HáztartásID
        """,
        conn,
    )

    def _size_bucket(s: int) -> int:
        try:
            s = int(s)
        except Exception:
            return 6
        return s if s <= 5 else 6

    hh_sizes["size_bucket"] = hh_sizes["size"].apply(_size_bucket)

    size_counts = (
        hh_sizes.groupby(["Lakhely", "size_bucket"])["HáztartásID"]
        .count()
        .reset_index(name="Count")
    )
    size_pivot = size_counts.pivot(index="Lakhely", columns="size_bucket", values="Count").fillna(0)

    for b in range(1, 7):
        if b not in size_pivot.columns:
            size_pivot[b] = 0

    size_pivot.rename(columns=size_cols_city, inplace=True)
    size_pivot.reset_index(inplace=True)

    # Institutional residents from SQL
    inst_counts = pd.read_sql_query(
        """
        SELECT TRIM(Lakhely) AS Lakhely,
               COUNT(*) AS Inst_sim
        FROM Finishing_step
        WHERE HáztartásID LIKE 'I_%'
        GROUP BY TRIM(Lakhely)
        """,
        conn,
    )

    sim_hh = size_pivot.merge(inst_counts, on="Lakhely", how="left").fillna(0)

    hh_check = orig_hh.merge(
        sim_hh,
        on="Lakhely",
        how="left",
        suffixes=("_orig", "_sim"),
    ).fillna(0)

    for col in size_cols_city.values():
        col_orig = f"{col}_orig"
        col_sim = f"{col}_sim"
        hh_check[col + "_diff"] = hh_check[col_sim] - hh_check[col_orig]

    hh_check["Inst_diff"] = (
        hh_check["Inst_sim"] - hh_check["Intézeti háztartásban élő személy"]
    )

    print(
        hh_check.head(10)[
            ["Lakhely"] + [c for c in hh_check.columns if c.endswith("_diff")]
        ]
    )

    print("Max abs household size diff per category:")
    for col in size_cols_city.values():
        dcol = col + "_diff"
        print(f"  {col}: {hh_check[dcol].abs().max()}")

    print("Max abs institutional resident diff:", hh_check["Inst_diff"].abs().max())


# =========================
# MAIN LOGIC
# =========================

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # -----------------------------------------------------
    # 0) Helpful indexes for the big JOIN (created once)
    # -----------------------------------------------------
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_assign_lakos ON {ASSIGN_TABLE}(LakosID)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_assign_lakhely ON {ASSIGN_TABLE}(LakhelyID)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_people_lakos ON {PEOPLE_TABLE}(LakosID)")
    conn.commit()

    # -----------------------------------------------------
    # 1) Start from a clean Finishing_step
    # -----------------------------------------------------
    ensure_final_table(conn)

    # Load all templates once
    tmpl_all = pd.read_sql_query(f"SELECT * FROM {TEMPLATES_TABLE}", conn)

    # -----------------------------------------------------
    # 2) ONE BIG JOIN: assignments + person attributes
    #    (instead of 3400 small per-city queries)
    # -----------------------------------------------------
    df_all = pd.read_sql_query(
        f"""
        SELECT
            t.LakhelyID,
            t.HáztartásID,
            t.LakosID,
            s.Kor,
            s.Nem,
            s.Munkaviszony,
            s.Lakhely
        FROM {ASSIGN_TABLE} AS t
        JOIN {PEOPLE_TABLE} AS s
          ON t.LakosID = s.LakosID
        """,
        conn,
    )

    # Make sure LakhelyID is integer for grouping
    df_all["LakhelyID"] = df_all["LakhelyID"].astype(int)

    city_ids = sorted(df_all["LakhelyID"].unique().tolist())
    print(f"Found {len(city_ids)} cities in {ASSIGN_TABLE}.")

    # -----------------------------------------------------
    # 3) Process each city *in memory*
    # -----------------------------------------------------
    for lakhely_id in city_ids:
        print(f"\n=== Processing city {lakhely_id} ===")

        # Filter rows for this city from the already-loaded big dataframe
        df_city_raw = df_all[df_all["LakhelyID"] == lakhely_id].copy()

        if df_city_raw.empty:
            print(f"City {lakhely_id}: no rows in assignments, skipping.")
            continue

        # Derive age_bin and labour_cat from real attributes
        if "Kor" not in df_city_raw.columns:
            raise ValueError("Column 'Kor' not found – cannot derive age_bin.")
        if "Munkaviszony" not in df_city_raw.columns:
            raise ValueError("Column 'Munkaviszony' not found – cannot derive labour_cat.")

        df_city_raw["age_bin"] = df_city_raw["Kor"].apply(_age_bin_from_value)
        df_city_raw["labour_cat"] = df_city_raw.apply(
            lambda r: _labour_cat_from_value(r["Munkaviszony"], r["age_bin"]),
            axis=1,
        )

        # Templates for this city
        tmpl_city = tmpl_all[tmpl_all["LakhelyID"] == lakhely_id].copy()
        if tmpl_city.empty:
            print(f"City {lakhely_id}: no templates found in {TEMPLATES_TABLE}, copying assignments as-is.")
            df_out = df_city_raw.copy()
        else:
            df_out = run_swapping_for_city(df_city_raw, tmpl_city, lakhely_id)

        # Quick consistency check (private households)
        if not tmpl_city.empty:
            check_city_against_templates(df_out, tmpl_city, lakhely_id)

        # Append ALL columns (keys + attributes) to Finishing_step
        df_out.to_sql(FINAL_TABLE, conn, if_exists="append", index=False)

        total_people = len(df_out)
        print(f"City {lakhely_id}: final assigned people in {FINAL_TABLE} = {total_people}")

    # -----------------------------------------------------
    # 4) Indexes on final table (for later analysis)
    # -----------------------------------------------------
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_fin_city ON {FINAL_TABLE}(LakhelyID)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_fin_house ON {FINAL_TABLE}(HáztartásID)")
    conn.commit()

    # -----------------------------------------------------
    # 5) Global checks at the end
    # -----------------------------------------------------
    run_global_checks(conn)
    conn.close()
    print("\nAll done. Final assignments are in table:", FINAL_TABLE)

if __name__ == "__main__":
    main()