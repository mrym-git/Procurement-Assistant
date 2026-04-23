"""One-time script: replace BSON Double NaN in total_price / unit_price with null."""
import math
from pymongo import MongoClient

col = MongoClient()["procurement_db"]["orders"]

def fix_nan(field):
    result = col.update_many(
        {field: {"$type": "double"}},
        [{"$set": {field: {"$cond": {
            "if": {"$and": [
                {"$not": [{"$gte": ["$" + field, 0]}]},
                {"$not": [{"$lte": ["$" + field, 0]}]},
            ]},
            "then": None,
            "else": "$" + field,
        }}}}]
    )
    print(f"{field}: fixed {result.modified_count} NaN values")

fix_nan("total_price")
fix_nan("unit_price")

# Verify: run the quarter spending query
pipeline = [
    {"$match": {"total_price": {"$gt": 0}}},
    {"$group": {
        "_id": {"year": "$year", "quarter": "$quarter"},
        "total": {"$sum": "$total_price"},
    }},
    {"$sort": {"total": -1}},
    {"$limit": 3},
]
print("\nTop 3 quarters by spend:")
for r in col.aggregate(pipeline):
    val = r["total"]
    label = f"{r['_id']['year']}-Q{r['_id']['quarter']}"
    if isinstance(val, float) and math.isnan(val):
        print(f"  {label}: NaN (still broken)")
    else:
        print(f"  {label}: ${val:,.2f}")
