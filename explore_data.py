import pandas as pd
import numpy as np

CSV_PATH = r"C:\Users\SP7\Downloads\archive (1)\PURCHASE ORDER DATA EXTRACT 2012-2015_0.csv"

# ── Load ──────────────────────────────────────────────────────────────────────
print("Loading CSV…")
df = pd.read_csv(CSV_PATH, low_memory=False)

print("\n" + "="*70)
print("1. BASIC INFO")
print("="*70)

print(f"\nTotal rows    : {len(df):,}")
print(f"Total columns : {len(df.columns)}")

print("\n--- Column names & dtypes ---")
for col in df.columns:
    print(f"  {col:<50} {str(df[col].dtype)}")

print("\n--- Sample (5 rows) ---")
print(df.head(5).to_string())

print("\n" + "="*70)
print("2. DATA QUALITY")
print("="*70)

# Missing values
missing = df.isnull().sum()
missing = missing[missing > 0].sort_values(ascending=False)
print("\n--- Missing values ---")
if missing.empty:
    print("  No missing values found.")
else:
    for col, count in missing.items():
        pct = count / len(df) * 100
        print(f"  {col:<50} {count:>8,}  ({pct:.1f}%)")

# Duplicates
dups = df.duplicated().sum()
print(f"\n--- Duplicate rows ---")
print(f"  {dups:,} duplicate rows ({dups/len(df)*100:.2f}%)")

# Date columns detection
print("\n--- Date columns & formats ---")
date_cols = []
for col in df.columns:
    if df[col].dtype == object:
        sample = df[col].dropna().head(100)
        try:
            parsed = pd.to_datetime(sample, infer_datetime_format=True, errors='coerce')
            if parsed.notna().sum() > 80:
                date_cols.append(col)
                print(f"  {col:<50} sample value: {df[col].dropna().iloc[0]}")
        except Exception:
            pass
if not date_cols:
    print("  No date columns detected.")

# Numeric stored as string?
print("\n--- Numeric columns stored as strings? ---")
for col in df.columns:
    if df[col].dtype == object:
        sample = df[col].dropna().head(200).str.replace(r'[\$,]', '', regex=True)
        try:
            converted = pd.to_numeric(sample, errors='coerce')
            ratio = converted.notna().sum() / len(sample)
            if ratio > 0.8:
                print(f"  '{col}' looks numeric but stored as string (dtype: {df[col].dtype})")
        except Exception:
            pass

print("\n" + "="*70)
print("3. KEY INSIGHTS")
print("="*70)

# Date range
print("\n--- Date range ---")
for col in date_cols:
    parsed = pd.to_datetime(df[col], infer_datetime_format=True, errors='coerce')
    print(f"  {col}: {parsed.min().date()} → {parsed.max().date()}")

# Unique departments
dept_candidates = [c for c in df.columns if 'dept' in c.lower() or 'department' in c.lower()]
print("\n--- Unique departments ---")
if dept_candidates:
    for col in dept_candidates:
        print(f"  '{col}': {df[col].nunique():,} unique values")
        print("  Top 5:", df[col].value_counts().head(5).to_dict())
else:
    print("  No department column detected.")

# Unique suppliers
supplier_candidates = [c for c in df.columns if any(k in c.lower() for k in ['supplier', 'vendor', 'contractor', 'company'])]
print("\n--- Unique suppliers ---")
if supplier_candidates:
    for col in supplier_candidates:
        print(f"  '{col}': {df[col].nunique():,} unique values")
        print("  Top 5:", df[col].value_counts().head(5).to_dict())
else:
    print("  No supplier column detected.")

# Total spending
print("\n--- Total spending ---")
amount_candidates = [c for c in df.columns if any(k in c.lower() for k in ['amount', 'price', 'cost', 'total', 'spend', 'value'])]
for col in amount_candidates:
    series = df[col]
    if series.dtype == object:
        series = pd.to_numeric(series.str.replace(r'[\$,]', '', regex=True), errors='coerce')
    total = series.sum()
    print(f"  '{col}': ${total:,.2f}  (non-null: {series.notna().sum():,})")

print("\n" + "="*70)
print("4. ANALYSIS FOR SPECIFIC QUERY TYPES")
print("="*70)

# Orders in time period
print("\n--- Order date column ---")
if date_cols:
    for col in date_cols:
        print(f"  Column: '{col}'")
        print(f"  Sample values: {df[col].dropna().head(5).tolist()}")
        parsed = pd.to_datetime(df[col], infer_datetime_format=True, errors='coerce')
        print(f"  Parsed format: YYYY-MM-DD (pandas inferred)")
        print(f"  Monthly counts (top 5):")
        monthly = parsed.dt.to_period('M').value_counts().sort_index()
        print(monthly.tail(5).to_string())
else:
    print("  No date column found.")

# Quarter with highest spending
print("\n--- Quarter with highest spending ---")
if date_cols and amount_candidates:
    date_col = date_cols[0]
    amount_col = amount_candidates[0]
    parsed_dates = pd.to_datetime(df[date_col], infer_datetime_format=True, errors='coerce')
    amounts = df[amount_col]
    if amounts.dtype == object:
        amounts = pd.to_numeric(amounts.str.replace(r'[\$,]', '', regex=True), errors='coerce')
    tmp = pd.DataFrame({'date': parsed_dates, 'amount': amounts})
    tmp['quarter'] = tmp['date'].dt.to_period('Q')
    quarterly = tmp.groupby('quarter')['amount'].sum().sort_values(ascending=False)
    print(f"  Date column used  : '{date_col}'")
    print(f"  Amount column used: '{amount_col}'")
    print(f"  Quarter derived via: date.dt.to_period('Q')")
    print("\n  Top 5 quarters by spending:")
    print(quarterly.head(5).apply(lambda x: f"${x:,.2f}").to_string())
else:
    print("  Insufficient columns for this analysis.")

# Most frequently ordered line items
print("\n--- Most frequently ordered line items ---")
item_candidates = [c for c in df.columns if any(k in c.lower() for k in ['item', 'description', 'product', 'commodity', 'line'])]
qty_candidates  = [c for c in df.columns if any(k in c.lower() for k in ['qty', 'quantity', 'units'])]
if item_candidates:
    for col in item_candidates[:2]:
        print(f"  Column: '{col}'")
        print("  Top 10 most frequent:")
        print(df[col].value_counts().head(10).to_string())
else:
    print("  No item/description column detected.")
print(f"\n  Quantity column: {qty_candidates[0] if qty_candidates else 'Not found'}")
if qty_candidates:
    q = df[qty_candidates[0]]
    if q.dtype == object:
        q = pd.to_numeric(q.str.replace(r'[\$,]', '', regex=True), errors='coerce')
    print(f"  Total quantity ordered: {q.sum():,.0f}")

# Filtering/grouping columns
print("\n--- Columns suitable for filtering & grouping ---")
groupable = [c for c in df.columns if df[c].dtype == object and 2 <= df[c].nunique() <= 500]
for col in groupable:
    print(f"  '{col}': {df[col].nunique()} unique values")

print("\n" + "="*70)
print("5. RECOMMENDATIONS")
print("="*70)

print("\n--- Cleaning needed before loading to MongoDB ---")
print("  1. Strip '$' and ',' from monetary columns and cast to float.")
print("  2. Parse date columns to datetime and store as ISO strings or ISODate.")
if dups > 0:
    print(f"  3. Drop {dups:,} duplicate rows.")
if not missing.empty:
    print(f"  4. Decide how to handle nulls in: {list(missing.index)}")
print("  5. Normalize column names: lowercase, replace spaces with underscores.")
print("  6. Strip leading/trailing whitespace from string columns.")

print("\n--- Most important columns ---")
important = date_cols + dept_candidates + supplier_candidates + amount_candidates + item_candidates[:1] + qty_candidates[:1]
seen = []
for c in important:
    if c not in seen:
        seen.append(c)
        print(f"  - {c}")

print("\n--- Potential issues ---")
for col in amount_candidates:
    if df[col].dtype == object:
        print(f"  ! '{col}' is a string — must be cleaned before numeric aggregation.")
for col in date_cols:
    parsed = pd.to_datetime(df[col], infer_datetime_format=True, errors='coerce')
    null_dates = parsed.isna().sum()
    if null_dates > 0:
        print(f"  ! '{col}' has {null_dates:,} unparseable date values.")
if dups > 0:
    print(f"  ! {dups:,} duplicate rows may skew aggregations.")
mixed = [c for c in df.columns if df[c].dtype == object and df[c].str.strip().eq('').sum() > 0]
if mixed:
    print(f"  ! Columns with blank strings (not NaN): {mixed}")

print("\nDone.")
