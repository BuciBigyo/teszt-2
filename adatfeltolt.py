import sqlite3
import pandas as pd
import random
import numpy as np
from typing import Optional, Tuple, List
from Table import tablakezelo

data=tablakezelo("populacio.db","Szimulacio")
data.create_table()
data.create_sratio_table()
data.create_aratio_table()
data.create_lakasfel_table("Lakasfeltoltes")
data.reset_table()

ht = pd.read_excel("telepules_hierarchia.xlsx")
ha=pd.read_excel("flat_A_haztartasok_adatai_telepulesenkent.xlsx")
hl=pd.read_excel("flat_A_lakasok_legfontosabb_jellemzok_telepulesenkent.xlsx")
na=pd.read_excel("flat_A_nepesseg_adatok_telepulesenkent.xlsx")
hi=pd.read_excel("hier_iskolaba_jaro_nepesseg.xlsx",header=[0,1])
hfa=pd.read_excel("hier_foglalkoztatott_nepesseg_foglalkozasi_focsoport.xlsx",header=[0,1])
hga=pd.read_excel("hier_gazdasagi_aktivitas_varmegyenkent_telepulestipusonkent.xlsx",header=[0,1])
ils=pd.read_excel("duplicate_flat_Intezeti_es_hajl.xlsx")
nkh=pd.read_excel("hier_nemek_korosztalyonkent.xlsx",header=[0,1])
rlc=pd.read_excel("hier_lak_komb.xlsx",header=[0,1])

nkh.rename(columns={nkh.columns[0]:("","Nem"),
                    nkh.columns[1]:("","Korcsoport"),},inplace=True)
nkh.columns = [
    col[1] if col[1] in ["Nem", "Korcsoport"]
    else f"{col[0].strip()} | {col[1].strip()}"
    for col in nkh.columns
]
nkh.rename(columns={
    ('Unnamed: 0_level_0 | Unnamed: 0_level_1'): 'Nem',
    ('Unnamed: 1_level_0 | Unnamed: 1_level_1'): 'Korcsoport'
    },inplace=True)
nkh[["Nem","Korcsoport"]]=nkh[["Nem","Korcsoport"]].ffill()

nkh_lin = nkh.melt(
    id_vars=["Nem", "Korcsoport"],
    var_name="Location",
    value_name="Lakossag"
)
nkh_lin[["Megye", "TelepulesTipus"]] = nkh_lin["Location"].str.split(" \| ",n=1, expand=True)
nkh_lin.drop(columns="Location", inplace=True)
data.insert_ratios(nkh_lin,"Korok_nemenként_regio")


rlc.rename(columns={
    rlc.columns[0]: ("", "Lakasmeret"),
    rlc.columns[1]: ("", "Koreloszlas"),
    rlc.columns[2]: ("", "GazdAkt")
}, inplace=True)

rlc.columns = [
    col[1] if col[1] in ["Lakasmeret", "Koreloszlas","GazdAkt"]
    else f"{col[0].strip()} | {col[1].strip()}"
    for col in rlc.columns
]

rlc.rename(columns={
    ('Unnamed: 0_level_0 | Unnamed: 0_level_1'): 'Lakasmeret',
    ('Unnamed: 1_level_0 | Unnamed: 1_level_1'): 'Koreloszlas',
    ('Unnamed: 2_level_0 | Unnamed: 2_level_1'): 'GazdAkt',
    },inplace=True)
rlc[["Lakasmeret","Koreloszlas"]]=rlc[["Lakasmeret","Koreloszlas"]].ffill()
rlc_lin = rlc.melt(
    id_vars=["Lakasmeret", "Koreloszlas","GazdAkt"],
    var_name="Location",
    value_name="Lakossag"
)

rlc[["Lakasmeret","Koreloszlas"]]=rlc[["Lakasmeret","Koreloszlas"]].ffill()
rlc_lin[["Megye", "TelepulesTipus"]] = rlc_lin["Location"].str.split(" \| ",n=1, expand=True)
rlc_lin.drop(columns="Location", inplace=True)
ottossz=(
    rlc_lin
    .groupby(["Lakasmeret", "Koreloszlas", "Megye", "TelepulesTipus"], as_index=False)["Lakossag"]
    .sum()
    .rename(columns={"Lakossag": "Osszes"})
)

ottratio=rlc_lin.merge(ottossz, on=["Lakasmeret","Koreloszlas","Megye","TelepulesTipus"])
ottratio["Arany"]=ottratio["Lakossag"]/ottratio["Osszes"]
ottratio["Arany"] = ottratio["Arany"].replace([np.inf, -np.inf], 0).fillna(0)
data.insert_ratios(ottratio, "lakas_kor_gazdakt_ratios")

hga.rename(columns={
    hga.columns[0]: ("", "Nem"),
    hga.columns[1]: ("", "Korcsoport"),
    hga.columns[2]: ("", "IskolaVég"),
    hga.columns[3]:("","GazdAkt")
}, inplace=True)

hga.columns = [
    col[1] if col[1] in ["Nem", "Korcsoport", "IskolaVég","GazdAkt"]
    else f"{col[0].strip()} | {col[1].strip()}"
    for col in hga.columns
]

hga.rename(columns={
    ('Unnamed: 0_level_0 | Unnamed: 0_level_1'): 'Nem',
    ('Unnamed: 1_level_0 | Unnamed: 1_level_1'): 'Korcsoport',
    ('Unnamed: 2_level_0 | Unnamed: 2_level_1'): 'IskolaVég',
    ('Unnamed: 3_level_0 | Unnamed: 3_level_1'): 'GazdAkt'
    },inplace=True)
hga[["Nem","Korcsoport","IskolaVég"]]=hga[["Nem","Korcsoport","IskolaVég"]].ffill()
hga_lin = hga.melt(
    id_vars=["Nem", "Korcsoport", "IskolaVég","GazdAkt"],
    var_name="Location",
    value_name="Lakossag"
)
hga[["Nem","Korcsoport","Iskolavég"]]=hga[["Nem","Korcsoport","IskolaVég"]].ffill()
hga_lin[["Megye", "TelepulesTipus"]] = hga_lin["Location"].str.split(" \| ",n=1, expand=True)
hga_lin.drop(columns="Location", inplace=True)

aktossz=(
    hga_lin
    .groupby(["Nem", "Korcsoport","IskolaVég", "Megye", "TelepulesTipus"], as_index=False)["Lakossag"]
    .sum()
    .rename(columns={"Lakossag": "Osszes"})
)
aktratio=hga_lin.merge(aktossz, on=["Nem","Korcsoport","IskolaVég","Megye","TelepulesTipus"])

aktratio["Arany"]=aktratio["Lakossag"]/aktratio["Osszes"]
aktratio["Arany"] = aktratio["Arany"].replace([np.inf, -np.inf], 0).fillna(0)

data.insert_ratios(aktratio, "activity_ratios")


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
hfa[["Nem","Korcsoport","IskolaVég"]]=hfa[["Nem","Korcsoport","IskolaVég"]].ffill()
hfa_lin = hfa.melt(
    id_vars=["Nem", "Korcsoport", "IskolaVég","Munkatípus"],
    var_name="Location",
    value_name="Lakossag"
)

hfa_lin[["Megye", "TelepulesTipus"]] = hfa_lin["Location"].str.split(" \| ",n=1, expand=True)
hfa_lin.drop(columns="Location", inplace=True)

foglossz=(
    hfa_lin
    .groupby(["Nem", "Korcsoport","IskolaVég", "Megye", "TelepulesTipus"], as_index=False)["Lakossag"]
    .sum()
    .rename(columns={"Lakossag": "Osszes"})
)
foglratio=hfa_lin.merge(foglossz, on=["Nem","Korcsoport","IskolaVég","Megye","TelepulesTipus"])
foglratio["Arany"]=foglratio["Lakossag"]/foglratio["Osszes"]
foglratio["Arany"] = foglratio["Arany"].replace([np.inf, -np.inf], 0).fillna(0)
data.insert_ratios(foglratio, "employment_ratios")





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

data.insert_ratios(tanratio, "school_ratios")

names=ht["Helység megnevezése"]
nepesseg24=ht["Lakó-népesség"]
lakasszam=ht["Lakások száma"]


helytab=ht[["Helység megnevezése","Vármegye","Településtípus","Lakó-népesség","Lakások száma"]]
helytab=helytab.copy()
laktab=helytab
def as_int(x, default=0):
    """Coerce x to int; NaN/None/invalid -> default."""
    try:
        v = pd.to_numeric(x)
        if pd.isna(v):
            return default
        return int(round(float(v)))
    except Exception:
        return default

def safe_get(seq, i, default=0):
    """Index a list/tuple safely + cast to int."""
    try:
        return as_int(seq[i], default)
    except Exception:
        return default

def safe_div(num, den, default=0.0):
    """num/den with zero/NaN protection."""
    try:
        den = float(den)
        if den == 0:
            return default
        return float(num) / den
    except Exception:
        return default
   
for index, row in helytab.iterrows():
    név = row.iloc[0]
    try:
        adatok  = na[név]   # [Férfi, Nő, 0-9, 10-19, ..., 90+, 15- férfi, 15-64 férfi, 65+ férfi, 15- nő, 15-64 nő, 65+ nő, ..., iskolai szintek, ..., 7 évnél fiatalabb, fogl., munkan., inaktív, eltartott]
        lakadat = hl[név]   # [Lakott lakás, 1 szoba, 2 szoba, 3 szoba, 4+ szoba]
        hazadat = ha[név]   # háztartás méret és összetétel indexek szerint
        intezet = ils[név]  # [ ... , 10: Intézeti háztartásban élő személy, 11: Hajléktalan]

        ferfi = safe_get(adatok, 0)
        no    = safe_get(adatok, 1)
        lakok = ferfi + no
        helykül  = abs(ferfi - no)
        helyszaz = safe_div(helykül * 100.0, lakok, default=0.0)

        tarolo = {
            "Ferfi": ferfi,
            "No": no,
            "Lakok": lakok,
            "Nemkulonbseg": helykül,
            "Különbség százalék": helyszaz,

            "Intézeti háztartásban élő személy": safe_get(intezet, 10),
            "Hajléktalan": safe_get(intezet, 11),

            "0-9 koru":   safe_get(adatok, 2),
            "10-19 koru": safe_get(adatok, 3),
            "20-29 koru": safe_get(adatok, 4),
            "30-39 koru": safe_get(adatok, 5),
            "40-49 koru": safe_get(adatok, 6),
            "50-59 koru": safe_get(adatok, 7),
            "60-69 koru": safe_get(adatok, 8),
            "70-79 koru": safe_get(adatok, 9),
            "80-89 koru": safe_get(adatok,10),
            "90+ koru ":  safe_get(adatok,11),

            "15 évesnél fiatalabb férfi": safe_get(adatok,12),
            "15-64 éves férfi":           safe_get(adatok,13),
            "65 éves és idősebb férfi":   safe_get(adatok,14),
            "15 évesnél fiatalabb nő":    safe_get(adatok,15),
            "15-64 éves nő":              safe_get(adatok,16),
            "65 éves és idősebb nő":      safe_get(adatok,17),

            "Nőtlen": safe_get(adatok,18),
            "Házas":  safe_get(adatok,19),
            "Özvegy": safe_get(adatok,20),
            "Elvált": safe_get(adatok,21),

            "15 évnél fiatalabb személy": safe_get(adatok,22),
            "7 évnél fiatalabb":          safe_get(adatok,34),

            "Nincs 8 ált.":    safe_get(adatok,29),
            "8 általános":     safe_get(adatok,30),
            "Szakmai okl":     safe_get(adatok,31),
            "Érettségi":       safe_get(adatok,32),
            "Diploma/Oklevél": safe_get(adatok,33),

            "Foglalkoztatott":              safe_get(adatok,35),
            "Munkanélküli":                  safe_get(adatok,36),
            "Ellátásban részesülő inaktív": safe_get(adatok,37),
            "Eltartott":                    safe_get(adatok,38),

            "Lakott lakás":      safe_get(lakadat,0),
            "1 szoba":           safe_get(lakadat,1),
            "2 szoba":           safe_get(lakadat,2),
            "3 szoba":           safe_get(lakadat,3),
            "4 vagy több szoba": safe_get(lakadat,4),

            "1 személyes háztartás": safe_get(hazadat,0),
            "2 személyes háztartás": safe_get(hazadat,1),
            "3 személyes háztartás": safe_get(hazadat,2),
            "4 személyes háztartás": safe_get(hazadat,3),
            "5 személyes háztartás": safe_get(hazadat,4),
            "6+ személyes háztartás": safe_get(hazadat,5),

            "Egy családból álló háztartás": safe_get(hazadat,6),
            "Több családból álló háztartás": safe_get(hazadat,9),
            "Nem családháztartás":          safe_get(hazadat,12),
        }

        helytab.loc[index, list(tarolo.keys())] = list(tarolo.values())

    except Exception as e:
        print("Nincs ilyen város", név, "Hiba:", e)

for index, row in laktab.iterrows():
    név = row.iloc[0]
    try:
        adatok  = na[név]   # [Ferfi, No, ...]
        lakadat = hl[név]   # rooms etc.
        hazadat = ha[név]   # household distributions (big vector)
        intezet = ils[név]  # institutional, homeless

        # --- basic people counts + % diff ---
        ferfi  = safe_get(adatok, 0)
        no     = safe_get(adatok, 1)
        lakok  = ferfi + no
        nemkül = abs(ferfi - no)
        kulsz  = safe_div(nemkül * 100.0, lakok, default=0.0)

        # --- household size counts ---
        H1 = safe_get(hazadat, 0)
        H2 = safe_get(hazadat, 1)
        H3 = safe_get(hazadat, 2)
        H4 = safe_get(hazadat, 3)
        H5 = safe_get(hazadat, 4)
        H6p = safe_get(hazadat, 5)   # 6+


        # computed capacity if we treat 6+ as "6" heads baseline
        lakott_nep = 1*H1 + 2*H2 + 3*H3 + 4*H4 + 5*H5 + 6*H6p
        diff = lakott_nep - lakok
        inst_diff=lakott_nep-lakok+safe_get(intezet,10)+safe_get(intezet,11)
        # match your original: -a/hazadat[5] + 6  (safe if H6p==0)
        hatplusz_szorzo = 6 if H6p == 0 else 6 - safe_div(diff, H6p, default=0.0)
        hatplusz_inst=6 if H6p == 0 else 6 - safe_div(inst_diff, H6p,default=0.0)

        tarolo = {
            # people + simple diagnostics
            "Ferfi": ferfi,
            "No": no,
            "Lakok": lakok,
            "Nemkulonbseg": nemkül,
            "Különbség százalék": kulsz,

            # rooms / dwellings
            "Lakott lakás":        safe_get(lakadat, 0),
            "1 szoba":             safe_get(lakadat, 1),
            "2 szoba":             safe_get(lakadat, 2),
            "3 szoba":             safe_get(lakadat, 3),
            "4 vagy több szoba":   safe_get(lakadat, 4),

            # household sizes
            "1 személyes háztartás": H1,
            "2 személyes háztartás": H2,
            "3 személyes háztartás": H3,
            "4 személyes háztartás": H4,
            "5 személyes háztartás": H5,
            "6+ személyes háztartás": H6p,

            # institutional / homeless
            "Intézeti háztartásban élő személy": safe_get(intezet, 10),
            "Hajléktalan":                       safe_get(intezet, 11),

            # derived capacity + correction
            "Lakott nepesseg": lakott_nep,
            "Különbség":       diff,
            "Intézeti/Hajléktalan korrigált különbség": inst_diff,
            "Hat+ személyes háztartás szorzo": hatplusz_szorzo,
            "Hat+ személyes háztartás szorzo (int./hajl. korrigált)": hatplusz_inst,

            # household type blocks
            "Egy családból álló háztartás":  safe_get(hazadat, 6),
            "Több családból álló háztartás": safe_get(hazadat, 9),
            "Nem családháztartás":          safe_get(hazadat, 12),

            # age composition per household (0/1/2/3+)
            "Nincs 15 évesnél fiatalabb személy a háztartásban": safe_get(hazadat, 14),
            "1 személy 15 évesnél fiatalabb a háztartásban":     safe_get(hazadat, 15),
            "2 személy 15 évesnél fiatalabb a háztartásban":     safe_get(hazadat, 16),
            "3 vagy több személy 15 évesnél fiatalabb a háztartásban": safe_get(hazadat, 17),

            "Nincs 30 évesnél fiatalabb személy a háztartásban": safe_get(hazadat, 18),
            "1 személy 30 évesnél fiatalabb a háztartásban":     safe_get(hazadat, 19),
            "2 személy 30 évesnél fiatalabb a háztartásban":     safe_get(hazadat, 20),
            "3 vagy több személy 30 évesnél fiatalabb a háztartásban": safe_get(hazadat, 21),

            "Nincs 30–64 éves személy a háztartásban": safe_get(hazadat, 22),
            "1 személy 30–64 éves a háztartásban":     safe_get(hazadat, 23),
            "2 személy 30–64 éves a háztartásban":     safe_get(hazadat, 24),
            "3 vagy több személy 30–64 éves a háztartásban": safe_get(hazadat, 25),

            "Nincs 65 éves és idősebb személy a háztartásban": safe_get(hazadat, 26),
            "1 személy 65 éves és idősebb a háztartásban":     safe_get(hazadat, 27),
            "2 személy 65 éves és idősebb a háztartásban":     safe_get(hazadat, 28),
            "3 vagy több személy 65 éves és idősebb a háztartásban": safe_get(hazadat, 29),

            # “only / combination” age patterns
            "Csak 30 évesnél fiatalabb személy van a háztartásban":                          safe_get(hazadat, 30),
            "Csak 30–64 éves személy van a háztartásban":                                   safe_get(hazadat, 31),
            "Csak 65 éves és idősebb személy van a háztartásban":                           safe_get(hazadat, 32),
            "30 évesnél fiatalabb és 30–64 éves személyek vannak a háztartásban":           safe_get(hazadat, 33),
            "30 évesnél fiatalabb és 65 éves és idősebb személyek vannak a háztartásban":   safe_get(hazadat, 34),
            "30–64 éves és 65 éves és idősebb személyek vannak a háztartásban":             safe_get(hazadat, 35),
            "30 évesnél fiatalabb, 30–64 éves és 65 éves és idősebb személyek vannak a háztartásban": safe_get(hazadat, 36),

            # labour counts per household (0/1/2/3+)
            "Nincs foglalkoztatott személy a háztartásban":        safe_get(hazadat, 37),
            "1 foglalkoztatott személy van a háztartásban":        safe_get(hazadat, 38),
            "2 foglalkoztatott személy van a háztartásban":        safe_get(hazadat, 39),
            "3 vagy több foglalkoztatott személy van a háztartásban": safe_get(hazadat, 40),

            "Nincs munkanélküli személy a háztartásban":           safe_get(hazadat, 41),
            "1 munkanélküli személy van a háztartásban":           safe_get(hazadat, 42),
            "2 munkanélküli személy van a háztartásban":           safe_get(hazadat, 43),
            "3 vagy több munkanélküli személy van a háztartásban": safe_get(hazadat, 44),

            "Nincs ellátásban részesülő inaktív személy a háztartásban": safe_get(hazadat, 45),
            "1 ellátásban részesülő inaktív személy van a háztartásban": safe_get(hazadat, 46),
            "2 ellátásban részesülő inaktív személy van a háztartásban": safe_get(hazadat, 47),
            "3 vagy több ellátásban részesülő inaktív személy van a háztartásban": safe_get(hazadat, 48),

            "Nincs eltartott személy a háztartásban":  safe_get(hazadat, 49),
            "1 eltartott személy van a háztartásban":  safe_get(hazadat, 50),
            "2 eltartott személy van a háztartásban":  safe_get(hazadat, 51),
            "3 vagy több eltartott személy van a háztartásban": safe_get(hazadat, 52),

            "Van foglalkoztatott a háztartásban":   safe_get(hazadat, 53),
            "Nincs foglalkoztatott a háztartásban": safe_get(hazadat, 54),
        }

        # one-shot write
        laktab.loc[index, list(tarolo.keys())] = list(tarolo.values())

    except Exception as e:
        print("Nincs ilyen város", név, "| Hiba:", e)


num_cols = helytab.columns.difference(["Helység megnevezése","Vármegye","Településtípus"])
helytab[num_cols] = helytab[num_cols].apply(pd.to_numeric, errors="coerce")

# kiírás az adatbázisba
helytab.to_sql("TelepulesOsszegzett", data.conn, if_exists="replace", index=False)
data.conn.commit()

num_cols = laktab.columns.difference(["Helység megnevezése","Vármegye","Településtípus"])
laktab[num_cols] = laktab[num_cols].apply(pd.to_numeric, errors="coerce")

# kiírás az adatbázisba
laktab.to_sql("LakasOsszegzett", data.conn, if_exists="replace", index=False)
data.conn.commit()

