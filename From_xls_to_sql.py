import sqlite3
import pandas as pd
import random
import numpy as np
from Table import tablakezelo

data=tablakezelo("populacio.db","Szimulació")
data.create_table()
data.create_ratio_table()
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
#laktab=helytab.copy()
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
"""
for index,row in laktab.iterrows():
    hnév=row.iloc[0]
    try:
        lakadat=hl[hnév]
        hazadat=ha[hnév]
        laktab.loc[index,"Lakott lakás"]=lakadat[0]
        laktab.loc[index,"1 szoba"]=lakadat[1]
        laktab.loc[index,"2 csoba"]=lakadat[2]
        laktab.loc[index,"3 szoba"]=lakadat[3]
        laktab.loc[index,"4 vagy több szoba"]=lakadat[4]
        laktab.loc[index,"Egyszemélyes háztartás"]=hazadat[0]
        laktab.loc[index,"Kétszemélyes háztartás"]=hazadat[1]
        laktab.loc[index,"Háromszemélyes Háztartás"]=hazadat[2]
        laktab.loc[index,"Négyszemélyes háztartás"]=hazadat[3]
        laktab.loc[index,"Ötszemélyes háztartás"]=hazadat[4]
        laktab.loc[index,"Hat vagy többszemélyes háztartás"]=hazadat[5]
        laktab.loc[index,"Egy családból álló háztartás"]=hazadat[6]
        laktab.loc[index,"Több családból álló háztartás"]=hazadat[9]
        laktab.loc[index,"Nem családháztartás"]=hazadat[12]

    except:
        print("Nincs ilyen nevű város:{hnév}")

   """     
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



def linearizalas(lak:pd.DataFrame)-> pd.DataFrame:
    data=lak.copy()
    szobasoszlopok=[c for c in data.columns if str[c].lower().endswith("háztartás")]
    hosszított=szobasoszlopok.melt(id_vars=["LakhelyID"],value_vars=szobasoszlopok,var_name="lak_meret",value_name="lakszam")
    hosszított["lak_meret"]=hosszított["lak_meret"].str.replace(" személyes háztartás","",regex=False).astype(int)
    hosszított["lakszam"]=hosszított["lakszam"].fillna(0).astype(int)
    hosszított=hosszított[hosszított["lakszam"]>0]
    return hosszított.sort_values(["LakhelyID","lak_meret"])

def build_households_from_counts(hh_counts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: hh_counts_df (long or wide). Output households table:
      HouseholdID (int), LakhelyID (int), hh_size (int).
    HouseholdID scheme: LakhelyID*1_000_000 + per-city sequence.
    """
    long = linearizalas(hh_counts_df)
    rows = []
    for (city,), grp in long.groupby(["LakhelyID"]):
        seq = 0
        for _, r in grp.iterrows():
            s, n = int(r.lak_meret), int(r.lakszam)
            for _ in range(n):
                seq += 1
                rows.append({"LakhelyID": int(city), "lak_meret": s, "HouseholdID": int(city)*1_000_000 + seq})
    return pd.DataFrame(rows, columns=["HouseholdID","LakhelyID","lak_meret"])

people_df=data.query("""select * from Szimulació""")

def assign_people_to_households(people_df: pd.DataFrame,
                                households_df: pd.DataFrame,
                                adult_age_cutoff: int = 18,
                                try_require_adult: bool = True) -> pd.DataFrame:
    """
    Returns household_members:
       HouseholdID, LakosID, role ('head' or 'member'), LakhelyID
    - Fills exactly hh_size people per household.
    - If 'age' present and try_require_adult=True, tries to put ≥1 adult in each HH.
    - Raises if a city doesn't have enough people.
    """
    # normalization
    if "LakosID" not in people_df.columns:
        # fall back to a deterministic ID
        people_df = people_df.copy()
        people_df = people_df.sort_values(["LakhelyID"]).reset_index(drop=True)
        people_df["LakosID"] = people_df.groupby("LakhelyID").cumcount()+1 + people_df["LakhelyID"]*10_000_000

    out_rows = []

    for city, hh_g in households_df.groupby("LakhelyID"):
        hh_g = hh_g.sort_values("HouseholdID")
        ppl = people_df[people_df["LakhelyID"]==city].copy()

        # Quick check: totals must match exactly
        need = int(hh_g["hh_size"].sum())
        if len(ppl) < need:
            raise ValueError(f"City {city}: not enough people ({len(ppl)}) for required {need} household slots.")
        if len(ppl) > need:
            # We'll just leave extras unassigned (you can handle them later if needed)
            ppl = ppl.head(need).copy()

        # Try to ensure ≥1 adult per HH if age present
        has_age = "Kor" in ppl.columns
        if try_require_adult and has_age:
            adults = ppl[ppl["Kor"] >= adult_age_cutoff].sample(frac=1, random_state=42).reset_index(drop=True)
            kids   = ppl[ppl["Kor"] <  adult_age_cutoff].sample(frac=1, random_state=43).reset_index(drop=True)
            a_idx, k_idx = 0, 0
            for _, hh in hh_g.iterrows():
                k = int(hh.hh_size)
                members = []

                # pick one adult if available
                if a_idx < len(adults):
                    members.append(("fej", int(adults.loc[a_idx, "LakosID"])))
                    a_idx += 1
                else:
                    # fallback: no adult left; take a kid as head
                    members.append(("fej", int(kids.loc[k_idx, "LakosID"])))
                    k_idx += 1

                # fill the rest, prefer kids first (optional)
                while len(members) < k and k_idx < len(kids):
                    members.append(("tag", int(kids.loc[k_idx, "LakosID"])))
                    k_idx += 1
                while len(members) < k and a_idx < len(adults):
                    members.append(("tag", int(adults.loc[a_idx, "LakosID"])))
                    a_idx += 1

                if len(members) < k:
                    raise RuntimeError(f"City {city}: ran out of people while filling Household {hh.HouseholdID}.")

                for role, pid in members:
                    out_rows.append({"LakhelyID": int(city),
                                     "HouseholdID": int(hh.HouseholdID),
                                     "LakosID": pid,
                                     "Szerep": role})
        else:
            # Simple fill: shuffled order, first is head
            ppl = ppl.sample(frac=1, random_state=44).reset_index(drop=True)
            p_idx = 0
            for _, hh in hh_g.iterrows():
                k = int(hh.hh_size)
                chosen = ppl.iloc[p_idx:p_idx+k]
                p_idx += k
                for j, pid in enumerate(chosen["LakosID"].tolist()):
                    out_rows.append({"LakhelyID": int(city),
                                     "HouseholdID": int(hh.HouseholdID),
                                     "LakosID": int(pid),
                                     "role": "fej" if j==0 else "member"})

    return pd.DataFrame(out_rows, columns=["HouseholdID","LakosID","LakhelyID","role"])


embik=pd.DataFrame({"Lakhely","Nem","Kor","Oktatás"})

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
    kisisk=row.get("Nincs 8 ált.",0)
    ballagott=row.get("8 általános",0)
    szakköz=row.get("Szakmai okl",0)
    gimi=row.get("Érettségi",0)
    magasisk=row.get("Diploma/Oklevél",0)
    Nőtlen=row.get("Nőtlen",0)
    Házas=row.get("Nőtlen",0)
    Özvegy=row.get("Özvegy",0)
    Elvált=row.get("Elvált",0)
    #Kiskorú=row.get("15 évnél fiatalabb",0)
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

    age_groups = {k: row[k] for k in row.index if "0" in k or "+" in k}

    people = []
    
    for age_range, count in age_groups.items():
        genders = np.random.choice( 
            ["Férfi", "Nő"],
            size=count,
            p=[férfiráta, nőráta]
        )
        print(count)
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


for index, row in helytab.head(5).iterrows():
    hely=row["Helység megnevezése"]
    varos=szimulacio(index,row)
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


