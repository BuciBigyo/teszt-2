import sqlite3
import pandas as pd

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

