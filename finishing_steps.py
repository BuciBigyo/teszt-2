import sqlite3
import pandas as pd
from collections import defaultdict
from typing import Any, Dict, List, Tuple

DB_PATH = "populacio.db"

PEOPLE_TABLE = "Szimuláció"
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

    for _, r in df_priv.iterrows():
        hid = str(r["HáztartásID"])
        pid = int(r["LakosID"])
        lab = str(r["labour_cat"])
        if hid not in hh_people:
            hh_people[hid] = {c: [] for c in LABOUR_CATS}
        if lab not in hh_people[hid]:
            hh_people[hid][lab] = []
        hh_people[hid][lab].append(pid)

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
                    hh_people[give_hid][cat].append(donor_id)
                    continue

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
    tmpl_city: pd.DataFrame,lakhely_id: int
) -> pd.DataFrame:
    """
    df_city_raw: includes LakhelyID, HáztartásID, LakosID, age_bin, labour_cat,
                 plus ALL other columns from Szimuláció (Nem, Lakhely, etc.).
    Returns a DataFrame with the same person-level columns, but with possibly
    updated HáztartásID and labour_cat for private households.
    """
    if df_city_raw.empty:
        return df_city_raw.copy()


    base_cols = ["LakhelyID", "HáztartásID", "LakosID", "age_bin", "labour_cat"]
    extra_cols = [c for c in df_city_raw.columns if c not in base_cols]

    mask_inst = df_city_raw["HáztartásID"].astype(str).str.startswith("I_")
    df_inst = df_city_raw[mask_inst].copy()
    df_priv_all = df_city_raw[~mask_inst].copy()

    if df_priv_all.empty:
        # Only institutions -> keep as is
        return df_city_raw[base_cols + extra_cols].copy()

    hh_people, hh_targets = build_household_structures(df_priv_all, tmpl_city)
    if not hh_people:
        return df_city_raw[base_cols + extra_cols].copy()

    total_swaps = 0
    for cat in LABOUR_CATS:
        s = perform_swaps_for_category(cat, hh_people, hh_targets)
        if s > 0:
            print(f"City {lakhely_id}: performed {s} swaps for category {cat}")
        total_swaps += s

    # Person-level attributes from Szimuláció (for private households)
    # Key: LakosID -> other attributes
    df_city_attrs = df_city_raw[["LakosID"] + extra_cols].drop_duplicates(subset="LakosID")

    # Rebuild private assignments with new households + labour_cat
    rows_priv: List[Dict[str, Any]] = []
    for hid, cats in hh_people.items():
        for cat, pid_list in cats.items():
            for pid in pid_list:
                # age_bin remains the one derived from real age
                age_bin_series = df_city_raw.loc[df_city_raw["LakosID"] == pid, "age_bin"]
                if age_bin_series.empty:
                    age_str = "<15"
                else:
                    age_str = str(age_bin_series.iloc[0])

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
# MAIN LOGIC
# =========================

def main():
    conn = sqlite3.connect(DB_PATH)
    ensure_final_table(conn)

    tmpl_all = pd.read_sql_query(f"SELECT * FROM {TEMPLATES_TABLE}", conn)

    cities_df = pd.read_sql_query(
        f"SELECT DISTINCT LakhelyID FROM {ASSIGN_TABLE}",
        conn,
    )
    city_ids = sorted(cities_df["LakhelyID"].astype(int).tolist())

    print(f"Found {len(city_ids)} cities in {ASSIGN_TABLE}.")

    for lakhely_id in city_ids:
        print(f"\n=== Processing city {lakhely_id} ===")

        # Pull all columns from Szimuláció (+ assignment household info)
        df_city_raw = pd.read_sql_query(
            f"""
            SELECT
            t.LakhelyID,
            t.HáztartásID,
            t.LakosID,          -- use LakosID from the link table
            t.age_bin,
            t.labour_cat,
            -- pick all the person attributes you want from Szimuláció,
            -- but DO NOT include s.LakosID again
            s.Kor,
            s.Nem,
            s.Munkaviszony,
            s.Lakhely
            FROM {ASSIGN_TABLE} t
            JOIN {PEOPLE_TABLE} s
            ON t.LakosID = s.LakosID
            WHERE t.LakhelyID = ?
            """,
            conn,
            params=(lakhely_id,),
        )

        if df_city_raw.empty:
            print(f"City {lakhely_id}: no rows in assignments, skipping.")
            continue

        # If Szimuláció also has LakosID or LakhelyID, pandas will duplicate them
        # e.g. LakosID, LakosID_1 – we keep the ones from t.*
        for dup_col in ["LakosID_1", "LakhelyID_1"]:
            if dup_col in df_city_raw.columns:
                df_city_raw.drop(columns=[dup_col], inplace=True)

        # Add derived bins from REAL attributes (Kor, Munkaviszony, etc.)
        if "Kor" not in df_city_raw.columns:
            raise ValueError("Column 'Kor' not found in Szimuláció – cannot derive age_bin.")
        if "Munkaviszony" not in df_city_raw.columns:
            raise ValueError("Column 'Munkaviszony' not found in Szimuláció – cannot derive labour_cat.")

        df_city_raw["age_bin"] = df_city_raw["Kor"].apply(_age_bin_from_value)
        df_city_raw["labour_cat"] = df_city_raw.apply(
            lambda r: _labour_cat_from_value(r["Munkaviszony"], r["age_bin"]),
            axis=1,
        )

        tmpl_city = tmpl_all[tmpl_all["LakhelyID"] == lakhely_id].copy()
        if tmpl_city.empty:
            print(f"City {lakhely_id}: no templates found in {TEMPLATES_TABLE}, copying assignments as-is.")
            df_out = df_city_raw.copy()
        else:
            df_out = run_swapping_for_city(df_city_raw, tmpl_city, lakhely_id)

        # Quick consistency check (private households)
        if not tmpl_city.empty:
            check_city_against_templates(df_out, tmpl_city, lakhely_id)

        # Write out ALL columns (keys + attributes) to Finishing_step
        df_out.to_sql(FINAL_TABLE, conn, if_exists="append", index=False)

        total_people = len(df_out)
        print(f"City {lakhely_id}: final assigned people in {FINAL_TABLE} = {total_people}")

        # Create indexes once the table exists
        cur = conn.cursor()
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_fin_city ON {FINAL_TABLE}(LakhelyID)")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_fin_house ON {FINAL_TABLE}(HáztartásID)")
        conn.commit()

    conn.close()
    print("\nAll done. Final assignments are in table:", FINAL_TABLE)


if __name__ == "__main__":
    main()