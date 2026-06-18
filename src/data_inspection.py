import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = PROJECT_ROOT / "food_wastage.db"


def create_database():
    # Load raw CSVs (data already clean: 0 nulls, 1000 rows each)
    providers = pd.read_csv(DATA_DIR / "providers_data.csv")
    receivers = pd.read_csv(DATA_DIR / "receivers_data.csv")
    food_listings = pd.read_csv(DATA_DIR / "food_listings_data.csv")
    claims = pd.read_csv(DATA_DIR / "claims_data.csv")

    # Parse date columns to proper datetime (enables SQL date filters, comparisons, strftime later)
    food_listings["Expiry_Date"] = pd.to_datetime(
        food_listings["Expiry_Date"], format="%m/%d/%Y", errors="coerce"
    )
    claims["Timestamp"] = pd.to_datetime(
        claims["Timestamp"], format="%m/%d/%Y %H:%M", errors="coerce"
    )

    engine = create_engine(f"sqlite:///{DB_PATH.resolve()}")
    conn = engine.connect()
    conn.execute(text("PRAGMA foreign_keys = ON;"))

    # Drop in dependency order for clean reloads during development
    conn.execute(text("DROP TABLE IF EXISTS claims"))
    conn.execute(text("DROP TABLE IF EXISTS food_listings"))
    conn.execute(text("DROP TABLE IF EXISTS receivers"))
    conn.execute(text("DROP TABLE IF EXISTS providers"))

    # Explicit schema: types + PK + FK for integrity, query planner hints, and future CRUD safety
    conn.execute(
        text("""
        CREATE TABLE providers (
            Provider_ID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL,
            Type TEXT,
            Address TEXT,
            City TEXT,
            Contact TEXT
        )
    """)
    )
    conn.execute(
        text("""
        CREATE TABLE receivers (
            Receiver_ID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL,
            Type TEXT,
            City TEXT,
            Contact TEXT
        )
    """)
    )
    conn.execute(
        text("""
        CREATE TABLE food_listings (
            Food_ID INTEGER PRIMARY KEY,
            Food_Name TEXT NOT NULL,
            Quantity INTEGER,
            Expiry_Date DATE,
            Provider_ID INTEGER,
            Provider_Type TEXT,
            Location TEXT,
            Food_Type TEXT,
            Meal_Type TEXT,
            FOREIGN KEY (Provider_ID) REFERENCES providers(Provider_ID)
        )
    """)
    )
    conn.execute(
        text("""
        CREATE TABLE claims (
            Claim_ID INTEGER PRIMARY KEY,
            Food_ID INTEGER,
            Receiver_ID INTEGER,
            Status TEXT,
            Timestamp DATETIME,
            FOREIGN KEY (Food_ID) REFERENCES food_listings(Food_ID),
            FOREIGN KEY (Receiver_ID) REFERENCES receivers(Receiver_ID)
        )
    """)
    )

    # Indexes on filter/join columns used by the 15 queries and Streamlit filters (city, type, status, expiry, meal)
    conn.execute(text("CREATE INDEX idx_providers_city ON providers(City)"))
    conn.execute(text("CREATE INDEX idx_food_location ON food_listings(Location)"))
    conn.execute(text("CREATE INDEX idx_food_type ON food_listings(Food_Type)"))
    conn.execute(text("CREATE INDEX idx_food_meal ON food_listings(Meal_Type)"))
    conn.execute(text("CREATE INDEX idx_claim_status ON claims(Status)"))
    conn.execute(text("CREATE INDEX idx_claim_food ON claims(Food_ID)"))
    conn.execute(text("CREATE INDEX idx_claim_receiver ON claims(Receiver_ID)"))

    # Load data (append after explicit CREATE so FKs and types are enforced)
    providers.to_sql("providers", engine, if_exists="append", index=False)
    receivers.to_sql("receivers", engine, if_exists="append", index=False)
    food_listings.to_sql("food_listings", engine, if_exists="append", index=False)
    claims.to_sql("claims", engine, if_exists="append", index=False)

    # Verification counts (must match 1000 each)
    for tbl in ["providers", "receivers", "food_listings", "claims"]:
        cnt = pd.read_sql(f"SELECT COUNT(*) as c FROM {tbl}", engine).iloc[0, 0]
        print(f"{tbl}: {cnt} rows loaded")

    print(f"\nDatabase created at: {DB_PATH.resolve()}")
    conn.close()


if __name__ == "__main__":
    create_database()
