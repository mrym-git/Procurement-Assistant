"""
Clean reload of procurement CSV into MongoDB.
- Strips $ / commas from price columns
- Converts to float with pd.to_numeric(errors='coerce')
- Drops rows where Total Price is NaN or <= 0
- Verifies average Total Price after load
"""
import os
import math
import pandas as pd
import numpy as np
from pymongo import MongoClient, ASCENDING

# ── Find CSV ──────────────────────────────────────────────────────────────────
CACHE = os.path.expanduser(
    r"~\.cache\kagglehub\datasets\sohier\large-purchases-by-the-state-of-ca\versions\1"
)
csv_files = [f for f in os.listdir(CACHE) if f.endswith(".csv")]
DATA_PATH = os.path.join(CACHE, csv_files[0])
print(f"Loading: {DATA_PATH}")

# ── Load ──────────────────────────────────────────────────────────────────────
df = pd.read_csv(DATA_PATH, low_memory=False)
print(f"Raw rows: {len(df):,}")

# ── Step 1: Clean price columns ───────────────────────────────────────────────
for col in ("Total Price", "Unit Price"):
    df[col] = (
        df[col]
        .astype(str)
        .str.replace(r"[\$,\s]", "", regex=True)
        .replace("nan", pd.NA)
        .replace("", pd.NA)
    )
    df[col] = pd.to_numeric(df[col], errors="coerce")

# ── Step 2: Drop rows where Total Price is NaN or <= 0 ────────────────────────
before = len(df)
df = df[df["Total Price"].notna() & (df["Total Price"] > 0)]
print(f"Dropped {before - len(df):,} rows with null/zero/negative Total Price -> {len(df):,} remaining")

# ── Step 3: Standard cleaning ─────────────────────────────────────────────────
df["Creation Date"] = pd.to_datetime(df["Creation Date"], errors="coerce")
df["Purchase Date"] = pd.to_datetime(df["Purchase Date"], errors="coerce")

df["Item Name"] = df["Item Name"].str.lower().str.strip()
for col in df.select_dtypes(include="object").columns:
    df[col] = df[col].str.strip()

df = df.drop_duplicates()
print(f"After dedup: {len(df):,} rows")

# ── Step 4: Rename to snake_case ──────────────────────────────────────────────
df.columns = (
    df.columns.str.strip()
    .str.lower()
    .str.replace(r"[\s\-/]+", "_", regex=True)
    .str.replace(r"[^a-z0-9_]", "", regex=True)
)

# ── Step 5: Normalize names ───────────────────────────────────────────────────
df["supplier_name"]   = df["supplier_name"].str.title()
df["department_name"] = df["department_name"].str.title()

# ── Step 6: Add helper columns ────────────────────────────────────────────────
df["year"]    = df["creation_date"].dt.year.astype("Int64")
df["month"]   = df["creation_date"].dt.month.astype("Int64")
df["quarter"] = df["creation_date"].dt.quarter.astype("Int64")

# ── Step 7: Drop high-null columns ────────────────────────────────────────────
drop_cols = [c for c in [
    "requisition_number", "sub_acquisition_method",
    "sub_acquisition_type", "lpa_number", "supplier_qualifications"
] if c in df.columns]
df = df.drop(columns=drop_cols)

# Fill medium-null columns
for col in ["supplier_zip_code", "location"]:
    if col in df.columns:
        df[col] = df[col].fillna("Unknown")

# ── Step 8: Verify no NaN in total_price before insert ───────────────────────
nan_check = df["total_price"].isna().sum()
inf_check = np.isinf(df["total_price"]).sum()
assert nan_check == 0, f"Still {nan_check} NaN values in total_price!"
assert inf_check == 0, f"Still {inf_check} Inf values in total_price!"
print(f"total_price - NaN: {nan_check}, Inf: {inf_check}  OK clean")
print(f"total_price avg  : ${df['total_price'].mean():,.2f}")
print(f"total_price min  : ${df['total_price'].min():,.2f}")

# ── Step 9: Convert datetime NaT → None for MongoDB ──────────────────────────
clean_df = df.copy()
for col in clean_df.select_dtypes(include="datetime").columns:
    clean_df[col] = clean_df[col].astype(object).where(clean_df[col].notna(), None)

# Convert any remaining NaN in other columns to None
# For numeric columns, use a safe approach that preserves float values
for col in clean_df.columns:
    if clean_df[col].dtype == object:
        clean_df[col] = clean_df[col].where(clean_df[col].notna(), None)
    elif pd.api.types.is_float_dtype(clean_df[col]):
        # Replace NaN with None by converting to object first
        mask = clean_df[col].isna()
        if mask.any():
            clean_df[col] = clean_df[col].astype(object).where(~mask, None)

# ── Step 10: Load into MongoDB ────────────────────────────────────────────────
client = MongoClient("mongodb://localhost:27017/")
col_db = client["procurement_db"]["orders"]

col_db.drop()
print("Dropped existing collection.")

records = clean_df.to_dict(orient="records")
result  = col_db.insert_many(records)
print(f"Inserted {len(result.inserted_ids):,} records into procurement_db.orders")

# ── Step 11: Recreate indexes ─────────────────────────────────────────────────
col_db.create_index([("creation_date",   ASCENDING)], name="idx_creation_date")
col_db.create_index([("supplier_name",   ASCENDING)], name="idx_supplier_name")
col_db.create_index([("total_price",     ASCENDING)], name="idx_total_price")
col_db.create_index([("department_name", ASCENDING)], name="idx_department_name")
col_db.create_index([("year",            ASCENDING)], name="idx_year")
col_db.create_index([("quarter",         ASCENDING)], name="idx_quarter")
col_db.create_index([("year", ASCENDING), ("quarter", ASCENDING)], name="idx_year_quarter")
print("Indexes created.")

# ── Step 12: Final verification ───────────────────────────────────────────────
print("\n=== Post-load verification ===")
sample = list(col_db.aggregate([
    {"$match": {"total_price": {"$gt": 0}}},
    {"$group": {
        "_id": {"year": "$year", "quarter": "$quarter"},
        "total": {"$sum": "$total_price"},
    }},
    {"$sort": {"total": -1}},
    {"$limit": 3},
]))
print("Top 3 quarters by spend:")
for r in sample:
    val = r["total"]
    label = f"{r['_id']['year']}-Q{r['_id']['quarter']}"
    if isinstance(val, float) and math.isnan(val):
        print(f"  {label}: NaN  ← still broken")
    else:
        print(f"  {label}: ${val:,.2f}  OK")

nan_remaining = col_db.count_documents({"total_price": float("nan")})
print(f"\nNaN total_price docs remaining: {nan_remaining}")
client.close()
