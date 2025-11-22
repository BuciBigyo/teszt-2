import sqlite3
import pandas as pd
import random
import numpy as np
from typing import Optional, Tuple, List
from Table import tablakezelo


data=tablakezelo("populacio.db","Szimulació")
data.create_table()
data.create_sratio_table()
data.create_aratio_table()
data.create_lakasfel_table("Lakasfeltoltes")
data.reset_table()
helytab=pd.read_sql_query("select * from TelepulesOsszegzett",data.conn)
laktab=pd.read_sql_query("select * from LakasOsszegzett",data.conn)

def random_age_from_range(age_range: str) -> int:
    age_range = age_range.replace(" koru", "")
    if "+" in age_range:
        start = int(age_range.replace("+", ""))
        return np.random.randint(start, start + 11)  # 90+ koru → 90–100
    else:
        
        start, end = map(int, age_range.split("-"))
        return np.random.randint(start, end + 1)
    
def korcsoport1(age: int):
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
def korcsoport2(age: int):
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
        "75 éves és idősebb": range(75, 120)
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
def assign_activity(age: int,arany:dict) -> str:
    aktivitások=list(arany.keys())
    esely=list(arany.values())
    if arany=={}:
        return "Rossz vagy nincs adat"
    if age < 6:
        return np.random.choice(aktivitások, p=esely)
    elif age < 10:
        return np.random.choice(aktivitások, p=esely)
    elif age < 15:
        return np.random.choice(aktivitások, p=esely)
    elif age<20:
        return np.random.choice(aktivitások, p=esely)
    elif age<25:
        return np.random.choice(aktivitások, p=esely)
    elif age<30:
        return np.random.choice(aktivitások, p=esely)
    elif age<35:
        return np.random.choice(aktivitások, p=esely)
    elif age<40:
        return np.random.choice(aktivitások, p=esely)
    elif age>39:
        return np.random.choice(aktivitások, p=esely)
def edureduction(age:int,education:dict)->str:
    kor=list(education.keys())
    esely=list(education.values())

    if education=={}:
        return "Rossz vagy nincs adat"
    if age<15:
        return np.random.choice(kor, p=esely)
    elif age<20:
        return np.random.choice(kor, p=esely)
    elif age<25:
        return np.random.choice(kor, p=esely)
    elif age<30:
        return np.random.choice(kor, p=esely)
    elif age<35:
        return np.random.choice(kor, p=esely)
    elif age<40:
        return np.random.choice(kor, p=esely)
    elif age<45:
        return np.random.choice(kor, p=esely)
    elif age <50:
        return np.random.choice(kor, p=esely)
    elif age<55:
        return np.random.choice(kor, p=esely)
    elif age<60:
        return np.random.choice(kor, p=esely)
    elif age<65:
        return np.random.choice(kor, p=esely)
    elif age<70:
        return np.random.choice(kor, p=esely)
    elif age<75:
        return np.random.choice(kor, p=esely)
    elif age>74:
        return np.random.choice(kor, p=esely)
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

    age_groups = {k: row[k] for k in row.index if "koru" in k}

    people = []

    for age_range, count in age_groups.items():
        if pd.isna(count) or count==0:
            continue
        age_range=age_range.replace(" koru","")
        count=int(count)
        genders = np.random.choice( 
            ["Férfi", "Nő"],
            size=count,
            p=[férfiráta, nőráta]
        )
        for g in genders:
            age = random_age_from_range(age_range)
            kor1=korcsoport1(age)
            kor2=korcsoport2(age)
            konkráta, szumma=data.get_eratios(g,kor1,megye,teltip)
            education = assign_education(age,konkráta)
            ered=data.edueasy(g,kor2,megye,teltip)
            edured=edureduction(age,ered)
            aráta=data.get_aratios(g,kor2,edured,megye,teltip)
            activity=assign_activity(age,aráta)
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
                "Aktivitas":activity,
                "Kapcsolat": marital,
                "Munkaviszony": work
            })
            

    return pd.DataFrame(people)

            
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


varosell=data.query("""
select Lakhely, Nem, count(*) as eredmeny
from Szimulació
Group by Lakhely, Nem
""")

korell = data.query("""
SELECT 
Lakhely,
CASE
WHEN CAST(Kor AS INTEGER) BETWEEN 0 AND 9  THEN '0-9 koru'
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
    WHEN CAST(Kor AS INTEGER) BETWEEN 0 AND 9  THEN '0-9 koru'
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
print("Város nemek szerint:\n",varosell)
print("Város korcsoportok szerint:\n",korell)
print("Város iskolázottság szerint:\n",iskell)
print("Összesített nemek szerint:\n",össznemell)
print("Összesített korcsoportok szerint:\n",összkorell)
print("Összesített iskolázottság szerint:\n",össziskell)    

data.close()


