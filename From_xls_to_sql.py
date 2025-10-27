import sqlite3
import pandas as pd
import random
import numpy as np
from typing import Optional, Tuple, List
from Table import tablakezelo

data=tablakezelo("populacio.db","Szimulació")
data.create_table()
data.create_ratio_table()
data.create_lakasfel_table("Lakasfeltoltes")
data.reset_table()

ht = pd.read_excel("telepules_hierarchia.xlsx")
ha=pd.read_excel("flat_A_haztartasok_adatai_telepulesenkent.xlsx")
hl=pd.read_excel("flat_A_lakasok_legfontosabb_jellemzok_telepulesenkent.xlsx")
na=pd.read_excel("flat_A_nepesseg_adatok_telepulesenkent.xlsx")
hi=pd.read_excel("hier_iskolaba_jaro_nepesseg.xlsx",header=[0,1])
hfa=pd.read_excel("hier_foglalkoztatott_nepesseg_foglalkozasi_focsoport.xlsx",header=[0,1])

hfa.rename(columns={
    hfa.columns[0]: ("", "Nem"),
    hfa.columns[1]: ("", "Korcsoport"),
    hfa.columns[2]: ("", "IskolaVég"),
    hfa.columns[3]:("","Munkatípus")
}, inplace=True)

hfa.columns = [
    col[1] if col[1] in ["Nem", "Korcsoport", "IskolaVég","Munkatípus"]
    else f"{col[0].strip()} | {col[1].strip()}"
    for col in hfa.columns
]

hfa.rename(columns={
    ('Unnamed: 0_level_0 | Unnamed: 0_level_1'): 'Nem',
    ('Unnamed: 1_level_0 | Unnamed: 1_level_1'): 'Korcsoport',
    ('Unnamed: 2_level_0 | Unnamed: 2_level_1'): 'IskolaVég',
    ('Unnamed: 3_level_0 | Unnamed: 3_level_1'): 'Munkatípus'
    },inplace=True)
hfa[["Nem","Korcsoport","Iskolavég"]]=hfa[["Nem","Korcsoport","IskolaVég"]].ffill()
hfa_lin = hfa.melt(
    id_vars=["Nem", "Korcsoport", "IskolaVég","Munkatípus"],
    var_name="Location",
    value_name="Lakossag"
)

hfa_lin[["Megye", "TelepulesTipus"]] = hfa_lin["Location"].str.split(" | ",n=1, expand=True)
hfa_lin.drop(columns="Location", inplace=True)
print("Foglalkoztatott népesség adatok:")
print(hfa_lin.head())




hi.columns = hi.columns.map(lambda x: ("", x[1]) if "Unnamed" in str(x[0]) else x)
hi.columns = [
    col[1] if col[0] == "" else f"{col[0]} | {col[1]}"
    for col in hi.columns
]
hi.rename(columns={
    ('Unnamed: 0_level_1'): 'Nem',
    ('Unnamed: 1_level_1'): 'Korcsoport',
    ('Unnamed: 2_level_1'): 'IskolaTípus'

}, inplace=True)
hi[["Nem","Korcsoport"]]=hi[["Nem","Korcsoport"]].ffill()
lin = hi.melt(
    id_vars=["Nem", "Korcsoport", "IskolaTípus"],
    var_name="Terulet",
    value_name="Lakossag"
)
lin[["Megye", "TelepulesTipus"]] = lin["Terulet"].str.split(" \| ", expand=True)


tanosz = (
    lin
    .groupby(["Nem", "Korcsoport", "Megye", "TelepulesTipus"], as_index=False)["Lakossag"]
    .sum()
    .rename(columns={"Lakossag": "Osszes"})
)
tanratio=lin.merge(tanosz, on=["Nem","Korcsoport","Megye","TelepulesTipus"])
tanratio["Arany"]=tanratio["Lakossag"]/tanratio["Osszes"]
tanratio["Arany"] = tanratio["Arany"].replace([np.inf, -np.inf], 0).fillna(0)

print(tanratio.head(200))
data.insert_ratios(tanratio)

names=ht["Helység megnevezése"]
nepesseg24=ht["Lakó-népesség"]
lakasszam=ht["Lakások száma"]


helytab=ht[["Helység megnevezése","Vármegye","Településtípus","Lakó-népesség","Lakások száma"]]
helytab=helytab.copy()
helytab["Ferfi"]=None
helytab["No"]=None
helytab["Lakok"]=helytab["Ferfi"]+helytab["No"]
helytab["0-9"]=None
helytab["10-19"]=None
helytab["20-29"]=None
helytab["30-39"]=None
helytab["40-49"]=None
helytab["50-59"]=None
helytab["60-69"]=None
helytab["70-79"]=None
helytab["80-89"]=None
helytab["90+"]=None
helytab["Nőtlen"]=None
helytab["Házas"]=None
helytab["Özvegy"]=None
helytab["Elvált"]=None
helytab["15 évnél fiatalabb"]=None
helytab["Helység típus"]=None
helytab["Helység megye"]=None
   
for index,row in helytab.iterrows():

    név=row.iloc[0]
    
    try:
        adatok=na[név]
        lakadat=hl[név]
        hazadat=ha[név]

        helytab.loc[index, "Ferfi"]  = adatok[0]
        helytab.loc[index, "No"]  = adatok[1]
        helytab.loc[index, "Lakok"]  = adatok[0] + adatok[1]
        helytab.loc[index, "0-9"]  = adatok[2]
        helytab.loc[index, "10-19"]  = adatok[3]
        helytab.loc[index, "20-29"]  = adatok[4]
        helytab.loc[index, "30-39"]  = adatok[5]
        helytab.loc[index, "40-49"] = adatok[6]
        helytab.loc[index, "50-59"] = adatok[7]
        helytab.loc[index, "60-69"] = adatok[8]
        helytab.loc[index, "70-79"] = adatok[9]
        helytab.loc[index, "80-89"] = adatok[10]
        helytab.loc[index, "90+"] = adatok[11]
        helytab.loc[index,"7 évnél fiatalabb"]= adatok[34]
        helytab.loc[index,"Nincs 8 ált."]=adatok[29]
        helytab.loc[index,"8 általános"]=adatok[30]
        helytab.loc[index,"Szakmai okl"]=adatok[31]
        helytab.loc[index,"Érettségi"]=adatok[32]
        helytab.loc[index,"Diploma/Oklevél"]=adatok[33]
        helytab.loc[index,"Nőtlen"]=adatok[18]
        helytab.loc[index,"Házas"]=adatok[19]
        helytab.loc[index,"Özvegy"]=adatok[20]
        helytab.loc[index,"Elvált"]=adatok[21]
        helytab.loc[index,"15 évnél fiatalabb"]=adatok[22]
        helytab.loc[index,"Foglalkoztatott"]=adatok[35]
        helytab.loc[index,"Ellátásban részesülő inaktív"]=adatok[37]
        helytab.loc[index,"Munkanélküli"]=adatok[36]
        helytab.loc[index,"Eltartott"]=adatok[38]

        helytab.loc[index,"Lakott lakás"]=lakadat[0]
        helytab.loc[index,"1 szoba"]=lakadat[1]
        helytab.loc[index,"2 szoba"]=lakadat[2]
        helytab.loc[index,"3 szoba"]=lakadat[3]
        helytab.loc[index,"4 vagy több szoba"]=lakadat[4]
        helytab.loc[index,"1 személyes háztartás"]=hazadat[0]
        helytab.loc[index,"2 személyes háztartás"]=hazadat[1]
        helytab.loc[index,"3 személyes háztartás"]=hazadat[2]
        helytab.loc[index,"4 személyes háztartás"]=hazadat[3]
        helytab.loc[index,"5 személyes háztartás"]=hazadat[4]
        helytab.loc[index,"6+ személyes háztartás"]=hazadat[5]
        helytab.loc[index,"Egy családból álló háztartás"]=hazadat[6]
        helytab.loc[index,"Több családból álló háztartás"]=hazadat[9]
        helytab.loc[index,"Nem családháztartás"]=hazadat[12]
        
    except:
        print("Nincs ilyen város",név)



def random_age_from_range(age_range: str) -> int:
    if "+" in age_range:
        start = int(age_range.replace("+", ""))
        return np.random.randint(start, start + 11)  # 90+ → 90–100
    else:
        start, end = map(int, age_range.split("-"))
        return np.random.randint(start, end + 1)
    
def korcsoport(age: int):
    ranges = {
        "0-5 éves": range(0, 6),
        "6-9 éves": range(6, 10),
        "10-14 éves": range(10, 15),
        "15-19 éves": range(15, 20),
        "20-24 éves": range(20, 25),
        "25-29 éves": range(25, 30),
        "30-34 éves": range(30, 35),
        "35-39 éves": range(35, 40),
        "40 éves és idősebb": range(40, 120)
    }
    for label, r in ranges.items():
        if age in r:
            return label
    return None

def assign_education(age: int,arany:dict) -> str:
    iskolak=list(arany.keys())
    esely=list(arany.values())
    if esely=={}:
        return "Rosz vagy nincs adat"
    if age < 6:
        return np.random.choice(iskolak, p=esely)
    elif age < 10:
        return np.random.choice(iskolak, p=esely)
    elif age < 15:
        return np.random.choice(iskolak, p=esely)
    elif age<20:
        return np.random.choice(iskolak, p=esely)
    elif age<25:
        return np.random.choice(iskolak, p=esely)
    elif age<30:
        return np.random.choice(iskolak, p=esely)
    elif age<35:
        return np.random.choice(iskolak, p=esely)
    elif age<40:
        return np.random.choice(iskolak, p=esely)
    elif age>39:
        return np.random.choice(iskolak, p=esely)
    
def iskolarany(df, nem, kor, megye, tipus):
    korcs = korcsoport(kor)
    korcs = korcs.replace('-', '–') 
    if kor is None:
        return {}
    if korcs=="0–5 éves":
        return {"6 év alatti": 1.0}
    subset = df.query(
        'Nem == @nem and Korcsoport == @korcs and Megye == @megye and TelepulesTipus == @tipus'
    )
    
    if subset.empty:
        return {}
    
    return dict(zip(subset["IskolaTípus"], subset["Arany"]))
    
def házasság(age:int,N:int,H:int,Ö:int,E:int)-> str:
    if N+H+Ö+E==0:
        return "Rossz vagy nincs adat"
    if age<15:
        return "15 évnél fiatalabb"
    else:
        return np.random.choice(
            [
                "Nőtlen",
                "Házas",
                "Özvegy",
                "Elvált"
            ],
            p=[N/(N+H+Ö+E),H/(N+H+Ö+E),Ö/(N+H+Ö+E),E/(N+H+Ö+E)]
        )

def munka(age:int,F:int,M:int,I:int,E:int)->str:
    if F+M+I+E==0:
        return "Rossz vagy nincs adat"
    if age<15:
        return "Tanköteles/Nem dolgozhat még"
    else:
        return np.random.choice(
            [
                "Foglalkoztatott",
                "Munkanélküli",
                "Inaktív, ellátásban részesül",
                "Eltartott"
            ],
            p=[F/(F+M+I+E),M/(F+M+I+E),I/(F+M+I+E),E/(F+M+I+E)]
        )
    
def szimulacio(index:int,row) -> pd.DataFrame:
    férfi = row.get("Ferfi", 0)
    nő = row.get("No", 0)
    össz = row["Lakok"]
    gyerek=row.get("7 évnél fiatalabb",0)
    Nőtlen=row.get("Nőtlen",0)
    Házas=row.get("Nőtlen",0)
    Özvegy=row.get("Özvegy",0)
    Elvált=row.get("Elvált",0)
    megye=row.get("Vármegye",0)
    teltip=row.get("Településtípus")
    Dolg=row.get("Foglalkoztatott",0)
    Munkanélküli=row.get("Munkanélküli",0)
    Inaktív=row.get("Ellátásban részesülő inaktív",0)
    Eltartott=row.get("Eltartott",0)


    if pd.isna(férfi) or pd.isna(nő) or pd.isna(gyerek) or pd.isna(Nőtlen):
        return pd.DataFrame(columns=["Lakhely", "Kor", "Nem", "Oktatás","Kapcsolat","Munkaviszony"])

    férfiráta = férfi / össz
    nőráta = 1 - férfiráta
    ID=0

    age_groups = {k: row[k] for k in row.index if "0" in k or "+90" in k}

    people = []

    for age_range, count in age_groups.items():
        genders = np.random.choice( 
            ["Férfi", "Nő"],
            size=count,
            p=[férfiráta, nőráta]
        )
        for g in genders:
            age = random_age_from_range(age_range)
            kor=korcsoport(age)
            konkráta=data.get_ratios(g,kor,megye,teltip)
            education = assign_education(age,konkráta)
            marital=házasság(age,Nőtlen,Házas,Özvegy,Elvált)
            work=munka(age,Dolg,Munkanélküli,Inaktív,Eltartott)
            ID+=1
            people.append({
                "Lakhely": row["Helység megnevezése"],
                "LakhelyID":index+1,
                "LakosID":(index+1)*10_000_000+ID,
                "Nem": g,
                "Kor": age,
                "Oktatás": education,
                "Kapcsolat": marital,
                "Munkaviszony": work
            })
            

    return pd.DataFrame(people)
def lakasok(varos:pd.DataFrame)->pd.DataFrame:

    pass
"""def haztart(index,row)->pd.DataFrame:
    varosID=index+1
    egylakos= row["1 személyes háztartás"]
    ketszemelyes=row["2 személyes háztartás"]
    hármas=row["3 személyes háztartás"]
    négylakos=row["4 személyes háztartás"]
    ötlakos=row["5 személyes háztartás"]
    hatlakos=row["6+ személyes háztartás"]
    egycsalados=row["Egy családból álló háztartás"]
    tobbcsalados=row["Több családból álló háztartás"]
    nemcsalad=row["Nem családháztartás"]
    count={egylakos:1,ketszemelyes:2,hármas:3,négylakos:4,ötlakos:5,hatlakos:6}
    család={egycsalados:1,tobbcsalados:2,nemcsalad:3}
    lakasfel = pd.DataFrame(columns=["LakhelyID", "LakásID", "HáztartásID", "Lakszemélyekszáma", "Háztartástípus"])
    for méret,db in count.items():
        for i in range(db):
            lakasID=(index+1)*1_000_000+(i+1)*10_000+méret
            háztartásID=(index+1)*1_000_000+(i+1)*10_000
            lakasfel = lakasfel.append({
                "LakhelyID": varosID,
                "LakásID": lakasID,
                "HáztartásID": háztartásID,
                "Lakszemélyekszáma": méret,
                "Háztartástípus": None
            }, ignore_index=True)
    for típus,db in család.items():
        for i in range(db):
            háztartásID=(index+1)*1_000_000+(i+1)*10_000
            lakasfel.loc[lakasfel["HáztartásID"]==háztartásID,"Háztartástípus"]=típus
    print(lakasfel.head(),"-----------------")
    return lakasfel"""
            
def haztart(index: int, row: pd.Series) -> pd.DataFrame:
    """
    Build lakasfel for one settlement (index is 0-based).
    Expects row to have the following columns with INTEGER COUNTS:
      "1 személyes háztartás", "2 személyes háztartás", ..., "6+ személyes háztartás"
      "Egy családból álló háztartás", "Több családból álló háztartás", "Nem családháztartás"
    """
    rng = np.random.default_rng(42 + index)  # reproducible per settlement

    varosID = index + 1

    # ----- read counts (households counts, not shares)
    egylakos       = int(pd.to_numeric(row["1 személyes háztartás"], errors="coerce") or 0)
    ketszemelyes   = int(pd.to_numeric(row["2 személyes háztartás"], errors="coerce") or 0)
    harmas         = int(pd.to_numeric(row["3 személyes háztartás"], errors="coerce") or 0)
    negylakos      = int(pd.to_numeric(row["4 személyes háztartás"], errors="coerce") or 0)
    otlakos        = int(pd.to_numeric(row["5 személyes háztartás"], errors="coerce") or 0)
    hatplusz       = int(pd.to_numeric(row["6+ személyes háztartás"], errors="coerce") or 0)

    egycsalados    = int(pd.to_numeric(row["Egy családból álló háztartás"], errors="coerce") or 0)
    tobbcsalados   = int(pd.to_numeric(row["Több családból álló háztartás"], errors="coerce") or 0)
    nemcsalad      = int(pd.to_numeric(row["Nem családháztartás"], errors="coerce") or 0)

    # ----- sizes -> counts (correct direction!)
    size_to_count = {
        1: egylakos,
        2: ketszemelyes,
        3: harmas,
        4: negylakos,
        5: otlakos,
        6: hatplusz,   # treat 6+ as 6 for now (can expand to 6–8 later)
    }

    # Build explicit household size list: [1,1,1,2,2,3,3,3,3,...]
    size_list = []
    for size, cnt in size_to_count.items():
        if cnt > 0:
            size_list.extend([size] * cnt)

    n_households = len(size_list)
    if n_households == 0:
        # return empty, but with the right dtypes
        return pd.DataFrame({
            "LakhelyID": pd.Series(dtype="int64"),
            "LakásID": pd.Series(dtype="int64"),
            "HáztartásID": pd.Series(dtype="int64"),
            "Lakszemélyekszáma": pd.Series(dtype="int64"),
            "Háztartástípus": pd.Series(dtype="string"),
        })

    # Shuffle sizes to avoid ordering bias
    rng.shuffle(size_list)

    # ----- household types -> counts (correct direction!)
    type_to_count = {
        "Egy családból álló háztartás": egycsalados,
        "Több családból álló háztartás": tobbcsalados,
        "Nem családháztartás":          nemcsalad,
    }
    # Build explicit type list of length <= n_households
    type_list = []
    for t, cnt in type_to_count.items():
        if cnt > 0:
            type_list.extend([t] * cnt)

    # Reconcile lengths (trim or pad with the most common type)
    if len(type_list) >= n_households:
        type_list = type_list[:n_households]
    else:
        # pad with the mode (or fall back to "Egy családból álló háztartás")
        most_common_type = max(type_to_count.items(), key=lambda kv: kv[1])[0] if n_households > 0 else "Egy családból álló háztartás"
        type_list.extend([most_common_type] * (n_households - len(type_list)))

    # Shuffle types to avoid position correlation with sizes
    rng.shuffle(type_list)

    # ----- ID scheme (preserving your original pattern):
    #   HáztartásID = (index+1)*1_000_000 + (i+1)*10_000
    #   LakásID     = HáztartásID + size   (as you did)
    base = (index + 1) * 1_000_000
    i_seq = np.arange(1, n_households + 1, dtype=np.int64)
    haztartas_ids = base + i_seq * 10_000
    lakas_ids = haztartas_ids + np.array(size_list, dtype=np.int64)

    df = pd.DataFrame({
        "LakhelyID":        np.full(n_households, varosID, dtype=np.int64),
        "LakásID":          lakas_ids,
        "HáztartásID":      haztartas_ids,
        "Lakszemélyekszáma": np.array(size_list, dtype=np.int64),
        "Háztartástípus":   pd.array(type_list, dtype="string"),
    })

    # Optional sanity checks (you can remove in production)
    # Ensure the household-type counts are close to requested counts
    # and sizes sum to expected persons if you track that elsewhere.

    return df

for index, row in helytab.head(5).iterrows():
    hely=row["Helység megnevezése"]
    varos=szimulacio(index,row)
    hazadat=haztart(index,row)
    data.insert_lakasfel(hazadat,table_name="Lakasfeltoltes")
    data.insert_dataframe(varos,hely)



def parse_age_to_int(kor_val) -> Optional[int]:
    """
    Turn 'Kor' (age) column into an int if possible.
    Accepts integers/strings or ranges like '18-24', '18–24'.
    Returns None if unknown.
    """
    if pd.isna(kor_val):
        return None
    try:
        # already numeric or numeric string
        return int(kor_val)
    except Exception:
        s = str(kor_val)
        # normalize dash variants
        s = s.replace("–", "-").replace("—", "-").strip()
        if "-" in s:
            a, b = s.split("-", 1)
            try:
                a = int(a.strip()); b = int(b.strip())
                return (a + b) // 2  # mid-point as a proxy
            except Exception:
                return None
        # last fallback: strip non-digits
        digits = "".join(ch for ch in s if ch.isdigit())
        return int(digits) if digits else None

def is_adult(age: Optional[int], threshold: int = 18) -> bool:
    return (age is not None) and (age >= threshold)

def ensure_tables_for_assignment(conn: sqlite3.Connection,
                                 people_table: str,
                                 lakasfel_table: str,
                                 link_table: str = "lakasfel_tag"):
    """
    Create the (person -> household) link table and useful indexes.
    Does NOT drop anything.
    """
    conn.execute(f"""
    CREATE TABLE IF NOT EXISTS {link_table} (
        LakosID        TEXT NOT NULL PRIMARY KEY,
        HáztartásID    TEXT NOT NULL,
        LakhelyID      TEXT NOT NULL,
        Szerep         TEXT
    );
    """)
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{link_table}_haz ON {link_table}(HáztartásID);")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{link_table}_lakhely ON {link_table}(LakhelyID);")
    # helpful indexes on sources (no-op if exist)
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{people_table}_lakhely ON {people_table}(LakhelyID);")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{lakasfel_table}_lakhely ON {lakasfel_table}(LakhelyID);")
    conn.commit()

# -------------------------------
# Core assigner
# -------------------------------
def _ensure_int_max(conn, table, sid):
    # Numeric max by settlement, robust to TEXT storage
    row = conn.execute(
        f'''SELECT MAX(CAST("HáztartásID" AS INTEGER))
            FROM {table}
            WHERE "LakhelyID" = ?;''',
        (str(sid),)
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else None

def _global_int_max(conn, table):
    row = conn.execute(
        f'''SELECT MAX(CAST("HáztartásID" AS INTEGER))
            FROM {table};'''
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else None

def _insert_homes_chunk(conn, table, df):
    # Use executemany with INSERT OR IGNORE to avoid crashes on rare collisions
    cur = conn.cursor()
    try:
        conn.execute("BEGIN;")
        cur.executemany(
            f'''INSERT OR IGNORE INTO {table}
                ("LakhelyID","LakásID","HáztartásID","Lakszemélyekszáma","Háztartástípus")
                VALUES (?,?,?,?,?);''',
            list(zip(
                df["LakhelyID"].astype(str),
                df["LakásID"].astype(str),
                df["HáztartásID"].astype(str),
                df["Lakszemélyekszáma"].astype(int),
                df["Háztartástípus"].where(df["Háztartástípus"].notna(), None)
            ))
        )
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        cur.close()
def _flush_links(conn: sqlite3.Connection, link_table: str,
                 rows: List[Tuple[str, str, str, Optional[str]]]) -> None:
    """
    Batch-insert person→household links.
    rows: list of (LakosID, HáztartásID, LakhelyID, Szerep)
    Uses INSERT OR REPLACE so re-runs won't crash on PK collisions.
    """
    if not rows:
        return
    cur = conn.cursor()
    try:
        conn.execute("BEGIN;")
        cur.executemany(
            f'''INSERT OR REPLACE INTO {link_table}
                ("LakosID","HáztartásID","LakhelyID","Szerep")
                VALUES (?,?,?,?);''',
            rows
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
def assign_people_to_homes(db_path: str,
                           people_table: str,
                           lakasfel_table: str,
                           link_table: str = "lakasfel_tag",
                           batch_size: int = 200_000,
                           prefer_adult_in_single_family: bool = True,
                           auto_expand_if_capacity_short: bool = True,
                           rng_seed: int = 12345):
    rng = np.random.default_rng(rng_seed)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")

    ensure_tables_for_assignment(conn, people_table, lakasfel_table, link_table)

    sids = pd.read_sql_query(
        f"SELECT DISTINCT LakhelyID FROM {people_table} ORDER BY LakhelyID", conn
    )["LakhelyID"].tolist()

    link_rows = []

    for sid in sids:
        # --- READS (patched: pass sid as str)
        people = pd.read_sql_query(
            f'SELECT LakosID, LakhelyID, Nem, Kor FROM {people_table} WHERE LakhelyID = ?',
            conn, params=(str(sid),)
        )
        if people.empty:
            continue

        homes = pd.read_sql_query(
            f'''SELECT "HáztartásID","LakhelyID","Lakszemélyekszáma","Háztartástípus","LakásID"
                FROM {lakasfel_table} WHERE LakhelyID = ? ORDER BY "HáztartásID"''',
            conn, params=(str(sid),)
        )

        # derive adult flags
        ages = people["Kor"].apply(parse_age_to_int)
        people["is_adult"] = ages.apply(is_adult).fillna(False)

        # shuffle people
        idx = np.arange(len(people)); rng.shuffle(idx)
        people = people.iloc[idx].reset_index(drop=True)
        adult_ids = people.loc[people["is_adult"], "LakosID"].tolist()
        minor_ids = people.loc[~people["is_adult"], "LakosID"].tolist()

        # ---------- PATCH START: safe expansion ----------
        total_capacity = int(homes["Lakszemélyekszáma"].sum()) if not homes.empty else 0
        total_people = len(people)

        if total_capacity < total_people and auto_expand_if_capacity_short:
            deficit = total_people - total_capacity

            last_for_sid = _ensure_int_max(conn, lakasfel_table, sid)
            if last_for_sid is not None:
                start = last_for_sid
            else:
                global_max = _global_int_max(conn, lakasfel_table)
                start = global_max if global_max is not None else 0

            step = 10_000
            next_ids = np.arange(start + step, start + step * (deficit + 1), step, dtype=np.int64)
            new_haz_ids = next_ids
            new_lakas_ids = new_haz_ids + 1

            add_df = pd.DataFrame({
                "LakhelyID": str(sid),
                "LakásID":   new_lakas_ids.astype(str),
                "HáztartásID": new_haz_ids.astype(str),
                "Lakszemélyekszáma": 1,
                "Háztartástípus": "Nem családháztartás",
            })
            _insert_homes_chunk(conn, lakasfel_table, add_df)
            homes = pd.concat([homes, add_df], ignore_index=True)
            total_capacity = int(homes["Lakszemélyekszáma"].sum())
        # ---------- PATCH END ----------

        capacity = min(total_capacity, len(people))
        homes = homes.sample(frac=1.0, random_state=int(rng.integers(0, 2**31-1))).reset_index(drop=True)

        def pop_from(lst, k):
            take = lst[:k]
            del lst[:k]
            return take

        remaining_ids = people["LakosID"].tolist()
        assigned_count = 0

        for _, h in homes.iterrows():
            if assigned_count >= capacity:
                break
            haz_id = str(h["HáztartásID"])
            hsize = int(h["Lakszemélyekszáma"])
            htype = str(h["Háztartástípus"]) if pd.notna(h["Háztartástípus"]) else None

            members = []

            if prefer_adult_in_single_family and htype == "Egy családból álló háztartás" and hsize > 0 and adult_ids:
                head = pop_from(adult_ids, 1)[0]
                if head in remaining_ids:
                    remaining_ids.remove(head)
                members.append(head)

            need = hsize - len(members)
            if need > 0:
                members.extend(pop_from(remaining_ids, min(need, len(remaining_ids))))
                chosen = set(members)
                if adult_ids:
                    adult_ids = [x for x in adult_ids if x not in chosen]
                if minor_ids:
                    minor_ids = [x for x in minor_ids if x not in chosen]

            for j, pid in enumerate(members):
                role = "head" if (j == 0 and htype == "Egy családból álló háztartás") else "member"
                link_rows.append((pid, haz_id, str(sid), role))

            assigned_count += len(members)
            if len(link_rows) >= batch_size:
                _flush_links(conn, link_table, link_rows)
                link_rows.clear()

        if remaining_ids and auto_expand_if_capacity_short:
            # spillover guard: create 1-person homes for any leftovers
            last_for_sid = _ensure_int_max(conn, lakasfel_table, sid)
            start = last_for_sid if last_for_sid is not None else (_global_int_max(conn, lakasfel_table) or 0)
            step = 10_000
            seq = np.arange(start + step, start + step * (len(remaining_ids) + 1), step, dtype=np.int64)
            add_df = pd.DataFrame({
                "LakhelyID": str(sid),
                "LakásID":   (seq + 1).astype(str),
                "HáztartásID": seq.astype(str),
                "Lakszemélyekszáma": 1,
                "Háztartástípus": "Nem családháztartás",
            })
            _insert_homes_chunk(conn, lakasfel_table, add_df)
            for pid, hid in zip(remaining_ids, add_df["HáztartásID"].tolist()):
                link_rows.append((pid, str(hid), str(sid), "member"))
            remaining_ids = []
            if len(link_rows) >= batch_size:
                _flush_links(conn, link_table, link_rows)
                link_rows.clear()

    if link_rows:
        _flush_links(conn, link_table, link_rows)
        link_rows.clear()

    conn.close()
    print("✅ Assignment complete.")
a=assign_people_to_homes(
    db_path="populacio.db",
    people_table="Szimulació",
    lakasfel_table="Lakasfeltoltes",   
    link_table="lakasfel_tag"
)


varosell=data.query("""
select Lakhely, Nem, count(*) as eredmeny
from Szimulació
Group by Lakhely, Nem
""")

korell = data.query("""
SELECT 
Lakhely,
CASE
WHEN CAST(Kor AS INTEGER) BETWEEN 0 AND 9  THEN '0-9'
WHEN CAST(Kor AS INTEGER) BETWEEN 10 AND 19 THEN '10-19'
WHEN CAST(Kor AS INTEGER) BETWEEN 20 AND 29 THEN '20-29'
WHEN CAST(Kor AS INTEGER) BETWEEN 30 AND 39 THEN '30-39'
WHEN CAST(Kor AS INTEGER) BETWEEN 40 AND 49 THEN '40-49'
WHEN CAST(Kor AS INTEGER) BETWEEN 50 AND 59 THEN '50-59'
WHEN CAST(Kor AS INTEGER) BETWEEN 60 AND 69 THEN '60-69'
WHEN CAST(Kor AS INTEGER) BETWEEN 70 AND 79 THEN '70-79'
WHEN CAST(Kor AS INTEGER) BETWEEN 80 AND 89 THEN '80-89'
ELSE '90+'
END AS AgeRange,
COUNT(*) AS Count
FROM Szimulació
GROUP BY Lakhely, AgeRange
ORDER BY Lakhely, MIN(CAST(Kor AS INTEGER))
""")
iskell=data.query(
"""
Select
Lakhely, Oktatás, count(*) as okt
from Szimulació
Group by Lakhely, Oktatás
"""
)

össznemell=data.query(
    """
    select nem, count(*)
    from Szimulació
    group by nem
    """
)
összkorell=data.query(
    """
    SELECT 
  CASE
    WHEN CAST(Kor AS INTEGER) BETWEEN 0 AND 9  THEN '0-9'
    WHEN CAST(Kor AS INTEGER) BETWEEN 10 AND 19 THEN '10-19'
    WHEN CAST(Kor AS INTEGER) BETWEEN 20 AND 29 THEN '20-29'
    WHEN CAST(Kor AS INTEGER) BETWEEN 30 AND 39 THEN '30-39'
    WHEN CAST(Kor AS INTEGER) BETWEEN 40 AND 49 THEN '40-49'
    WHEN CAST(Kor AS INTEGER) BETWEEN 50 AND 59 THEN '50-59'
    WHEN CAST(Kor AS INTEGER) BETWEEN 60 AND 69 THEN '60-69'
    WHEN CAST(Kor AS INTEGER) BETWEEN 70 AND 79 THEN '70-79'
    WHEN CAST(Kor AS INTEGER) BETWEEN 80 AND 89 THEN '80-89'
    ELSE '90+'
    END AS AgeRange,
    COUNT(*) AS Count
    FROM Szimulació
    GROUP BY  AgeRange
    ORDER BY MIN(CAST(Kor AS INTEGER))
    """
)
össziskell=data.query(
    """
    Select
    Oktatás, count(*) as okt
    from Szimulació
    Group by Oktatás
    """
    )


print(korell)
print(varosell)
print(iskell)
print(össziskell,összkorell,össznemell)

data.close()


