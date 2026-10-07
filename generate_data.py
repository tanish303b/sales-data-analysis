"""Generate data/sales_data.csv - a synthetic sales dataset for a retail store.

The data is simulated (no real customers or shops are involved). It is built to
behave like real store data: weekends and the festive season sell more, some
products are more popular than others, and a few rows are deliberately dirty
(missing values, duplicate rows) so that the analysis has something to clean.

A fixed random seed makes the output identical on every run.
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START_DATE = "2024-01-01"
END_DATE = "2025-12-31"
BASE_ORDERS_PER_DAY = 7
GROWTH_IN_SECOND_YEAR = 1.15

# (product, category, selling price, cost price, popularity weight)
PRODUCTS = [
    ("Basmati Rice 5kg", "Groceries", 650, 520, 9),
    ("Sunflower Oil 1L", "Groceries", 160, 136, 10),
    ("Wheat Flour 10kg", "Groceries", 420, 357, 8),
    ("Tea 500g", "Groceries", 280, 218, 7),
    ("Bluetooth Earbuds", "Electronics", 1499, 1050, 4),
    ("Power Bank 10000mAh", "Electronics", 999, 720, 3),
    ("LED Bulb 9W", "Electronics", 120, 78, 6),
    ("Smart Watch", "Electronics", 2999, 2250, 2),
    ("Men's T-Shirt", "Clothing", 499, 275, 5),
    ("Women's Kurti", "Clothing", 799, 440, 4),
    ("Jeans", "Clothing", 1299, 780, 3),
    ("Kids Wear Set", "Clothing", 599, 345, 3),
    ("Pressure Cooker 3L", "Home & Kitchen", 1450, 1045, 2),
    ("Non-stick Pan", "Home & Kitchen", 899, 610, 2),
    ("Water Bottle 1L", "Home & Kitchen", 299, 170, 5),
    ("Bedsheet Double", "Home & Kitchen", 749, 490, 2),
    ("Shampoo 340ml", "Personal Care", 320, 224, 6),
    ("Face Wash 100ml", "Personal Care", 199, 131, 6),
    ("Toothpaste 150g", "Personal Care", 110, 80, 8),
    ("Body Lotion 400ml", "Personal Care", 375, 255, 4),
    ("Notebook Pack of 6", "Stationery", 240, 156, 5),
    ("Ball Pen Pack of 10", "Stationery", 100, 58, 6),
    ("School Bag", "Stationery", 899, 585, 2),
    ("Geometry Box", "Stationery", 150, 93, 3),
]

# Monday .. Sunday: the store is busiest at the weekend.
WEEKDAY_FACTOR = [0.85, 0.85, 0.90, 0.95, 1.05, 1.35, 1.40]
# January .. December: October-November is the festive season.
MONTH_FACTOR = [1.00, 0.90, 0.95, 1.00, 0.95, 1.05, 0.95, 1.05, 1.00, 1.35, 1.40, 1.15]


def generate() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    days = pd.date_range(START_DATE, END_DATE, freq="D")

    # How many orders each day gets.
    expected = (
        BASE_ORDERS_PER_DAY
        * np.array(WEEKDAY_FACTOR)[days.dayofweek]
        * np.array(MONTH_FACTOR)[days.month - 1]
        * np.where(days.year == days.year.min(), 1.0, GROWTH_IN_SECOND_YEAR)
    )
    orders_per_day = rng.poisson(expected)
    n = int(orders_per_day.sum())

    products = pd.DataFrame(PRODUCTS, columns=["product", "category", "unit_price", "cost_price", "weight"])
    picked = rng.choice(len(products), size=n, p=products["weight"] / products["weight"].sum())
    df = products.drop(columns="weight").iloc[picked].reset_index(drop=True)

    df.insert(0, "order_date", np.repeat(days, orders_per_day))
    df.insert(0, "order_id", [f"ORD{i:05d}" for i in range(1, n + 1)])

    # Cheap items are bought several at a time, expensive ones usually singly.
    cheap = df["unit_price"] < 500
    df["quantity"] = np.where(cheap, rng.integers(1, 6, size=n), rng.integers(1, 3, size=n)).astype(float)
    df["discount_pct"] = rng.choice([0, 5, 10, 15, 20], size=n, p=[0.50, 0.20, 0.15, 0.10, 0.05])
    df["payment_mode"] = rng.choice(["UPI", "Cash", "Card", "Wallet"], size=n, p=[0.45, 0.25, 0.20, 0.10])
    df["customer_type"] = rng.choice(["Returning", "New"], size=n, p=[0.60, 0.40])

    # Make the data a little dirty, like a real export.
    df.loc[rng.choice(n, size=n // 100, replace=False), "payment_mode"] = np.nan
    df.loc[rng.choice(n, size=n // 200, replace=False), "quantity"] = np.nan
    duplicates = df.iloc[rng.choice(n, size=40, replace=False)]
    df = pd.concat([df, duplicates]).sort_values(["order_date", "order_id"], kind="stable")
    return df.reset_index(drop=True)


if __name__ == "__main__":
    out = Path(__file__).parent / "data" / "sales_data.csv"
    out.parent.mkdir(exist_ok=True)
    data = generate()
    data.to_csv(out, index=False, date_format="%Y-%m-%d")
    print(f"Wrote {len(data)} rows to {out}")
