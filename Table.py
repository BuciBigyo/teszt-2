import sqlite3
import pandas as pd
from typing import Optional

class tablakezelo:
    def __init__(self, db_path: str,table_name:str):
        """db_path: path to your SQLite file, e.g. 'my_database.db'"""
        self.db_path = db_path
        self.table_name=table_name
        self.conn=sqlite3.connect(self.db_path)


    def create_table(self):
        """
        Create the population table if it doesn't exist already.
        Columns: City, AgeRange, Gender
        """
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            Lakhely TEXT NOT NULL,
            LakhelyID text not null,
            LakosID text not null,
            Nem TEXT NOT NULL,
            Kor TEXT NOT NULL,
            Oktatás TEXT NOT NULL,
            Kapcsolat TEXT NOT NULL,
            Munkaviszony Text NOT NULL
        );
        """
        self.conn.execute(query)
        self.conn.commit()
        print(f"✅ Table '{self.table_name}' ready in {self.db_path}")
    def create_lakasfel_table(self, table_name: Optional[str] = None):
        """
        Create the housing/household table 'lakasfel' (or a custom name) if it doesn't exist.
        Columns match your DataFrame:
          LakhelyID, LakásID, HáztartásID, Lakszemélyekszáma, Háztartástípus
        """
        tname = table_name or self.table_name
        query = f"""
        CREATE TABLE IF NOT EXISTS {tname} (
            LakhelyID           TEXT NOT NULL,
            LakásID             TEXT NOT NULL,
            HáztartásID         TEXT NOT NULL,
            Lakszemélyekszáma   INTEGER NOT NULL,
            Háztartástípus      TEXT,
            PRIMARY KEY (HáztartásID)
        );
        """
        self.conn.execute(query)
        # Helpful indexes
        self.conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tname}_LakhelyID ON {tname}(LakhelyID);")
        self.conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tname}_LakasID   ON {tname}(LakásID);")
        self.conn.commit()
        print(f"✅ Table '{tname}' ready in {self.db_path}")

    def insert_lakasfel(self, lakasfel_df: pd.DataFrame, table_name: Optional[str] = None, replace: bool = False, chunk: int = 100_000):
        """
        Bulk insert a lakasfel DataFrame.
        - If replace=True, uses INSERT OR REPLACE (overwrites by primary key 'HáztartásID').
        - Inserts in chunks to keep memory reasonable.
        """
        tname = table_name or self.table_name

        # Ensure required columns exist and cast to expected dtypes
        required = ["LakhelyID", "LakásID", "HáztartásID", "Lakszemélyekszáma", "Háztartástípus"]
        missing = [c for c in required if c not in lakasfel_df.columns]
        if missing:
            raise ValueError(f"Missing required columns in DataFrame: {missing}")

        df = lakasfel_df.copy()

        # Casts (align with table schema)
        df["LakhelyID"] = df["LakhelyID"].astype(str)
        df["LakásID"] = df["LakásID"].astype(str)
        df["HáztartásID"] = df["HáztartásID"].astype(str)
        df["Lakszemélyekszáma"] = pd.to_numeric(df["Lakszemélyekszáma"], errors="coerce").fillna(0).astype(int)
        # allow NULL for type if missing
        if "Háztartástípus" in df.columns:
            df["Háztartástípus"] = df["Háztartástípus"].astype(object)

        op = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
        sql = f"""
        {op} INTO {tname}
        (LakhelyID, LakásID, HáztartásID, Lakszemélyekszáma, Háztartástípus)
        VALUES (?, ?, ?, ?, ?)
        """

        # Chunked executemany inside a single transaction for speed
        cur = self.conn.cursor()
        try:
            self.conn.execute("BEGIN;")
            for start in range(0, len(df), chunk):
                part = df.iloc[start:start+chunk]
                cur.executemany(
                    sql,
                    list(zip(
                        part["LakhelyID"].tolist(),
                        part["LakásID"].tolist(),
                        part["HáztartásID"].tolist(),
                        part["Lakszemélyekszáma"].tolist(),
                        part["Háztartástípus"].where(part["Háztartástípus"].notna(), None).tolist(),
                    ))
                )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise
        finally:
            cur.close()

        print(f"📤 Inserted {len(df)} rows into '{tname}'")

    def insert_dataframe(self, df: pd.DataFrame,név:str):
        """
        Insert a DataFrame into the database.
        Expects columns: City, AgeRange, Gender, Marital status, Job status
        """
        required_cols = {"Lakhely", "Nem", "Kor","Oktatás","Kapcsolat","Munkaviszony"}
        if not required_cols.issubset(df.columns):
            raise ValueError(f"DataFrame must contain columns: {required_cols}")

        df.to_sql(self.table_name, self.conn, if_exists="append", index=False)
        print(f"✅ Inserted {len(df)} people from '{név}'")


    def create_table_lekhely(self, table_name: str = "lakhelyek"):
        """
        Create a separate table for storing schooling ratios.
        """
        query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            HazID TEXT,
            LakoID text
        );
        """
        self.conn.execute(query)
        self.conn.commit()
        print(f"✅ Ratio table '{table_name}' ready in {self.db_path}")





    def create_ratio_table(self, ratio_table_name: str = "school_ratios"):
        """
        Create a separate table for storing schooling ratios.
        """
        query = f"""
        CREATE TABLE IF NOT EXISTS {ratio_table_name} (
            Nem TEXT,
            Korcsoport TEXT,
            Megye TEXT,
            TelepulesTipus TEXT,
            IskolaTípus TEXT,
            Lakossag REAL,
            Osszes REAL,
            Arany REAL
        );
        """
        self.conn.execute(query)
        self.conn.commit()
        print(f"✅ Ratio table '{ratio_table_name}' ready in {self.db_path}")

    def insert_ratios(self, df: pd.DataFrame, ratio_table_name: str = "school_ratios"):
        """
        Insert the ratio DataFrame into the database.
        If table exists, replaces it completely.
        """
        df.to_sql(ratio_table_name, self.conn, if_exists="replace", index=False)
        self.conn.commit()
        print(f"✅ Inserted {len(df)} ratio rows into '{ratio_table_name}'")

    def get_ratios(self, nem: str, kor: str, megye: str, tipus: str,
                ratio_table_name: str = "school_ratios") -> dict:
        """
        Query schooling ratios for a given demographic group.
        Returns a dict: {IskolaTípus: Arany, ...}
        """
        kor = kor.replace('-', '–') 
        if kor=="0–5 éves":
            return {"6 év alatti": 1.0}
        query = f"""
        SELECT IskolaTípus, Arany
        FROM {ratio_table_name}
        WHERE Nem = ?
        AND Korcsoport = ?
        AND Megye = ?
        AND TelepulesTipus = ?
        """
        df = pd.read_sql_query(query, self.conn, params=[nem, kor, megye, tipus])
        if df.empty:
            return {}
        return dict(zip(df["IskolaTípus"], df["Arany"]))

    def create_ratio_index(self, ratio_table_name: str = "school_ratios"):
        """
        Add indexes for faster ratio queries.
        """
        query = f"""
        CREATE INDEX IF NOT EXISTS idx_ratios_demographics
        ON {ratio_table_name} (Nem, Korcsoport, Megye, TelepulesTipus)
        """
        self.conn.execute(query)
        self.conn.commit()
        print(f"⚡ Index added to '{ratio_table_name}' for faster querying.")











    def query(self, sql: str) -> pd.DataFrame:
        """
        Run a SQL query and return results as a DataFrame.
        """
        return pd.read_sql_query(sql, self.conn)

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def reset_table(self):
        """Drop the table and recreate it empty."""
        self.conn.execute(f"DROP TABLE IF EXISTS {self.table_name}")
        self.conn.commit()
        self.create_table()
        print(f"🗑️ Table '{self.table_name}' reset.")

