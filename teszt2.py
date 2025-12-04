import sqlite3
import pandas as pd
import numpy as np
from typing import Optional, Tuple, List
from Table import tablakezelo

# ======================================================
# Setup & inputs
# ======================================================

data = tablakezelo("populacio.db", "Szimulació")
data.create_table()
data.create_sratio_table()
data.create_aratio_table()
# Household table is handled elsewhere in your pipeline
data.reset_table()

helytab = pd.read_sql_query("SELECT * FROM TelepulesOsszegzett", data.conn)

GLOBAL_SEED = 2025
rng = np.random.default_rng(GLOBAL_SEED)

# ======================================================
# General helpers
# ======================================================

def safe_int(val) -> int:
    """Convert to int; NaN / invalid -> 0."""
    try:
        v = pd.to_numeric(val, errors="coerce")
    except Exception:
        return 0
    if pd.isna(v):
        return 0
    try:
        return int(v)
    except Exception:
        return 0

def random_age_from_range(age_range: str) -> int:
    """
    Accepts 'a-b koru' or '90+ koru' (with optional trailing spaces).
    Returns a random integer age in that range.
    """
    age_range = str(age_range).strip().replace(" koru", "")
    if "+" in age_range:
        start = int(age_range.replace("+", ""))
        return int(rng.integers(start, start + 11))  # e.g. 90–100
    start, end = map(int, age_range.split("-"))
    return int(rng.integers(start, end + 1))

def korcsoport2(age: int) -> Optional[str]:
    """Regional age buckets (the ones used in edueasy / activity tables)."""
    ranges = {
        "15 évesnél fiatalabb": range(0, 15),
        "15-19 éves": range(15, 20),
        "20-24 éves": range(20, 25),
        "25-29 éves": range(25, 30),
        "30-34 éves": range(30, 35),
        "35-39 éves": range(35, 40),
        "40-44 éves": range(40, 45),
        "45-49 éves": range(45, 50),
        "50-54 éves": range(50, 55),
        "55-59 éves": range(55, 60),
        "60-64 éves": range(60, 65),
        "65-69 éves": range(65, 70),
        "70-74 éves": range(70, 75),
        "75 éves és idősebb": range(75, 120),
    }
    for label, r in ranges.items():
        if age in r:
            return label
    return None

def _normalize_probs(d: dict) -> Tuple[list, np.ndarray]:
    """Return (labels, normalized_probs). If invalid/empty, returns ([], [])."""
    if not d:
        return [], np.array([])
    labels = list(d.keys())
    p = np.array(list(d.values()), dtype=float)
    s = p.sum()
    if s <= 0:
        return [], np.array([])
    return labels, p / s

# ======================================================
# Activity & job-type assignment
# ======================================================

def assign_activity(activity_probs: dict, age: int) -> str:
    """
    Draws an activity label from {label: prob}.
    Fallbacks:
      - <15: 'Eltartott'
      - >=15 & no data: 'Foglalkoztatott'
    """
    labels, p = _normalize_probs(activity_probs)
    if p.size == 0:
        if age < 15:
            return "Eltartott"
        else:
            return "Foglalkoztatott"
    return str(rng.choice(labels, p=p))

def assign_jobtype(job_probs: dict) -> str:
    """
    Draws a job type from {Munkatípus: prob}.
    Fallback: 'Ismeretlen foglalkozás'.
    """
    labels, p = _normalize_probs(job_probs)
    if p.size == 0:
        return "Ismeretlen foglalkozás"
    return str(rng.choice(labels, p=p))

def házasság(age: int, N: int, H: int, Ö: int, E: int) -> str:
    """Marital status from city totals (no 'Rossz vagy nincs adat')."""
    N = safe_int(N); H = safe_int(H); Ö = safe_int(Ö); E = safe_int(E)
    total = N + H + Ö + E
    if age < 15:
        return "15 évnél fiatalabb"
    if total <= 0:
        return "Nőtlen"
    p = np.array([N, H, Ö, E], dtype=float)
    p /= p.sum()
    return str(rng.choice(["Nőtlen", "Házas", "Özvegy", "Elvált"], p=p))

def munka_status(age: int, F: int, M: int, I: int, E: int) -> str:
    """
    High-level activity category from city totals.
    This is NOT the same as 'Aktivitas' from the regional ratios;
    you can use it as a backup, but here we mostly rely on regional 'Aktivitas'.
    """
    F = safe_int(F); M = safe_int(M); I = safe_int(I); E = safe_int(E)
    total = F + M + I + E
    if age < 15:
        return "Tanköteles/Nem dolgozhat még"
    if total <= 0:
        return "Inaktív, ellátásban részesül"
    p = np.array([F, M, I, E], dtype=float)
    p /= p.sum()
    return str(rng.choice(
        ["Foglalkoztatott", "Munkanélküli", "Inaktív, ellátásban részesül", "Eltartott"],
        p=p
    ))

# ======================================================
# Education labels & mappings
# ======================================================

UNDER7_LABEL = "7 évesnél fiatalabb személy"

# City-level categories for adults (these exist in the city table)
EDU_CITY_ADULT = [
    "Nincs 8 ált.",
    "8 általános",
    "Szakmai okl",
    "Érettségi",
    "Diploma/Oklevél",
]

# Mapping city labels -> regional "IskolaVég" labels (for edueasy / employment tables)
EDU_CITY_TO_LONG = {
    "Nincs 8 ált.": "Általános iskola 8. évfolyamnál alacsonyabb",
    "8 általános": "Általános iskola 8. évfolyam",
    "Szakmai okl": "Középfokú iskola érettségi nélkül, szakmai oklevéllel",
    "Érettségi": "Érettségi",
    "Diploma/Oklevél": "Egyetem, főiskola stb. oklevéllel",
    # for under-7, regional tables use '15 évesnél fiatalabb személy' as education bucket
    UNDER7_LABEL: "15 évesnél fiatalabb személy",
}

def allowed_city_edus_for_age(age: int) -> list:
    """
    Feasible city-level education labels for a given age.
    This is what fixes 'too many diplomas under 18' etc.
    You can tweak thresholds if needed.
    """
    if age <= 6:
        return [UNDER7_LABEL]
    # 7–13: only primary school states
    if 7 <= age <= 13:
        return ["Nincs 8 ált.", "8 általános"]
    # 14–17: can have vocational, but realistically not diploma
    if 14 <= age <= 17:
        return ["Nincs 8 ált.", "8 általános", "Szakmai okl", "Érettségi"]
    # 18–20: allow everything except diploma (most diplomas come later)
    if 18 <= age <= 20:
        return ["Nincs 8 ált.", "8 általános", "Szakmai okl", "Érettségi"]
    # 21+: all adult categories allowed
    return EDU_CITY_ADULT.copy()

# ======================================================
# Caches for DB-backed lookups
# ======================================================

e_ratio_cache   = {}   # not heavily used now, but kept for compatibility
edueasy_cache   = {}   # (sex, kor2, megye, tipus) -> {IskolaVég_long: prob}
a_ratio_cache   = {}   # (sex, kor2, edured_long, megye, tipus) -> {Aktivitas: prob}
workratio_cache = {}   # (sex, kor2, edu_long, megye, tipus) -> {Munkatípus: prob}

def get_eratios_cached(nem, kor, megye, tipus):
    key = (nem, kor, megye, tipus)
    if key not in e_ratio_cache:
        try:
            e_ratio_cache[key] = data.get_eratios(nem, kor, megye, tipus)
        except Exception:
            e_ratio_cache[key] = ({}, 0)
    return e_ratio_cache[key]

def edueasy_cached(nem, kor2, megye, tipus):
    key = (nem, kor2, megye, tipus)
    if key not in edueasy_cache:
        try:
            edueasy_cache[key] = data.edueasy(nem, kor2, megye, tipus)
        except Exception:
            edueasy_cache[key] = {}
    return edueasy_cache[key]

def get_aratios_cached(nem, kor2, edu_long, megye, tipus):
    key = (nem, kor2, edu_long, megye, tipus)
    if key not in a_ratio_cache:
        try:
            a_ratio_cache[key] = data.get_aratios(nem, kor2, edu_long, megye, tipus)
        except Exception:
            a_ratio_cache[key] = {}
    return a_ratio_cache[key]

def get_workratios_cached(nem, kor2, edu_long, megye, tipus):
    key = (nem, kor2, edu_long, megye, tipus)
    if key not in workratio_cache:
        try:
            # if your method name is `workratio`, change this line:
            workratio_cache[key] = data.get_workratios(nem, kor2, edu_long, megye, tipus)
        except Exception:
            workratio_cache[key] = {}
    return workratio_cache[key]

# ======================================================
# Main simulation per city
# ======================================================

def simulate_city(index: int, row: pd.Series) -> pd.DataFrame:
    # --- basic population
    férfi = safe_int(row.get("Ferfi", 0))
    nő    = safe_int(row.get("No", 0))
    össz  = safe_int(row.get("Lakok", férfi + nő))
    if össz <= 0:
        return pd.DataFrame(columns=[
            "Lakhely","LakhelyID","LakosID","Nem","Kor",
            "Oktatás","Aktivitas","Kapcsolat","Munkaviszony"
        ])

    férfiráta = np.clip(férfi / max(össz, 1), 0.0, 1.0)
    nőráta    = 1.0 - férfiráta

    # --- marital & activity city totals
    Nőtlen = safe_int(row.get("Nőtlen", 0))
    Házas  = safe_int(row.get("Házas", 0))
    Özvegy = safe_int(row.get("Özvegy", 0))
    Elvált = safe_int(row.get("Elvált", 0))

    Foglalk = safe_int(row.get("Foglalkoztatott", 0))
    Munkanelk = safe_int(row.get("Munkanélküli", 0))
    Inaktív   = safe_int(row.get("Ellátásban részesülő inaktív", 0))
    Eltartott = safe_int(row.get("Eltartott", 0))

    # --- city-level education counts
    Nincs8  = safe_int(row.get("Nincs 8 ált.", 0))
    Nyolc8  = safe_int(row.get("8 általános", 0))
    Szakmk  = safe_int(row.get("Szakmai okl", 0))
    Erett   = safe_int(row.get("Érettségi", 0))
    Diploma = safe_int(row.get("Diploma/Oklevél", 0))
    Under7c = safe_int(row.get("7 évnél fiatalabb", 0))

    city_quota = {
        "Nincs 8 ált.": Nincs8,
        "8 általános": Nyolc8,
        "Szakmai okl": Szakmk,
        "Érettségi": Erett,
        "Diploma/Oklevél": Diploma,
        UNDER7_LABEL: Under7c,
    }

    megye  = row.get("Vármegye", "")
    tipus  = row.get("Településtípus", "")

    # --- build individuals with age & sex, but no education/activity yet
    age_groups = {k: row[k] for k in row.index if "koru" in str(k)}
    persons = []
    person_id = 0

    for age_range_col, count in age_groups.items():
        cnt = safe_int(count)
        if cnt <= 0:
            continue
        age_range_label = str(age_range_col).strip().replace(" koru", "")

        genders = rng.choice(["Férfi", "Nő"], size=cnt, p=[férfiráta, nőráta])
        ages    = [random_age_from_range(age_range_label) for _ in range(cnt)]

        for sex, age in zip(genders, ages):
            kc2 = korcsoport2(age)
            person_id += 1
            persons.append({
                "Lakhely":   row["Helység megnevezése"],
                "LakhelyID": index + 1,
                "LakosID":   (index + 1) * 10_000_000 + person_id,
                "Nem":       sex,
                "Kor":       age,
                "kor2":      kc2,
                "Oktatás":   None,  # to be filled
                "Aktivitas": None,  # to be filled
                "Kapcsolat": None,  # to be filled
                "Munkaviszony": None,  # to be filled
            })

    # --- sanity check (optional)
    total_persons = len(persons)
    # if total_persons != össz:  # you can log this if you want
    #     print("Warning: person count != Lakok for", row["Helység megnevezése"])

    # ======================================================
    # EDUCATION ASSIGNMENT
    # ======================================================

    # 1) fix education for under 7
    for p in persons:
        if p["Kor"] <= 6:
            p["Oktatás"] = UNDER7_LABEL

    # 2) quotas for adult categories (we don't touch the under-7 quota here)
    remaining = {k: int(city_quota.get(k, 0)) for k in EDU_CITY_ADULT}
    # target_adult_total = sum(remaining.values())  # optional check

    # 3) assign adult education using regional p(E|age×sex) and remaining quotas
    idxs = np.arange(len(persons))
    rng.shuffle(idxs)

    for i in idxs:
        p = persons[i]
        age = p["Kor"]
        if age <= 6:
            continue  # already assigned

        sex = p["Nem"]
        kc2 = p["kor2"]

        feasible_city = allowed_city_edus_for_age(age)
        if feasible_city == [UNDER7_LABEL]:
            p["Oktatás"] = UNDER7_LABEL
            continue

        # regional probabilities for long labels
        reg = edueasy_cached(sex, kc2, megye, tipus)  # {IskolaVég_long: prob}

        choices = []
        weights = []

        for city_lab in feasible_city:
            if city_lab == UNDER7_LABEL:
                continue
            long_lab = EDU_CITY_TO_LONG.get(city_lab, city_lab)
            prob     = float(reg.get(long_lab, 0.0))
            rem      = float(remaining.get(city_lab, 0))
            if rem <= 0:
                continue
            w = prob * rem
            choices.append(city_lab)
            weights.append(w)

        if choices:
            w = np.array(weights, dtype=float)
            if w.sum() == 0:
                w = np.ones_like(w) / len(w)
            else:
                w = w / w.sum()
            chosen_city = str(rng.choice(choices, p=w))
        else:
            if sum(remaining.values()) > 0:
                chosen_city = max(remaining.items(), key=lambda kv: kv[1])[0]
            else:
                chosen_city = "Nincs 8 ált."

        if chosen_city in remaining and remaining[chosen_city] > 0:
            remaining[chosen_city] -= 1
        p["Oktatás"] = chosen_city

    # ======================================================
    # MARITAL STATUS, ACTIVITY, JOB TYPE
    # ======================================================

    for p in persons:
        age = p["Kor"]
        sex = p["Nem"]
        kc2 = p["kor2"]

        # 1) marital
        p["Kapcsolat"] = házasság(age, Nőtlen, Házas, Özvegy, Elvált)

        # 2) education long label for regional tables
        edu_city = p["Oktatás"] or "Nincs 8 ált."
        edu_long = EDU_CITY_TO_LONG.get(edu_city, edu_city)

        # 3) Aktivitas from regional rates
        if age < 15:
            p["Aktivitas"] = "Eltartott"
        else:
            # for 15+ we use regional p(Aktivitás | sex, kor2, edu_long)
            # some tables treat under-15 as a special education bucket, so guard:
            edured_for_activity = edu_long
            a_dict = get_aratios_cached(sex, kc2, edured_for_activity, megye, tipus)
            p["Aktivitas"] = assign_activity(a_dict, age)

        # 4) Job type (Munkaviszony) using your get_workratios
        if age < 15:
            p["Munkaviszony"] = "Tanköteles/Nem dolgozhat még"
        else:
            if p["Aktivitas"] == "Foglalkoztatott":
                job_probs = get_workratios_cached(sex, kc2, edu_long, megye, tipus)
                p["Munkaviszony"] = assign_jobtype(job_probs)
            else:
                p["Munkaviszony"] = "Nem foglalkoztatott"

    return pd.DataFrame(persons, columns=[
        "Lakhely","LakhelyID","LakosID","Nem","Kor",
        "Oktatás","Aktivitas","Kapcsolat","Munkaviszony"
    ])

# ======================================================
# Run simulation for all cities
# ======================================================

for index, row in helytab.iterrows():   # remove .head(...) to run all
    city_name = row["Helység megnevezése"]
    df_city   = simulate_city(index, row)
    if not df_city.empty:
        data.insert_dataframe(df_city, city_name)

# ======================================================
# Diagnostics / summaries
# ======================================================
# ==============================
# GLOBAL CONSISTENCY CHECKS
#   1) Sex per city
#   2) Age per city
#   3) Education per city
#   4) Employment status per city
# ==============================

print("\n================ CONSISTENCY CHECKS ================")

# --- small rename fix for age column in helytab (trailing space) ---
if "90+ koru " in helytab.columns and "90+ koru" not in helytab.columns:
    helytab = helytab.rename(columns={"90+ koru ": "90+ koru"})

# --------------------------------------------------
# 1) SEX PER CITY
# --------------------------------------------------
print("\n=== 1) SEX PER CITY ===")

sex_cols_city = ["Ferfi", "No"]

orig_sex = helytab[["Helység megnevezése"] + sex_cols_city].copy()
orig_sex.rename(columns={"Helység megnevezése": "Lakhely"}, inplace=True)

sim_sex = data.query("""
    SELECT Lakhely, Nem, COUNT(*) AS Count
    FROM Szimulació
    GROUP BY Lakhely, Nem
""")

sim_sex_pivot = sim_sex.pivot(index="Lakhely", columns="Nem", values="Count").fillna(0)

# Ensure both sexes exist as columns
for col in ["Férfi", "Nő"]:
    if col not in sim_sex_pivot.columns:
        sim_sex_pivot[col] = 0

# Map simulated column names to city labels
sim_sex_pivot = sim_sex_pivot.rename(columns={"Férfi": "Ferfi", "Nő": "No"})
sim_sex_pivot.reset_index(inplace=True)

sex_check = orig_sex.merge(sim_sex_pivot, on="Lakhely", how="left", suffixes=("_orig", "_sim")).fillna(0)

for col in sex_cols_city:
    col_orig = f"{col}_orig"
    col_sim  = f"{col}_sim"
    diff_col = f"{col}_diff"
    sex_check[diff_col] = sex_check[col_sim] - sex_check[col_orig]

print(sex_check.head(10)[["Lakhely"] + [c for c in sex_check.columns if c.endswith("_diff")]])

print("Max abs sex diff per category:")
for col in sex_cols_city:
    dcol = f"{col}_diff"
    print(col, ":", sex_check[dcol].abs().max())


# --------------------------------------------------
# 2) AGE PER CITY
# --------------------------------------------------
print("\n=== 2) AGE PER CITY ===")

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

sim_age = data.query("""
    SELECT 
      Lakhely,
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
    FROM Szimulació
    GROUP BY Lakhely, AgeRange
""")

sim_age_pivot = sim_age.pivot(index="Lakhely", columns="AgeRange", values="Count").fillna(0)

# Ensure all age categories exist as columns
for col in age_cols_city:
    if col not in sim_age_pivot.columns:
        sim_age_pivot[col] = 0

sim_age_pivot.reset_index(inplace=True)

age_check = orig_age.merge(sim_age_pivot, on="Lakhely", how="left", suffixes=("_orig", "_sim")).fillna(0)

for col in age_cols_city:
    col_orig = f"{col}_orig"
    col_sim  = f"{col}_sim"
    diff_col = f"{col}_diff"
    age_check[diff_col] = age_check[col_sim] - age_check[col_orig]

print(age_check.head(5)[["Lakhely"] + [c for c in age_check.columns if c.endswith("_diff")]])

print("Max abs age diff per category:")
for col in age_cols_city:
    dcol = f"{col}_diff"
    print(col, ":", age_check[dcol].abs().max())


# --------------------------------------------------
# 3) EDUCATION PER CITY
# --------------------------------------------------
print("\n=== 3) EDUCATION PER CITY ===")

edu_cols_city = [
    "Nincs 8 ált.",
    "8 általános",
    "Szakmai okl",
    "Érettségi",
    "Diploma/Oklevél",
    "7 évnél fiatalabb",
]

orig_edu = helytab[["Helység megnevezése"] + edu_cols_city].copy()
orig_edu.rename(columns={"Helység megnevezése": "Lakhely"}, inplace=True)

sim_edu = data.query("""
    SELECT Lakhely, Oktatás, COUNT(*) AS Count
    FROM Szimulació
    GROUP BY Lakhely, Oktatás
""")

sim_edu_pivot = sim_edu.pivot(index="Lakhely", columns="Oktatás", values="Count").fillna(0)

# Ensure all education categories exist as columns
for col in edu_cols_city:
    if col not in sim_edu_pivot.columns:
        sim_edu_pivot[col] = 0

sim_edu_pivot.reset_index(inplace=True)

edu_check = orig_edu.merge(sim_edu_pivot, on="Lakhely", how="left", suffixes=("_orig", "_sim")).fillna(0)

for col in edu_cols_city:
    col_orig = f"{col}_orig"
    col_sim  = f"{col}_sim"
    diff_col = f"{col}_diff"
    edu_check[diff_col] = edu_check[col_sim] - edu_check[col_orig]

print(edu_check.head(5)[["Lakhely"] + [c for c in edu_check.columns if c.endswith("_diff")]])

print("Max abs education diff per category:")
for col in edu_cols_city:
    dcol = f"{col}_diff"
    print(col, ":", edu_check[dcol].abs().max())


# --------------------------------------------------
# 4) EMPLOYMENT STATUS PER CITY
# --------------------------------------------------
print("\n=== 4) EMPLOYMENT STATUS PER CITY ===")

emp_cols_city = [
    "Foglalkoztatott",
    "Munkanélküli",
    "Ellátásban részesülő inaktív",
    "Eltartott",
]

orig_emp = helytab[["Helység megnevezése"] + emp_cols_city].copy()
orig_emp.rename(columns={"Helység megnevezése": "Lakhely"}, inplace=True)

sim_emp = data.query("""
    SELECT Lakhely, Munkaviszony, COUNT(*) AS Count
    FROM Szimulació
    GROUP BY Lakhely, Munkaviszony
""")

sim_emp_pivot = sim_emp.pivot(index="Lakhely", columns="Munkaviszony", values="Count").fillna(0)

# Map simulated employment labels to city-level labels
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

# Ensure all employment categories exist as columns
for col in emp_cols_city:
    if col not in sim_emp_renamed.columns:
        sim_emp_renamed[col] = 0

sim_emp_renamed.reset_index(inplace=True)

emp_check = orig_emp.merge(sim_emp_renamed, on="Lakhely", how="left", suffixes=("_orig", "_sim")).fillna(0)

for col in emp_cols_city:
    col_orig = f"{col}_orig"
    col_sim  = f"{col}_sim"
    diff_col = f"{col}_diff"
    emp_check[diff_col] = emp_check[col_sim] - emp_check[col_orig]

print(emp_check.head(5)[["Lakhely"] + [c for c in emp_check.columns if c.endswith("_diff")]])

print("Max abs employment diff per category:")
for col in emp_cols_city:
    dcol = f"{col}_diff"
    print(col, ":", emp_check[dcol].abs().max())
data.close()