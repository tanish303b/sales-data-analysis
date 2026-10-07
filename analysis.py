"""Sales data analysis of a commercial store.

Loads data/sales_data.csv, cleans it, calculates the key business numbers and
saves the charts to charts/ and a text report to output/summary.txt.

Run:  python analysis.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to image files, no window needed
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

BASE = Path(__file__).parent
DATA_FILE = BASE / "data" / "sales_data.csv"
CHART_DIR = BASE / "charts"
OUTPUT_DIR = BASE / "output"

# Chart colours
BLUE = "#2a78d6"
ORANGE = "#eb6834"
GREY = "#c3c2b7"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SOFT = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ------------------------------------------------------------------ data preparation

def load_data(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["order_date"])


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remove duplicate rows, handle missing values and fix column types."""
    df = raw.drop_duplicates()
    report = {
        "rows_raw": len(raw),
        "duplicates_removed": len(raw) - len(df),
        "missing_quantity_dropped": int(df["quantity"].isna().sum()),
        "missing_payment_filled": int(df["payment_mode"].isna().sum()),
    }
    # Without a quantity the sale amount cannot be calculated, so those rows are dropped.
    df = df.dropna(subset=["quantity"]).copy()
    df["quantity"] = df["quantity"].astype(int)
    # A missing payment mode does not affect the amounts, so the row is kept.
    df["payment_mode"] = df["payment_mode"].fillna("Unknown")
    report["rows_clean"] = len(df)
    return df, report


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add the calculated columns used by the analysis."""
    df = df.copy()
    df["revenue"] = df["unit_price"] * df["quantity"] * (1 - df["discount_pct"] / 100)
    df["cost"] = df["cost_price"] * df["quantity"]
    df["profit"] = df["revenue"] - df["cost"]
    df["year"] = df["order_date"].dt.year
    df["month"] = df["order_date"].dt.month
    df["year_month"] = df["order_date"].dt.to_period("M")
    df["weekday"] = pd.Categorical(df["order_date"].dt.day_name(), categories=WEEKDAYS, ordered=True)
    return df


# ------------------------------------------------------------------ analysis

def analyse(df: pd.DataFrame) -> dict:
    """Calculate every table and number that the report and the charts use."""
    revenue = df["revenue"].sum()
    profit = df["profit"].sum()

    monthly = df.groupby("year_month")["revenue"].sum()
    yearly = df.groupby("year")[["revenue", "profit"]].sum()
    by_year_month = df.pivot_table(index="month", columns="year", values="revenue", aggfunc="sum")

    category = df.groupby("category")[["revenue", "profit"]].sum().sort_values("revenue", ascending=False)
    category["revenue_share_pct"] = category["revenue"] / revenue * 100
    category["margin_pct"] = category["profit"] / category["revenue"] * 100

    products = (
        df.groupby("product")
        .agg(revenue=("revenue", "sum"), units=("quantity", "sum"), profit=("profit", "sum"))
        .sort_values("revenue", ascending=False)
    )

    # Average revenue of one Monday, one Tuesday, ... (total per day first, then the mean).
    daily = df.groupby(["order_date", "weekday"], observed=True)["revenue"].sum().reset_index()
    weekday = daily.groupby("weekday", observed=False)["revenue"].mean()

    payment = df.groupby("payment_mode")["revenue"].agg(["sum", "count"])
    payment["revenue_share_pct"] = payment["sum"] / revenue * 100
    payment = payment.sort_values("revenue_share_pct", ascending=False)

    discount = df.groupby("discount_pct").agg(
        orders=("order_id", "count"), revenue=("revenue", "sum"), profit=("profit", "sum"),
        avg_quantity=("quantity", "mean"))
    discount["margin_pct"] = discount["profit"] / discount["revenue"] * 100

    customer = df.groupby("customer_type")["revenue"].agg(["sum", "count", "mean"])

    return {
        "revenue": revenue,
        "profit": profit,
        "margin_pct": profit / revenue * 100,
        "orders": len(df),
        "units": int(df["quantity"].sum()),
        "avg_order_value": df["revenue"].mean(),
        "monthly": monthly,
        "yearly": yearly,
        "by_year_month": by_year_month,
        "category": category,
        "products": products,
        "weekday": weekday,
        "payment": payment,
        "discount": discount,
        "customer": customer,
    }


def build_summary(clean_report: dict, r: dict) -> str:
    """Write the findings as plain text."""
    monthly, yearly, category = r["monthly"], r["yearly"], r["category"]
    weekday, products, discount = r["weekday"], r["products"], r["discount"]
    years = list(yearly.index)
    growth = (yearly["revenue"].iloc[-1] / yearly["revenue"].iloc[0] - 1) * 100
    weekend = weekday[["Saturday", "Sunday"]].mean()
    working_days = weekday[WEEKDAYS[:5]].mean()
    festive = monthly[monthly.index.month.isin([10, 11])].sum()
    top3_share = products["revenue"].head(3).sum() / r["revenue"] * 100
    returning = r["customer"].loc["Returning"]

    lines = [
        "SALES DATA ANALYSIS - SUMMARY",
        "=" * 60,
        "",
        "DATA CLEANING",
        f"  Rows in raw file            : {clean_report['rows_raw']:,}",
        f"  Duplicate rows removed      : {clean_report['duplicates_removed']:,}",
        f"  Rows dropped (no quantity)  : {clean_report['missing_quantity_dropped']:,}",
        f"  Payment mode filled 'Unknown': {clean_report['missing_payment_filled']:,}",
        f"  Rows used for analysis      : {clean_report['rows_clean']:,}",
        "",
        "KEY NUMBERS",
        f"  Period                      : {monthly.index[0]} to {monthly.index[-1]}",
        f"  Total revenue               : Rs. {r['revenue']:,.0f}",
        f"  Total profit                : Rs. {r['profit']:,.0f}",
        f"  Profit margin               : {r['margin_pct']:.1f}%",
        f"  Orders                      : {r['orders']:,}",
        f"  Units sold                  : {r['units']:,}",
        f"  Average order value         : Rs. {r['avg_order_value']:,.0f}",
        "",
        "INSIGHTS",
        f"  1. Revenue grew {growth:.1f}% from {years[0]} (Rs. {yearly['revenue'].iloc[0]:,.0f}) "
        f"to {years[-1]} (Rs. {yearly['revenue'].iloc[-1]:,.0f}).",
        f"  2. Best month: {monthly.idxmax()} (Rs. {monthly.max():,.0f}). "
        f"Weakest month: {monthly.idxmin()} (Rs. {monthly.min():,.0f}).",
        f"  3. October and November together bring {festive / r['revenue'] * 100:.1f}% of all revenue "
        f"(2 of 12 months = 16.7% if sales were even).",
        f"  4. An average weekend day earns Rs. {weekend:,.0f} against Rs. {working_days:,.0f} on a "
        f"working day ({(weekend / working_days - 1) * 100:.0f}% more).",
        f"  5. Top category: {category.index[0]} with {category['revenue_share_pct'].iloc[0]:.1f}% of revenue. "
        f"Highest margin: {category['margin_pct'].idxmax()} ({category['margin_pct'].max():.1f}%). "
        f"Lowest margin: {category['margin_pct'].idxmin()} ({category['margin_pct'].min():.1f}%).",
        f"  6. Top product: {products.index[0]} (Rs. {products['revenue'].iloc[0]:,.0f}). "
        f"The top 3 products bring {top3_share:.1f}% of revenue.",
        f"  7. Profit margin falls from {discount['margin_pct'].iloc[0]:.1f}% with no discount to "
        f"{discount['margin_pct'].iloc[-1]:.1f}% at a {discount.index[-1]}% discount, while the average "
        f"quantity per order stays about the same ({discount['avg_quantity'].iloc[0]:.2f} vs "
        f"{discount['avg_quantity'].iloc[-1]:.2f}).",
        f"  8. Returning customers place {returning['count'] / r['orders'] * 100:.1f}% of the orders.",
        f"  9. Most used payment mode: {r['payment'].index[0]} "
        f"({r['payment']['revenue_share_pct'].iloc[0]:.1f}% of revenue).",
        "",
        "REVENUE BY CATEGORY",
        category.round(1).to_string(),
        "",
        "TOP 10 PRODUCTS BY REVENUE",
        products.head(10).round(0).to_string(),
        "",
        "PROFIT MARGIN BY DISCOUNT LEVEL",
        discount.round(2).to_string(),
        "",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------ charts

def set_chart_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "savefig.dpi": 150,
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans"],
        "font.size": 10,
        "text.color": INK,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 26,
        "axes.labelcolor": INK_SOFT,
        "axes.edgecolor": GREY,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK_SOFT,
        "ytick.labelcolor": INK_SOFT,
        "lines.linewidth": 2,
        "legend.frameon": False,
    })


def lakh(value: float) -> str:
    """Format rupees in lakhs: 1234567 -> '₹12.3 L'."""
    return f"₹{value / 1e5:.1f} L"


def subtitle(ax, text: str) -> None:
    ax.text(0, 1.02, text, transform=ax.transAxes, color=INK_SOFT, fontsize=9.5, va="bottom")


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(CHART_DIR / name)
    plt.close(fig)


def horizontal_bars(values: pd.Series, labels: list[str], title: str, sub: str, name: str) -> None:
    """Horizontal bar chart, largest bar on top, with the value written at each bar end."""
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(values) + 1.6))
    bars = ax.barh(values.index[::-1], values.values[::-1], height=0.45, color=BLUE)
    for bar, label in zip(bars, labels[::-1]):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, "  " + label,
                va="center", ha="left", color=INK_SOFT, fontsize=9)
    ax.set_xlim(0, values.max() * 1.22)
    ax.set_title(title)
    subtitle(ax, sub)
    # Every bar carries its value, so the x axis and grid would only repeat it.
    ax.grid(False)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    save(fig, name)


def value_columns(ax, bars, labels: list[str]) -> None:
    """Write the value above each column and hide the y axis, which would only repeat it."""
    for bar, label in zip(bars, labels):
        ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()), xytext=(0, 4),
                    textcoords="offset points", ha="center", va="bottom", color=INK_SOFT, fontsize=9)
    ax.set_ylim(0, max(bar.get_height() for bar in bars) * 1.15)
    ax.yaxis.set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.grid(False)
    ax.tick_params(axis="x", length=0)


def chart_monthly_trend(monthly: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = range(len(monthly))
    ax.plot(x, monthly.values, color=BLUE, marker="o", markersize=4)
    ax.fill_between(x, monthly.values, color=BLUE, alpha=0.10)

    peak = int(monthly.values.argmax())
    ax.annotate(f"{monthly.index[peak].strftime('%b %Y')}: {lakh(monthly.iloc[peak])}",
                xy=(peak, monthly.iloc[peak]), xytext=(0, 9), textcoords="offset points",
                ha="center", color=INK, fontsize=9)

    ticks = [i for i in x if monthly.index[i].month in (1, 4, 7, 10)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([monthly.index[i].strftime("%b\n%Y") for i in ticks])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: lakh(v)))
    ax.set_ylim(0, monthly.max() * 1.18)
    ax.grid(axis="x", visible=False)
    ax.set_title("Monthly revenue")
    subtitle(ax, "Revenue per month over the whole period; the highest month is labelled")
    save(fig, "01_monthly_revenue_trend.png")


def chart_year_comparison(by_year_month: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for year, colour in zip(by_year_month.columns, [BLUE, ORANGE]):
        values = by_year_month[year]
        ax.plot(MONTHS, values.values, color=colour, marker="o", markersize=4, label=str(year))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: lakh(v)))
    ax.set_ylim(0, by_year_month.max().max() * 1.15)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", ncol=2)
    ax.set_title("Revenue by month, year on year")
    subtitle(ax, "The same months of both years side by side")
    save(fig, "02_year_on_year.png")


def chart_weekday(weekday: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    colours = [BLUE if day in ("Saturday", "Sunday") else GREY for day in weekday.index]
    bars = ax.bar([day[:3] for day in weekday.index], weekday.values, width=0.4, color=colours)
    value_columns(ax, bars, [f"₹{v:,.0f}" for v in weekday.values])
    ax.set_title("Average revenue per day of the week")
    subtitle(ax, "Weekend days are highlighted in blue")
    save(fig, "05_revenue_by_weekday.png")


def chart_discount_margin(discount: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar([f"{d}%" for d in discount.index], discount["margin_pct"].values, width=0.4, color=BLUE)
    value_columns(ax, bars, [f"{v:.1f}%" for v in discount["margin_pct"].values])
    ax.set_xlabel("Discount given on the order")
    ax.set_title("Profit margin at each discount level")
    subtitle(ax, "Profit as a share of revenue")
    save(fig, "07_margin_by_discount.png")


def make_charts(r: dict) -> None:
    set_chart_style()
    CHART_DIR.mkdir(exist_ok=True)

    chart_monthly_trend(r["monthly"])
    chart_year_comparison(r["by_year_month"])

    category = r["category"]
    horizontal_bars(
        category["revenue"],
        [f"{lakh(v)}  ({s:.0f}%)" for v, s in zip(category["revenue"], category["revenue_share_pct"])],
        "Revenue by category", "Total revenue and share of all revenue", "03_revenue_by_category.png")

    top = r["products"]["revenue"].head(10)
    horizontal_bars(top, [lakh(v) for v in top],
                    "Top 10 products by revenue", "Total revenue over the whole period",
                    "04_top_10_products.png")

    chart_weekday(r["weekday"])

    payment = r["payment"]["revenue_share_pct"]
    horizontal_bars(payment, [f"{v:.1f}%" for v in payment],
                    "Revenue share by payment mode", "Share of total revenue", "06_payment_modes.png")

    chart_discount_margin(r["discount"])


# ------------------------------------------------------------------ main

def main() -> None:
    raw = load_data(DATA_FILE)
    df, clean_report = clean_data(raw)
    df = add_features(df)
    results = analyse(df)

    summary = build_summary(clean_report, results)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary)

    make_charts(results)
    print(f"Charts saved to {CHART_DIR}")
    print(f"Summary saved to {OUTPUT_DIR / 'summary.txt'}")


if __name__ == "__main__":
    main()
