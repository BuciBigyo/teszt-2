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
print("Gazdasági aktivitás adatok:")
print(hga_lin.head())
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
print(aktratio.head(20))

aktratio["Arany"]=aktratio["Lakossag"]/aktratio["Osszes"]
aktratio["Arany"] = aktratio["Arany"].replace([np.inf, -np.inf], 0).fillna(0)

print(aktratio.head(20))
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

print(tanratio.head(200))
data.insert_ratios(tanratio, "school_ratios")

names=ht["Helység megnevezése"]
nepesseg24=ht["Lakó-népesség"]
lakasszam=ht["Lakások száma"]


helytab=ht[["Helység megnevezése","Vármegye","Településtípus","Lakó-népesség","Lakások száma"]]
helytab=helytab.copy()
helytab["Ferfi"]=None
helytab["No"]=None
helytab["Lakok"]=helytab["Ferfi"]+helytab["No"]
helytab["0-9 koru"]=None
helytab["10-19 koru"]=None
helytab["20-29 koru"]=None
helytab["30-39 koru"]=None
helytab["40-49 koru"]=None
helytab["50-59 koru"]=None
helytab["60-69 koru"]=None
helytab["70-79 koru"]=None
helytab["80-89 koru"]=None
helytab["90+ koru"]=None
helytab["Nőtlen"]=None
helytab["Házas"]=None
helytab["Özvegy"]=None
helytab["Elvált"]=None
helytab["15 évnél fiatalabb"]=None
helytab["Helység típus"]=None
helytab["Helység megye"]=None
laktab=helytab
   
for index,row in helytab.iterrows():

    név=row.iloc[0]
    
    try:
        adatok=na[név]
        lakadat=hl[név]
        hazadat=ha[név]

        helytab.loc[index, "Ferfi"]  = adatok[0]
        helytab.loc[index, "No"]  = adatok[1]
        helytab.loc[index, "Lakok"]  = adatok[0] + adatok[1]
        helytab.loc[index, "0-9 koru"]  = adatok[2]
        helytab.loc[index, "10-19 koru"]  = adatok[3]
        helytab.loc[index, "20-29 koru"]  = adatok[4]
        helytab.loc[index, "30-39 koru"]  = adatok[5]
        helytab.loc[index, "40-49 koru"] = adatok[6]
        helytab.loc[index, "50-59 koru"] = adatok[7]
        helytab.loc[index, "60-69 koru"] = adatok[8]
        helytab.loc[index, "70-79 koru"] = adatok[9]
        helytab.loc[index, "80-89 koru"] = adatok[10]
        helytab.loc[index, "90+ koru "] = adatok[11]
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

for index, row in laktab.iterrows():
    név=row.iloc[0]
    try:
        lakadat=hl[név]
        hazadat=ha[név]
        adatok=na[név]
        laktab.loc[index, "Ferfi"]  = adatok[0]
        laktab.loc[index, "No"]  = adatok[1]
        laktab.loc[index, "Lakok"]  = adatok[0] + adatok[1]
        laktab.loc[index,"Lakott lakás"]=lakadat[0]
        laktab.loc[index,"1 szoba"]=lakadat[1]
        laktab.loc[index,"2 szoba"]=lakadat[2]
        laktab.loc[index,"3 szoba"]=lakadat[3]
        laktab.loc[index,"4 vagy több szoba"]=lakadat[4]
        laktab.loc[index,"1 személyes háztartás"]=hazadat[0]
        laktab.loc[index,"2 személyes háztartás"]=hazadat[1]
        laktab.loc[index,"3 személyes háztartás"]=hazadat[2]
        laktab.loc[index,"4 személyes háztartás"]=hazadat[3]
        laktab.loc[index,"5 személyes háztartás"]=hazadat[4]
        laktab.loc[index,"6+ személyes háztartás"]=hazadat[5]


        laktab.loc[index,"Lakott nepesseg"]=hazadat[0]*1+hazadat[1]*2+hazadat[2]*3+hazadat[3]*4+hazadat[4]*5+hazadat[5]*6
        a=(hazadat[0]*1+hazadat[1]*2+hazadat[2]*3+hazadat[3]*4+hazadat[4]*5+hazadat[5]*6)-adatok[0]-adatok[1]
        if a>0 or a<0:
            if hazadat[5]!=0:
                laktab.loc[index,"Hat+ személyes háztartás szorzo"]=-1*a/hazadat[5]+6
            else:
                laktab.loc[index,"Hat+ személyes háztartás szorzo"]=6
        elif a==0:
            laktab.loc[index,"Hat+ személyes háztartás szorzo"]=6
        print("Lakott népesség:",laktab.loc[index,"Lakott nepesseg"])
        print("különbség:",a)
        print("Lakó népesség:",adatok[0]+adatok[1])
        print(laktab.loc[index,"Hat+ személyes háztartás szorzo"])
            


        laktab.loc[index,"Egy családból álló háztartás"]=hazadat[6]
        laktab.loc[index,"Több családból álló háztartás"]=hazadat[9]
        laktab.loc[index,"Nem családháztartás"]=hazadat[12]
        laktab.loc[index,"Nincs 15 évesnél fiatalabb személy a háztartásban"]=hazadat[14]
        laktab.loc[index,"1 személy 15 évesnél fiatalabb a háztartásban"]=hazadat[15]
        laktab.loc[index,"2 személy 15 évesnél fiatalabb a háztartásban"]=hazadat[16]
        laktab.loc[index,"3 vagy több személy 15 évesnél fiatalabb a háztartásban"]=hazadat[17]
        laktab.loc[index,"Nincs 30 évesnél fiatalabb személy a háztartásban"]=hazadat[18]
        laktab.loc[index,"1 személy 30 évesnél fiatalabb a háztartásban"]=hazadat[19]
        laktab.loc[index,"2 személy 30 évesnél fiatalabb a háztartásban"]=hazadat[20]
        laktab.loc[index,"3 vagy több személy 30 évesnél fiatalabb a háztartásban"]=hazadat[21]
        laktab.loc[index,"Nincs 30–64 éves személy a háztartásban"]=hazadat[22]
        laktab.loc[index,"1 személy 30–64 éves a háztartásban"]=hazadat[23]
        laktab.loc[index,"2 személy 30–64 éves a háztartásban"]=hazadat[24]
        laktab.loc[index,"3 vagy több személy 30–64 éves a háztartásban"]=hazadat[25]
        laktab.loc[index,"Nincs 65 éves és idősebb személy a háztartásban"]=hazadat[26]
        laktab.loc[index,"1 személy 65 éves és idősebb a háztartásban"]=hazadat[27]
        laktab.loc[index,"2 személy 65 éves és idősebb a háztartásban"]=hazadat[28]
        laktab.loc[index,"3 vagy több személy 65 éves és idősebb a háztartásban"]=hazadat[29]  
        laktab.loc[index,"Csak 30 évesnél fiatalabb személy van a háztartásban"]=hazadat[30]
        laktab.loc[index,"Csak 30–64 éves személy van a háztartásban"]=hazadat[31]
        laktab.loc[index,"Csak 65 éves és idősebb személy van a háztartásban"]=hazadat[    32]
        laktab.loc[index,"30 évesnél fiatalabb és 30–64 éves személyek vannak a háztartásban"]=hazadat[ 33]
        laktab.loc[index,"30 évesnél fiatalabb és 65 éves és idősebb személyek vannak a háztartásban"]=hazadat[ 34]
        laktab.loc[index,"30–64 éves és 65 éves és idősebb személyek vannak a háztartásban"]=hazadat[ 35]
        laktab.loc[index,"30 évesnél fiatalabb, 30–64 éves és 65 éves és idősebb személyek vannak a háztartásban"]=hazadat[ 36]
        laktab.loc[index,"Nincs foglalkoztatott személy a háztartásban"]=hazadat[  37]
        laktab.loc[index,"1 foglalkoztatott személy van a háztartásban"]=hazadat[ 38]
        laktab.loc[index,"2 foglalkoztatott személy van a háztartásban"]=hazadat[  39]
        laktab.loc[index,"3 vagy több foglalkoztatott személy van a háztartásban"]=hazadat[ 40]
        laktab.loc[index,"Nincs munkanélküli személy a háztartásban"]=hazadat[ 41]
        laktab.loc[index,"1 munkanélküli személy van a háztartásban"]=hazadat[ 42]
        laktab.loc[index,"2 munkanélküli személy van a háztartásban"]=hazadat[ 43]
        laktab.loc[index,"3 vagy több munkanélküli személy van a háztartásban"]=hazadat[ 44]
        laktab.loc[index,"Nincs ellátásban részesülő inaktív személy a háztartásban"]=hazadat[ 45]
        laktab.loc[index,"1 ellátásban részesülő inaktív személy van a háztartásban"]=hazadat[ 46]
        laktab.loc[index,"2 ellátásban részesülő inaktív személy van a háztartásban"]=hazadat[ 47]
        laktab.loc[index,"3 vagy több ellátásban részesülő inaktív személy van a háztartásban"]=hazadat[ 48]
        laktab.loc[index,"Nincs eltartott személy a háztartásban"]=hazadat[49]
        laktab.loc[index,"1 eltartott személy van a háztartásban"]=hazadat[ 50]
        laktab.loc[index,"2 eltartott személy van a háztartásban"]=hazadat[ 51]
        laktab.loc[index,"3 vagy több eltartott személy van a háztartásban"]=hazadat[  52]
        laktab.loc[index,"Van foglalkoztatott a háztartásban"]=hazadat[    53]
        laktab.loc[index,"Nincs foglalkoztatott a háztartásban"]=hazadat[   54]

    except:
        print("Nincs ilyen város",név)


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

