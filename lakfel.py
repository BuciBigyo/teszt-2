import sqlite3
import pandas as pd
import random
import numpy as np
from dataclasses import dataclass
from functools import lru_cache
import math,random
from collections import deque, Counter
from typing import Dict, List, Tuple, Optional, Any, Iterable
from Table import tablakezelo


data=tablakezelo("populacio.db","Szimulacio")
data.create_table()
data.create_sratio_table()
data.create_aratio_table()
data.create_lakasfel_table("Lakasfeltoltes")
data.reset_table()
helytab=pd.read_sql_query("select * from TelepulesOsszegzett",data.conn)
laktab=pd.read_sql_query("select * from LakasOsszegzett",data.conn)

with sqlite3.connect("populacio.db") as conn:
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys=OFF;")   # safety when dropping
    cur.execute("DROP TABLE IF EXISTS lakasfel_tag;")
    cur.execute("DROP TABLE IF EXISTS LakasEpitő;")
    conn.commit()

def valoskor(nev)-> list:
    kor=[]
    q2 = 'SELECT COUNT(*) FROM Szimulació WHERE TRIM(Lakhely) = ? AND CAST(Kor AS INTEGER) BETWEEN ? AND ?;'
    fiossz = data.conn.execute(q2, (nev, 0,15)).fetchone()[0]
    felossz = data.conn.execute(q2, (nev, 15,30)).fetchone()[0]
    kozossz = data.conn.execute(q2, (nev, 30,65)).fetchone()[0]
    idossz= data.conn.execute(q2,(nev,65,200)).fetchone()[0]
    kor.append(fiossz)
    kor.append(felossz)
    kor.append(kozossz)
    kor.append(idossz)
    return kor
def lakokor(fiatal:int,felnott:int, kozepes:int, idos:int,nev:str)->list:
    macska=[]
    q2 = 'SELECT COUNT(*) FROM Szimulació WHERE TRIM(Lakhely) = ? AND CAST(Kor AS INTEGER) BETWEEN ? AND ?;'
    fiossz = data.conn.execute(q2, (nev, 0,15)).fetchone()[0]
    felossz = data.conn.execute(q2, (nev, 15,30)).fetchone()[0]
    kozossz = data.conn.execute(q2, (nev, 30,65)).fetchone()[0]
    idossz= data.conn.execute(q2,(nev,65,200)).fetchone()[0]
    print("Korok:",fiossz,felossz,kozossz,idossz)
    print(fiatal,felnott,kozepes,idos)
    macska.append(-1*(fiossz-fiatal))
    macska.append(-1*(felossz-felnott+fiossz))
    macska.append(-1*(kozossz-kozepes))
    macska.append(-1*(idossz-idos))
    print(macska)
    return macska
def lakomunka(el:int,inak:int,dolg:int,munkanel:int,nev:str)->list:
    kutya=[]
    dolgossz=data.query(f"""
    select count(*)
    from Szimulació
    where Lakhely='{nev}' and munkaviszony='Foglalkoztatott'
    """)
    munkanelossz=data.query(f"""
    select count(*)
    from Szimulació
    where Lakhely='{nev}' and munkaviszony='Munkanélküli'
    """)
    eltössz=data.query(f"""
    select count(*)
    from Szimulació
    where Lakhely='{nev}' and munkaviszony='Eltartott'
    """)
    inakossz=data.query(f"""
    select count(*)
    from Szimulació
    where Lakhely='{nev}' and munkaviszony='Ellátásban részesülő inaktív'
    """)
    
    kutya.append(int(eltössz.iloc[0,0]-el))
    kutya.append(int(inakossz.iloc[0,0]-inak))
    kutya.append(int(dolgossz.iloc[0,0]-dolg))
    kutya.append(int(munkanelossz.iloc[0,0]-munkanel))
    print(kutya)
    return kutya
def k3kiszam(korelt:list,fiatal:int,felnott:int,kozepes:int,idos:int)->list:
    k3=[]
    k3.append(korelt[0]/fiatal+3 if fiatal>0 else 3)
    k3.append(korelt[1]/(felnott-fiatal)+3 if felnott>0 else 3)
    k3.append(korelt[2]/kozepes+3 if kozepes>0 else 3)
    k3.append(korelt[3]/idos+3 if idos>0 else 3)
    return k3
def m6_kiszam_multinom(m6szam:float,H6szam:int,min_size:int, seed=1234)->list:
    
    cél=m6szam*H6szam

    if H6szam==np.nan:
        raise ValueError("H6szam nem lehet NaN.")
    if cél<min_size*H6szam:
        raise ValueError("Nem lehet a megadott átlagot elérni a megadott minimummal.")
    if cél==min_size*H6szam:
        return {min_size:int(H6szam)}
    kell=int(round(cél-min_size*H6szam))
    rng=np.random.default_rng(seed)
    sizes=np.full(int(H6szam),min_size,dtype=int)
    marad=np.full(int(H6szam),min_size+kell,dtype=int)
    marad=np.maximum(marad,0)
    while kell>0:
        totál=marad.sum()
        probs=marad/totál
        draw=rng.multinomial(kell,probs)
        add=np.minimum(draw,marad)
        sizes+=add
        kell-=int(add.sum())
        marad-=add
    fele ,db =np.unique(sizes,return_counts=True)

    return {int(f):int(d) for f,d in zip(fele,db)}
def k3kiszam_multinom(korelt:list,fiatal:int,felnott:int,kozepes:int,idos:int,min_size:int,seed:1234)->dict:
    fikül=int(round(korelt[0]))
    felkül=int(round(korelt[1]))
    kozkül=int(round(korelt[2]))
    időkül=int(round(korelt[3]))
    if korelt[0]==np.nan or korelt[1]==np.nan or korelt[2]==np.nan or korelt[3]==np.nan:
        raise ValueError("korelt nem lehet NaN.")
    
    rng=np.random.default_rng(seed)
    sizes1=np.full(int(fiatal),min_size,dtype=int)
    sizes2=np.full(int(felnott-fiatal),min_size,dtype=int)
    sizes3=np.full(int(kozepes),min_size,dtype=int)
    sizes4=np.full(int(idos),min_size,dtype=int)
    marad1=np.full(int(fiatal),min_size+fikül,dtype=int)
    marad2=np.full(int(felnott-fiatal),min_size+felkül,dtype=int)
    marad3=np.full(int(kozepes),min_size+kozkül,dtype=int)
    marad4=np.full(int(idos),min_size+időkül,dtype=int)
    while fikül>0:
        totál1=marad1.sum()
        probs1=marad1/totál1
        draw1=rng.multinomial(fikül,probs1)
        add1=np.minimum(draw1,marad1)
        sizes1+=add1
        fikül-=int(add1.sum())
        marad1-=add1
    while felkül>0:
        totál2=marad2.sum()
        probs2=marad2/totál2
        draw2=rng.multinomial(felkül,probs2)
        add2=np.minimum(draw2,marad2)
        sizes2+=add2
        felkül-=int(add2.sum())
        marad2-=add2
    while kozkül>0:
        totál3=marad3.sum()
        probs3=marad3/totál3
        draw3=rng.multinomial(kozkül,probs3)
        add3=np.minimum(draw3,marad3)
        sizes3+=add3
        kozkül-=int(add3.sum())
        marad3-=add3
    while időkül>0:
        totál4=marad4.sum()
        probs4=marad4/totál4
        draw4=rng.multinomial(időkül,probs4)
        add4=np.minimum(draw4,marad4)
        sizes4+=add4
        időkül-=int(add4.sum())
        marad4-=add4
    fele1 ,db1 =np.unique(sizes1,return_counts=True)
    fele2 ,db2 =np.unique(sizes2,return_counts=True)
    fele3 ,db3 =np.unique(sizes3,return_counts=True)
    fele4 ,db4 =np.unique(sizes4,return_counts=True)
    eredmeny={'kor0-14':{int(f): int(d) for f, d in zip(fele1, db1)},
                'kor15-29':{int(f): int(d) for f, d in zip(fele2, db2)},
                'kor30-64':{int(f): int(d) for f, d in zip(fele3, db3)},
                'kor65+':{int(f): int(d) for f, d in zip(fele4, db4)}}
    print(eredmeny)


    return eredmeny
def k3kiszam_multinom2(munkakolt:list,elt:int,inak:int,dolg:int,munkanel:int,min_size:int,seed=1234)->dict:
    etkül=int(round(munkakolt[0]))
    inkül=int(round(munkakolt[1]))
    dolgkül=int(round(munkakolt[2]))
    munkanelkül=int(round(munkakolt[3]))
    print(munkakolt)
    print(elt,inak,dolg,munkanel)
    if munkakolt[0]==np.nan or munkakolt[1]==np.nan or munkakolt[2]==np.nan or munkakolt[3]==np.nan:
        raise ValueError("munkakolt nem lehet NaN.")
    
        
    
    rng=np.random.default_rng(seed)
    sizes1=np.full(int(elt),min_size,dtype=int)
    sizes2=np.full(int(inak),min_size,dtype=int)
    sizes3=np.full(int(dolg),min_size,dtype=int)
    sizes4=np.full(int(munkanel),min_size,dtype=int)
    marad1=np.full(int(elt),min_size+etkül,dtype=int)
    marad2=np.full(int(inak),min_size+inkül,dtype=int)
    marad3=np.full(int(dolg),min_size+dolgkül,dtype=int)
    marad4=np.full(int(munkanel),min_size+munkanelkül,dtype=int)
    while etkül>0:
        totál1=marad1.sum()
        probs1=marad1/totál1
        draw1=rng.multinomial(etkül,probs1)
        add1=np.minimum(draw1,marad1)
        sizes1+=add1
        etkül-=int(add1.sum())
        marad1-=add1
    while inkül>0:
        totál2=marad2.sum()
        probs2=marad2/totál2
        draw2=rng.multinomial(inkül,probs2)
        add2=np.minimum(draw2,marad2)
        sizes2+=add2
        inkül-=int(add2.sum())
        marad2-=add2
    while dolgkül>0:
        totál3=marad3.sum()
        probs3=marad3/totál3
        draw3=rng.multinomial(dolgkül,probs3)
        add3=np.minimum(draw3,marad3)
        sizes3+=add3
        dolgkül-=int(add3.sum())
        marad3-=add3
    while munkanelkül>0:
        totál4=marad4.sum()
        probs4=marad4/totál4
        draw4=rng.multinomial(munkanelkül,probs4)
        add4=np.minimum(draw4,marad4)
        sizes4+=add4
        munkanelkül-=int(add4.sum())
        marad4-=add4
    fele1 ,db1 =np.unique(sizes1,return_counts=True)
    fele2 ,db2 =np.unique(sizes2,return_counts=True)
    fele3 ,db3 =np.unique(sizes3,return_counts=True)
    fele4 ,db4 =np.unique(sizes4,return_counts=True)
    eredmeny={'eltartott':{int(f): int(d) for f, d in zip(fele1, db1)},
                'inak':{int(f): int(d) for f, d in zip(fele2, db2)},
                'dolg':{int(f): int(d) for f, d in zip(fele3, db3)},
                'munkanel':{int(f): int(d) for f, d in zip(fele4, db4)}}
    print(eredmeny)
    return eredmeny


def varhatoeloszlas(row)->pd.DataFrame:
    varos=row["Helység megnevezése"]
    fiatal=row["Nincs 15 évesnél fiatalabb személy a háztartásban"]*0+row["1 személy 15 évesnél fiatalabb a háztartásban"]*1+row["2 személy 15 évesnél fiatalabb a háztartásban"]*2+row["3 vagy több személy 15 évesnél fiatalabb a háztartásban"]*3
    felnott=row["Nincs 30 évesnél fiatalabb személy a háztartásban"]*0+row["1 személy 30 évesnél fiatalabb a háztartásban"]*1+row["2 személy 30 évesnél fiatalabb a háztartásban"]*2+row["3 vagy több személy 30 évesnél fiatalabb a háztartásban"]*3
    kozepes=row["Nincs 30–64 éves személy a háztartásban"]*0+row["1 személy 30–64 éves a háztartásban"]*1+row["2 személy 30–64 éves a háztartásban"]*2+row["3 vagy több személy 30–64 éves a háztartásban"]*3
    idos=row["Nincs 65 éves és idősebb személy a háztartásban"]*0+row["1 személy 65 éves és idősebb a háztartásban"]*1+row["2 személy 65 éves és idősebb a háztartásban"]*2+row["3 vagy több személy 65 éves és idősebb a háztartásban"]*3
    korelt=lakokor(fiatal,felnott,kozepes,idos,varos)
    korval=valoskor(varos)
    k3e=k3kiszam(korelt,row["3 vagy több személy 15 évesnél fiatalabb a háztartásban"],row["3 vagy több személy 30 évesnél fiatalabb a háztartásban"],row["3 vagy több személy 30–64 éves a háztartásban"],row["3 vagy több személy 65 éves és idősebb a háztartásban"])
    dolg=row["Nincs foglalkoztatott a háztartásban"]*0+row["1 foglalkoztatott személy van a háztartásban"]*1+row["2 foglalkoztatott személy van a háztartásban"]*2+row["3 vagy több foglalkoztatott személy van a háztartásban"]*3
    munkanel=row["Nincs munkanélküli személy a háztartásban"]*0+row["1 munkanélküli személy van a háztartásban"]*1+row["2 munkanélküli személy van a háztartásban"]*2+row["3 vagy több munkanélküli személy van a háztartásban"]*3
    inak=row["Nincs ellátásban részesülő inaktív személy a háztartásban"]*0+row["1 ellátásban részesülő inaktív személy van a háztartásban"]*1+row["2 ellátásban részesülő inaktív személy van a háztartásban"]*2+row["3 vagy több ellátásban részesülő inaktív személy van a háztartásban"]*3
    elt=row["Nincs eltartott személy a háztartásban"]*0+row["1 eltartott személy van a háztartásban"]*1+row["2 eltartott személy van a háztartásban"]*2+row["3 vagy több eltartott személy van a háztartásban"]*3
    munkakolt=lakomunka(elt,inak,dolg,munkanel,varos)
    k3m=k3kiszam(munkakolt,row["3 vagy több eltartott személy van a háztartásban"],row["3 vagy több ellátásban részesülő inaktív személy van a háztartásban"],row["3 vagy több foglalkoztatott személy van a háztartásban"],row["3 vagy több munkanélküli személy van a háztartásban"])
    H6Ertek=m6_kiszam_multinom(row["Hat+ személyes háztartás szorzo"],row["6+ személyes háztartás"],6)
    k3ereal= k3kiszam_multinom(korelt,row["3 vagy több személy 15 évesnél fiatalabb a háztartásban"],row["3 vagy több személy 30 évesnél fiatalabb a háztartásban"],row["3 vagy több személy 30–64 éves a háztartásban"],row["3 vagy több személy 65 éves és idősebb a háztartásban"],3,1234)
    #k3wreal= k3kiszam_multinom2(munkakolt,row["3 vagy több eltartott személy van a háztartásban"],row["3 vagy több ellátásban részesülő inaktív személy van a háztartásban"],row["3 vagy több foglalkoztatott személy van a háztartásban"],row["3 vagy több munkanélküli személy van a háztartásban"],3,1234)
    adatok={
        "Lakhely":varos,
        "H1":row["1 személyes háztartás"],
        "H2":row["2 személyes háztartás"],
        "H3":row["3 személyes háztartás"],
        "H4":row["4 személyes háztartás"],
        "H5":row["5 személyes háztartás"],
        "H6":H6Ertek[6]if 6 in H6Ertek else 0,
        "H7":H6Ertek[7]if 7 in H6Ertek else 0,
        "H8":H6Ertek[8]if 8 in H6Ertek else 0,
        "H9":H6Ertek[9]if 9 in H6Ertek else 0,
        "H10":H6Ertek[10]if 10 in H6Ertek else 0,
        "H11":H6Ertek[11]if 11 in H6Ertek else 0,
        "H12":H6Ertek[12]if 12 in H6Ertek else 0,
        "H6+ szorzo":row["Hat+ személyes háztartás szorzo"],
        "Lakott népesség":row["Lakok"],
        "Lakható helyek száma":row["Lakott nepesseg"],
        "Kor0-14":korval[0],
        "Kor15-29":korval[1],
        "Kor30-64":korval[2],
        "Kor65+":korval[3],
        "Kor0-14 0 person":row["Nincs 15 évesnél fiatalabb személy a háztartásban"],
        "Kor0-14 1 person":row["1 személy 15 évesnél fiatalabb a háztartásban"],
        "Kor0-14 2 person":row["2 személy 15 évesnél fiatalabb a háztartásban"],
        "Kor0-14 3+ person":row["3 vagy több személy 15 évesnél fiatalabb a háztartásban"],
        "Kor15-29 0 person":row["Nincs 30 évesnél fiatalabb személy a háztartásban"]-row["Nincs 15 évesnél fiatalabb személy a háztartásban"],
        "Kor15-29 1 person":row["1 személy 30 évesnél fiatalabb a háztartásban"]-row["1 személy 15 évesnél fiatalabb a háztartásban"],
        "Kor15-29 2 person":row["2 személy 30 évesnél fiatalabb a háztartásban"]-row["2 személy 15 évesnél fiatalabb a háztartásban"],
        "Kor15-29 3+ person":row["3 vagy több személy 30 évesnél fiatalabb a háztartásban"]-row["3 vagy több személy 15 évesnél fiatalabb a háztartásban"],
        "Kor30-64 0 person":row["Nincs 30–64 éves személy a háztartásban"],
        "Kor30-64 1 person":row["1 személy 30–64 éves a háztartásban"],
        "Kor30-64 2 person":row["2 személy 30–64 éves a háztartásban"],
        "Kor30-64 3+ person":row["3 vagy több személy 30–64 éves a háztartásban"],
        "Kor65+ 0 person":row["Nincs 65 éves és idősebb személy a háztartásban"],
        "Kor65+ 1 person":row["1 személy 65 éves és idősebb a háztartásban"],
        "Kor65+ 2 person":row["2 személy 65 éves és idősebb a háztartásban"],
        "Kor65+ 3+ person":row["3 vagy több személy 65 éves és idősebb a háztartásban"],
        "K3 Kor0-14":k3e[0],
        "K3 Kor15-29":k3e[1],
        "K3 Kor30-64":k3e[2],
        "K3 Kor65+":k3e[3],
        "Foglalkoztatott":dolg,
        "Munkanélküli":munkanel,
        "Inaktív":inak,
        "Eltartott":elt,
        "Foglalkoztatott 0 person":row["Nincs foglalkoztatott a háztartásban"],
        "Foglalkoztatott 1 person":row["1 foglalkoztatott személy van a háztartásban"],
        "Foglalkoztatott 2 person":row["2 foglalkoztatott személy van a háztartásban"],
        "Foglalkoztatott 3+ person":row["3 vagy több foglalkoztatott személy van a háztartásban"],
        "Munkanélküli 0 person":row["Nincs munkanélküli személy a háztartásban"],
        "Munkanélküli 1 person":row["1 munkanélküli személy van a háztartásban"],
        "Munkanélküli 2 person":row["2 munkanélküli személy van a háztartásban"],
        "Munkanélküli 3+ person":row["3 vagy több munkanélküli személy van a háztartásban"],
        "Inaktív 0 person":row["Nincs ellátásban részesülő inaktív személy a háztartásban"],
        "Inaktív 1 person":row["1 ellátásban részesülő inaktív személy van a háztartásban"],
        "Inaktív 2 person":row["2 ellátásban részesülő inaktív személy van a háztartásban"],
        "Inaktív 3+ person":row["3 vagy több ellátásban részesülő inaktív személy van a háztartásban"],
        "Eltartott 0 person":row["Nincs eltartott személy a háztartásban"],
        "Eltartott 1 person":row["1 eltartott személy van a háztartásban"],
        "Eltartott 2 person":row["2 eltartott személy van a háztartásban"],
        "Eltartott 3+ person":row["3 vagy több eltartott személy van a háztartásban"],
        "K3 Foglalkoztatott":k3m[2],
        "K3 Munkanélküli":k3m[3],
        "K3 Inaktív":k3m[1],
        "K3 Eltartott":k3m[0]
    }
    return adatok


# ---------------------------
# 1) Enumerate age splits per size
# ---------------------------
@lru_cache(maxsize=None)
def enumerate_age_splits(size: int) -> List[Tuple[int,int,int,int]]:
    """
    All 4-tuples (n_<15, n_15-29, n_30-64, n_65+) summing to 'size'.
    Used to express every possible age composition for a given household size.
    """
    out = []
    for a in range(size+1):
        for b in range(size - a + 1):
            for c in range(size - a - b + 1):
                d = size - a - b - c
                out.append((a,b,c,d))
    return out

# ---------------------------
# 2) Fit age templates (IPF-like) to match city-wide age_totals exactly
# ---------------------------
@dataclass
class AgeTemplateFit:
    counts: Dict[Tuple[int, Tuple[int,int,int,int]], int]  # (size, split) -> number of households
    achieved: Dict[str, int]
    log: List[str]

def fit_age_templates(
    H_by_size: Dict[int, int],                 # exact household count per size (incl. expanded 6+)
    age_totals: Dict[str, int],                # disjoint totals: '<15','15-29','30-64','65+'
    max_iter: int = 200,
    tol: float = 1e-6
) -> AgeTemplateFit:
    """
    Builds fractional weights over all (size, age-split) combinations, then normalizes & rounds so that:
      • Sum over splits for each 'size' equals H_by_size[size].
      • Sum over all households & splits equals 'age_totals' exactly (after rounding + tiny correction).
    """
    # Universe of types
    types = []
    for size, Hs in H_by_size.items():
        if Hs <= 0: 
            continue
        for split in enumerate_age_splits(size):
            types.append((size, split))

    if not types:
        raise ValueError("No households to fit (H_by_size is empty).")

    # Global age proportions as a heuristic seed
    T = sum(age_totals.values())
    p = np.array([
        age_totals['<15']/T,
        age_totals['15-29']/T,
        age_totals['30-64']/T,
        age_totals['65+']/T
    ], dtype=float)

    # Seed weights with multinomial likelihood
    w = np.ones(len(types), dtype=float)
    for i, (size, split) in enumerate(types):
        coeff = math.factorial(size)
        for k in split:
            coeff /= math.factorial(k)
        w[i] = max(coeff * np.prod(p ** np.array(split)), 1e-14)

    # Normalize within each size to match H_by_size
    for size, Hs in H_by_size.items():
        idxs = [j for j,(sz,_) in enumerate(types) if sz == size]
        s = w[idxs].sum()
        if s > 0:
            w[idxs] *= (Hs / s)

    # Helper: implied age totals from current weights
    def implied_age(wvec: np.ndarray) -> np.ndarray:
        tot = np.zeros(4, dtype=float)
        for val, (_, split) in zip(wvec, types):
            tot += val * np.array(split, dtype=float)
        return tot

    target_age = np.array([
        age_totals['<15'], age_totals['15-29'], age_totals['30-64'], age_totals['65+']
    ], dtype=float)

    # IPF-like: alternate scaling to match age totals and re-normalize per size
    for _ in range(max_iter):
        cur = implied_age(w)
        if np.allclose(cur, target_age, atol=tol, rtol=0):
            break
        scale = np.divide(target_age, cur, out=np.ones_like(cur), where=(cur>0))
        # distribute scale to each (size,split) proportional to split composition
        new_w = []
        for val, (size, split) in zip(w, types):
            svec = np.array(split, dtype=float)
            if svec.sum() == 0:
                new_w.append(val); continue
            factor = float((svec / svec.sum() * scale).sum())
            new_w.append(val * factor)
        w = np.array(new_w, dtype=float)
        # re-normalize within each size
        for size, Hs in H_by_size.items():
            idxs = [j for j,(sz,_) in enumerate(types) if sz == size]
            s = w[idxs].sum()
            if s > 0:
                w[idxs] *= (Hs / s)

    # Round to integers using largest remainders, size by size
    w_floor = np.floor(w).astype(int)
    remainder = w - w_floor
    counts: Dict[Tuple[int, Tuple[int,int,int,int]], int] = {}
    for i, key in enumerate(types):
        counts[key] = w_floor[i]

    # ensure exact H_by_size per size
    for size, Hs in H_by_size.items():
        idxs = [j for j,(sz,_) in enumerate(types) if sz == size]
        have = int(sum(w_floor[j] for j in idxs))
        deficit =int(Hs - have)
        if deficit > 0:
            order = sorted(idxs, key=lambda j: remainder[j], reverse=True)
            for j in order[:deficit]:
                counts[types[j]] += 1

    # Check achieved age totals after rounding
    ach = np.zeros(4, dtype=int)
    for (size, split), c in counts.items():
        ach += c * np.array(split, dtype=int)
    achieved = {'<15': int(ach[0]), '15-29': int(ach[1]), '30-64': int(ach[2]), '65+': int(ach[3])}

    log = [f"Target ages: {age_totals}", f"Achieved ages: {achieved}"]
    return AgeTemplateFit(counts=counts, achieved=achieved, log=log)

# ---------------------------
# 3) Expand counts to per-household rows (age-only)
# ---------------------------
def expand_age_templates_to_rows(
    lakhely_id: Any,
    counts: Dict[Tuple[int, Tuple[int,int,int,int]], int],
    start_household_id: int = 0
) -> pd.DataFrame:
    """
    Make one row per household with size and the 4 age counts.
    Columns: LakhelyID, HáztartásID, size, n_<15, n_15-29, n_30-64, n_65+
    """
    rows = []
    hid = int(start_household_id)
    for (size, split), c in counts.items():
        for _ in range(int(c)):
            rows.append({
                'LakhelyID': lakhely_id,
                'HáztartásID': hid,
                'size': int(size),
                'n_<15': int(split[0]),
                'n_15-29': int(split[1]),
                'n_30-64': int(split[2]),
                'n_65+': int(split[3]),
            })
            hid += 1
    return pd.DataFrame(rows)

# ---------------------------
# 4) Distribute labour totals over templates (NO 'inactive_other')
# ---------------------------
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
    Allocate city-level labour totals (emp, unemp, inact_benefit, dependent) across households
    respecting per-household capacity:
      • 'emp','unemp','inact_benefit' can only occupy 15+ seats (n_15-29 + n_30-64 + n_65+).
      • 'dependent' can fill any remaining seats; children (<15) are preferred.
    If a working category cannot be fully placed due to capacity limits, the excess is shaved and
    added to 'dependent'. Final per-household labour sums equal 'size' exactly.
    """
    log: List[str] = []
    df = templates.copy()
    df['n_emp'] = 0
    df['n_unemp'] = 0
    df['n_inact_benefit'] = 0
    df['n_dep'] = 0

    pop_total = int(df['size'].sum())
    tgt_emp  = int(labour_totals.get('emp', 0))
    tgt_un   = int(labour_totals.get('unemp', 0))
    tgt_inb  = int(labour_totals.get('inact_benefit', 0))
    # Make 'dependent' the residual to force exact sum
    tgt_dep  = pop_total - (tgt_emp + tgt_un + tgt_inb)
    if 'dependent' in labour_totals and labour_totals['dependent'] != tgt_dep:
        log.append(f"Ignoring provided dependent={labour_totals['dependent']} and using residual {tgt_dep} to match total people.")

    # Capacities
    df['work_cap'] = df[['n_15-29','n_30-64','n_65+']].sum(axis=1)
    df['child_cap'] = df['n_<15']

    def allocate(category: str, target: int, cap_col: str) -> int:
        """
        Proportional integer allocation with cap. Returns actually placed amount.
        """
        if target <= 0:
            return 0
        cap = df[cap_col].to_numpy(dtype=int)
        total_cap = int(cap.sum())
        if total_cap <= 0:
            return 0
        # fractional proposal
        frac = target * (cap / total_cap)
        base = np.floor(frac).astype(int)
        placed = base.copy()
        # Distribute remainder by largest fractional part
        rem = target - int(base.sum())
        if rem > 0:
            order = np.argsort(-(frac - base))
            for j in order[:rem]:
                placed[j] += 1
        # Enforce per-row cap
        placed = np.minimum(placed, cap)
        # Write & reduce capacity
        df[f"n_{category}"] += placed
        df[cap_col] = (df[cap_col] - placed).clip(lower=0)
        return int(placed.sum())

    # Place working categories first (respect 15+ capacity)
    got_emp = allocate('emp', tgt_emp, 'work_cap')
    if got_emp < tgt_emp:
        log.append(f"Shaved emp by {tgt_emp - got_emp} (insufficient 15+ capacity).")
    got_un  = allocate('unemp', tgt_un, 'work_cap')
    if got_un < tgt_un:
        log.append(f"Shaved unemp by {tgt_un - got_un}.")
    got_inb = allocate('inact_benefit', tgt_inb, 'work_cap')
    if got_inb < tgt_inb:
        log.append(f"Shaved inact_benefit by {tgt_inb - got_inb}.")

    # Update dependent target with any shaved amounts
    shave = {'emp': tgt_emp-got_emp, 'unemp': tgt_un-got_un, 'inact_benefit': tgt_inb-got_inb}
    tgt_dep2 = tgt_dep + sum(max(0, v) for v in shave.values())

    # First, seat dependents on children
    got_dep_child = allocate('dep', min(tgt_dep2, int(df['child_cap'].sum())), 'child_cap')
    # Then, seat remaining dependents on any remaining seats (size - placed so far)
    df['leftover'] = df['size'] - df[['n_emp','n_unemp','n_inact_benefit','n_dep']].sum(axis=1)
    got_dep_rest = allocate('dep', tgt_dep2 - got_dep_child, 'leftover')

    # Final safety: fill any residual leftover (if rounding left 1–2 seats) as dependents
    df['leftover'] = df['size'] - df[['n_emp','n_unemp','n_inact_benefit','n_dep']].sum(axis=1)
    if int(df['leftover'].sum()) != 0:
        # place all leftovers as dependents
        allocate('dep', int(df['leftover'].sum()), 'leftover')

    shaved_totals = {k: int(max(0, v)) for k,v in shave.items()}
    return LabourSpread(templates=df.drop(columns=['work_cap','child_cap','leftover']),
                        shaved=shaved_totals, log=log)

# ---------------------------
# 5) High-level builder (one city)
# ---------------------------
@dataclass
class TemplateBuild:
    templates: pd.DataFrame
    logs: List[str]

def build_household_templates_for_city(
    lakhely_id: Any,
    H_by_size: Dict[int,int],
    age_totals: Dict[str,int],
    labour_totals: Dict[str,int],
    start_household_id: int = 0
) -> TemplateBuild:
    """
    Full pipeline to construct the template DataFrame:
      1) Fit age compositions per size to match 'age_totals' exactly.
      2) Expand to one row per household with age split.
      3) Distribute labour totals (no inactive_other), shaving working cats if 15+ capacity is insufficient,
         and placing any residual as 'dependent'. Every row sums exactly to 'size'.
    """
    logs: List[str] = []

    # 1) Fit age splits
    age_fit = fit_age_templates(H_by_size, age_totals)
    logs += [f"[AGE] {m}" for m in age_fit.log]

    # 2) Expand to rows
    tmpl_age = expand_age_templates_to_rows(
        lakhely_id=lakhely_id,
        counts=age_fit.counts,
        start_household_id=start_household_id
    )

    # 3) Spread labour totals (no inactive_other)
    lab = spread_labour_totals_no_inactive(tmpl_age, labour_totals)
    logs += [f"[LAB] {m}" for m in lab.log]
    if any(v>0 for v in lab.shaved.values()):
        logs.append(f"[LAB] Shaved (moved to dependent): {lab.shaved}")

    return TemplateBuild(templates=lab.templates, logs=logs)


# ============================
# ASSIGN PEOPLE TO HOUSEHOLDS
# ============================


# ----------------------------------------------------
# CONFIG: adjust to your schema/labels if needed
# ----------------------------------------------------
DB_PATH        = "populacio.db"
PEOPLE_TABLE   = "Szimulació"        # population table name
CITY_COL       = "LakhelyID"
ID_COL         = "LakosID"
AGE_COL        = "Kor"               # int age or labeled range
LABOUR_COL     = "Munkaviszony"      # employment/status text

TEMPLATES_TABLE = "LakasEpitő"
LINK_TABLE      = "lakasfel_tag"

AGE_BINS = ['<15','15-29','30-64','65+']
LABOUR_CATS = ['emp','unemp','inact_benefit','dependent']  # NO inactive_other

# ----------------------------------------------------
# A) SUPPLY QUEUES (age_bin × labour_cat)
# ----------------------------------------------------

def _age_bin_from_value(v: Any) -> str:
    """Map your age value to the 4 bins."""
    if pd.isna(v):
        return '<15'  # safest default
    # numeric?
    try:
        a = int(v)
        if a < 15:   return '<15'
        if a < 30:   return '15-29'
        if a < 65:   return '30-64'
        return '65+'
    except Exception:
        s = str(v).strip().replace('–','-').replace(' ','')
        if s in ('0-14','0–14','<15'): return '<15'
        if s in ('15-29','15–29'):     return '15-29'
        if s in ('30-64','30–64'):     return '30-64'
        if s in ('65+','65plus'):      return '65+'
        return '30-64'

def _labour_cat_from_value(v: Any, age_bin: str) -> str:
    """Map your labour/status text to 4 categories (Hungarian-ish heuristics)."""
    s = ("" if pd.isna(v) else str(v)).strip().lower()
    if 'foglalk' in s or 'employed' in s:          return 'emp'
    if 'munkanélk' in s or 'munka nelk' in s or 'unemploy' in s: return 'unemp'
    if 'nyugd' in s or 'ellátás' in s or 'benef' in s:           return 'inact_benefit'
    if 'eltartott' in s or 'dependent' in s:       return 'dependent'
    if 'tanul' in s or 'diák' in s or 'student' in s:            return 'dependent'
    # defaults by age:
    if age_bin == '<15': return 'dependent'
    if age_bin == '65+': return 'inact_benefit'
    return 'unemp'

def make_supply_queues(conn: sqlite3.Connection, lakhely_id: Any, chunksize: int = 200_000
) -> Dict[Tuple[str,str], deque[int]]:
    """
    Stream one city's people from SQLite, bin to queues keyed by (age_bin, labour_cat).
    Returns: {(age_bin, labour_cat): deque([LakosID, ...]), ...}
    """
    queues: Dict[Tuple[str,str], deque[int]] = {(a,l): deque() for a in AGE_BINS for l in LABOUR_CATS}
    sql = f'SELECT "{ID_COL}", "{AGE_COL}", "{LABOUR_COL}" FROM {PEOPLE_TABLE} WHERE "{CITY_COL}"=?'
    for chunk in pd.read_sql_query(sql, conn, params=(lakhely_id,), chunksize=chunksize):
        for _, r in chunk.iterrows():
            ageb = _age_bin_from_value(r[AGE_COL])
            lab  = _labour_cat_from_value(r[LABOUR_COL], ageb)
            queues[(ageb, lab)].append(int(r[ID_COL]))
    # deterministic shuffle for fairness
    rnd = random.Random(int(lakhely_id) ^ 0x5A17)
    for key in queues:
        q = list(queues[key])
        rnd.shuffle(q)
        queues[key] = deque(q)
    return queues

# ----------------------------------------------------
# B) ASSIGNER (no 'inactive_other')
# ----------------------------------------------------

# Age eligibility and priorities (tweak if desired)
ELIGIBLE_AGE_FOR = {
    'emp':             ['15-29','30-64','65+'],
    'unemp':           ['15-29','30-64','65+'],
    'inact_benefit':   ['15-29','30-64','65+'],
    'dependent':       ['<15','15-29','30-64','65+'],
}
LABOUR_AGE_PRIORITY = {
    'emp':             ['30-64','15-29','65+'],
    'unemp':           ['15-29','30-64','65+'],
    'inact_benefit':   ['65+','30-64','15-29'],
    'dependent':       ['<15','15-29','30-64','65+'],
}
AGE_FALLBACKS = {
    '<15':   ['15-29','30-64','65+'],
    '15-29': ['30-64','65+'],
    '30-64': ['15-29','65+'],
    '65+':   ['30-64','15-29'],
}

def normalize_labour_targets_to_size(row: pd.Series) -> Tuple[Dict[str,int], List[str]]:
    """
    Make row's labour counts sum EXACTLY to 'size' using only 4 cats:
      - if sum < size, add the gap to 'dependent'
      - if sum > size, reduce in order: dependent → inact_benefit → unemp → emp
    Returns: (fixed_labour_dict, logs)
    """
    logs: List[str] = []
    size = int(row['size'])
    L = {
        'emp':            int(row['n_emp']),
        'unemp':          int(row['n_unemp']),
        'inact_benefit':  int(row['n_inact_benefit']),
        'dependent':      int(row['n_dep']),
    }
    diff = size - sum(L.values())
    if diff > 0:
        L['dependent'] += diff
        logs.append(f"Filled +{diff} into dependent.")
    elif diff < 0:
        over = -diff
        for k in ['dependent','inact_benefit','unemp','emp']:
            if over <= 0: break
            cut = min(L[k], over)
            if cut > 0:
                L[k] -= cut
                over -= cut
                logs.append(f"Reduced {k} by {cut}.")
        if over > 0:
            raise ValueError("Cannot normalize labour to size (negative capacity).")
    return L, logs

def plan_age_lab_allocation_no_inactive(row: pd.Series) -> Tuple[Dict[Tuple[str,str], int], List[str]]:
    """
    Build exact (age_bin, labour_cat) plan for one household row.
    Enforces age split, labour totals (normalized), and age eligibility.
    """
    logs: List[str] = []
    A = {
        '<15':   int(row['n_<15']),
        '15-29': int(row['n_15-29']),
        '30-64': int(row['n_30-64']),
        '65+':   int(row['n_65+']),
    }
    L_in = {
        'emp':            int(row.get('n_emp', 0)),
        'unemp':          int(row.get('n_unemp', 0)),
        'inact_benefit':  int(row.get('n_inact_benefit', 0)),
        'dependent':      int(row.get('n_dep', 0)),
    }
    # ensure sums equal size
    size = int(row['size'])
    if sum(L_in.values()) != size:
        L, llog = normalize_labour_targets_to_size(pd.Series({'size': size, **L_in}))
        logs += llog
    else:
        L = L_in

    alloc: Dict[Tuple[str,str], int] = {}

    # 1) Dependents first to children
    need = L['dependent']
    for age in LABOUR_AGE_PRIORITY['dependent']:
        if need <= 0: break
        take = min(need, A[age])
        if take > 0:
            alloc[(age, 'dependent')] = take
            A[age] -= take
            need -= take
    L['dependent'] = need  # may remain > 0

    # 2) Working cats
    for lab in ['emp','unemp','inact_benefit']:
        need = L[lab]
        if need <= 0: continue
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
            # spill to dependent if not enough 15+ capacity in this household
            logs.append(f"Spilled {L[lab]} from {lab} to dependent (age capacity).")
            L['dependent'] += L[lab]
            L[lab] = 0

    # 3) Place remaining dependents into remaining age slots
    need = L['dependent']
    if need > 0:
        rem = sum(A.values())
        if rem < need:
            logs.append(f"Trim dependent from {need} to {rem} due to age slots.")
            need = rem
        for age in ['<15','15-29','30-64','65+']:
            if need <= 0: break
            if A[age] <= 0: continue
            take = min(need, A[age])
            alloc[(age, 'dependent')] = alloc.get((age, 'dependent'), 0) + take
            A[age] -= take
            need -= take

    return alloc, logs

def _pop_ids_no_inactive(
    queues: Dict[Tuple[str,str], deque],
    age_bin: str,
    lab: str,
    need: int,
    age_fallbacks: Dict[str, List[str]]
) -> List[int]:
    """
    Pull IDs for (age_bin, lab); if short, try age fallbacks same lab,
    then labour fallbacks within same age and across age fallbacks.
    """
    taken: List[int] = []
    # primary
    q = queues.get((age_bin, lab))
    while q and need > 0 and q:
        taken.append(q.popleft()); need -= 1
    if need == 0: return taken

    # same lab, other ages
    for fb_age in age_fallbacks.get(age_bin, []):
        if need == 0: break
        q = queues.get((fb_age, lab))
        while q and need > 0 and q:
            taken.append(q.popleft()); need -= 1
    if need == 0: return taken

    # labour fallback orders
    orders = {
        'emp': ['unemp','inact_benefit','dependent'],
        'unemp': ['inact_benefit','emp','dependent'],
        'inact_benefit': ['unemp','emp','dependent'],
        'dependent': ['inact_benefit','unemp','emp'],
    }
    order = orders.get(lab, ['dependent'])

    # same age, other labour
    for fb_lab in order:
        if need == 0: break
        q = queues.get((age_bin, fb_lab))
        while q and need > 0 and q:
            taken.append(q.popleft()); need -= 1
    if need == 0: return taken

    # other ages, other labour
    for fb_age in age_fallbacks.get(age_bin, []):
        if need == 0: break
        for fb_lab in order:
            if need == 0: break
            q = queues.get((fb_age, fb_lab))
            while q and need > 0 and q:
                taken.append(q.popleft()); need -= 1

    return taken

def assign_people_to_templates_no_inactive(
    templates: pd.DataFrame,
    supply_queues: Dict[Tuple[str,str], deque[int]],
    lakhely_id: int
) -> Tuple[pd.DataFrame, List[str]]:
    """
    For each template household row:
      • plan (age, labour) counts
      • pop that many IDs from queues with controlled fallbacks
    Returns: (assignments DF, logs)
    """
    logs: List[str] = []
    out_rows: List[Dict[str, Any]] = []

    # assign larger households first (more constrained)
    order = np.argsort(-(templates['size'].to_numpy()))
    for idx in order:
        row = templates.iloc[idx]
        hid = int(row['HáztartásID'])
        plan, plogs = plan_age_lab_allocation_no_inactive(row)
        for s in plogs:
            logs.append(f"HZ {hid}: {s}")

        for (age, lab), need in plan.items():
            if need <= 0: continue
            picked = _pop_ids_no_inactive(
                queues=supply_queues,
                age_bin=age,
                lab=lab,
                need=int(need),
                age_fallbacks=AGE_FALLBACKS
            )
            for pid in picked:
                out_rows.append({
                    'LakhelyID': lakhely_id,
                    'HáztartásID': hid,
                    'LakosID': pid,
                    'age_bin': age,
                    'labour_cat': lab
                })
            miss = int(need) - len(picked)
            if miss > 0:
                logs.append(f"City {lakhely_id} HZ {hid}: shortage {miss} for ({age},{lab}).")

    assignments = pd.DataFrame(out_rows)
    return assignments, logs

# ----------------------------------------------------
# C) VALIDATION (quick totals check)
# ----------------------------------------------------

def validate_city(templates: pd.DataFrame, assignments: pd.DataFrame) -> Dict[str, Any]:
    plan_age = {
        '<15':   int(templates['n_<15'].sum()),
        '15-29': int(templates['n_15-29'].sum()),
        '30-64': int(templates['n_30-64'].sum()),
        '65+':   int(templates['n_65+'].sum()),
    }
    asg_age = assignments['age_bin'].value_counts().to_dict()
    for k in plan_age: asg_age[k] = int(asg_age.get(k, 0))

    plan_lab = {
        'emp':            int(templates['n_emp'].sum()),
        'unemp':          int(templates['n_unemp'].sum()),
        'inact_benefit':  int(templates['n_inact_benefit'].sum()),
        'dependent':      int(templates['n_dep'].sum()),
    }
    asg_lab = assignments['labour_cat'].value_counts().to_dict()
    for k in plan_lab: asg_lab[k] = int(asg_lab.get(k, 0))

    return {
        'planned_people': int(templates['size'].sum()),
        'assigned_people': int(len(assignments)),
        'planned_age': plan_age,
        'assigned_age': asg_age,
        'planned_labour': plan_lab,
        'assigned_labour': asg_lab,
    }

# ----------------------------------------------------
# D) PERSISTENCE (SQLite)
# ----------------------------------------------------

def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    # one row per household (template)
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {TEMPLATES_TABLE} (
        LakhelyID    INTEGER NOT NULL,
        HáztartásID  INTEGER NOT NULL UNIQUE,
        size         INTEGER NOT NULL,
        n_<15        INTEGER NOT NULL,
        n_15-29      INTEGER NOT NULL,
        n_30-64      INTEGER NOT NULL,
        n_65+        INTEGER NOT NULL,
        n_emp        INTEGER NOT NULL,
        n_unemp      INTEGER NOT NULL,
        n_inact_benefit INTEGER NOT NULL,
        n_dep        INTEGER NOT NULL
    )""")
    # link: person → household
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {LINK_TABLE} (
        LakhelyID    INTEGER NOT NULL,
        HáztartásID  INTEGER NOT NULL,
        LakosID      INTEGER NOT NULL,
        age_bin      TEXT,
        labour_cat   TEXT,
        RunID        TEXT,
        PRIMARY KEY (LakosID, RunID)
    )""")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_tag_haz ON {LINK_TABLE}(HáztartásID)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_tag_city ON {LINK_TABLE}(LakhelyID)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_pop_city ON {PEOPLE_TABLE}({CITY_COL})")
    conn.commit()

def persist_templates(conn: sqlite3.Connection, templates: pd.DataFrame):
    cols = ['LakhelyID','HáztartásID','size','n_<15','n_15-29','n_30-64','n_65+',
            'n_emp','n_unemp','n_inact_benefit','n_dep']
    templates[cols].to_sql(TEMPLATES_TABLE, conn, if_exists="append", index=False)

def persist_assignments(conn: sqlite3.Connection, assignments: pd.DataFrame, run_id: str):
    df = assignments.copy()
    df['RunID'] = run_id
    df.to_sql(LINK_TABLE, conn, if_exists="append", index=False)

# ----------------------------------------------------
# HIGH-LEVEL helpers
# ----------------------------------------------------

def assign_city(conn: sqlite3.Connection, lakhely_id: int, templates_city: pd.DataFrame):
    queues = make_supply_queues(conn, lakhely_id)
    assignments, logs = assign_people_to_templates_no_inactive(templates_city, queues, lakhely_id)
    return assignments, logs

def process_city(conn: sqlite3.Connection, lakhely_id: int, templates_city: pd.DataFrame, run_id: str):
    """
    End-to-end for ONE city:
      - ensure schema
      - persist templates
      - assign people
      - validate
      - persist links
      Returns: (validation_summary, logs)
    """
    ensure_schema(conn)
    persist_templates(conn, templates_city)
    assignments, logs = assign_city(conn, lakhely_id, templates_city)
    summary = validate_city(templates_city, assignments)
    persist_assignments(conn, assignments, run_id)
    return summary, logs



conn = sqlite3.connect("populacio.db")

# ---- Helper: safe int casting (handles floats/NaN/None) ----
def _as_int(x, default=0):
    try:
        if pd.isna(x):
            return default
        return int(round(float(x)))
    except Exception:
        return default

# ---- Loop cities and build templates ----
all_templates = []     # collect per-city results here
all_logs = []          # optional: collect logs

for index, row in laktab.head(5).iterrows():
    lakhely_id = int(index) + 1
    hely = row.get("Helység megnevezése", lakhely_id)

    vege = varhatoeloszlas(row)   # <-- your function returns a dict
    print(vege)

    # Build H_by_size dynamically from any H1..H12 keys present in vege
    H_by_size = {}
    for k, v in vege.items():
        if isinstance(k, str) and k.startswith("H"):
            try:
                s = int(k[1:])  # size from key like 'H7' -> 7
                H_by_size[s] = _as_int(v, 0)
            except Exception:
                pass

    # If you prefer to cap to 1..12 explicitly, uncomment:
    # H_by_size = {s: _as_int(vege.get(f"H{s}", 0)) for s in range(1, 13)}

    age_totals = {
        '<15':   _as_int(vege.get("Kor0-14", 0)),
        '15-29': _as_int(vege.get("Kor15-29", 0)),
        '30-64': _as_int(vege.get("Kor30-64", 0)),
        '65+':   _as_int(vege.get("Kor65+", 0)),
    }

    labour_totals = {
        'emp':            _as_int(vege.get("Foglalkoztatott", 0)),
        'unemp':          _as_int(vege.get("Munkanélküli", 0)),
        'inact_benefit':  _as_int(vege.get("Inaktív", 0)),     # maps your "Inaktív" to our 'inact_benefit'
        'dependent':      _as_int(vege.get("Eltartott", 0)),
    }

    # Ensure HáztartásID range is unique per city (and per rerun if you repeat)
    start_household_id = lakhely_id * 1_000_000

    try:
        res = build_household_templates_for_city(
            lakhely_id=lakhely_id,
            H_by_size=H_by_size,
            age_totals=age_totals,
            labour_totals=labour_totals,
            start_household_id=start_household_id
        )
    except Exception as e:
        print(f"❌ City {lakhely_id} ({hely}): template build failed -> {e}")
        continue

    # Log a few messages
    print(f"\n✅ City {lakhely_id} ({hely}) — built {len(res.templates)} households")
    for line in res.logs[:10]:
        print("  ", line)

    # Inspect first rows
    print(res.templates.head(20))

    # Collect
    all_templates.append(res.templates.assign(_CityName=str(hely)))
    all_logs.extend([f"[{lakhely_id} {hely}] {m}" for m in res.logs])
    persist_templates(conn, res.templates)  # writes rows to Lakasfeltoltes

    assignments, logs = assign_city(conn, lakhely_id=index + 1, templates_city=res.templates)  # builds lakasfel_tag rows

    # quick sanity print (optional)
    summary = validate_city(res.templates, assignments)
    print(f"\nCity {index+1} ({hely}) – planned {summary['planned_people']} vs assigned {summary['assigned_people']}")

    persist_assignments(conn, assignments, run_id=f"run_city{index+1}_v1")


    


# Concatenate all cities’ templates if needed
templates_all = pd.concat(all_templates, ignore_index=True) if all_templates else pd.DataFrame()
print("\n=== Combined template shape:", templates_all.shape, "===")







data.close()
