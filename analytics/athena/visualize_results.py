import csv
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "evidence" / "athena"
OUTPUT = RESULTS / "charts"
OUTPUT.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT = 1000, 600
LEFT, RIGHT, TOP, BOTTOM = 100, 40, 80, 100


def read_csv(filename):
    with (RESULTS / filename).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def money(value):
    return f"${float(value):,.2f}"


def svg_text(x, y, text, size=16, anchor="middle", weight="normal"):
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-family="Arial, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="#222">'
        f'{escape(str(text))}</text>'
    )


def save_bar_chart(filename, title, labels, values, value_label,
                   horizontal=False, value_formatter=None):
    if not labels:
        raise ValueError(f"No data available for {filename}")

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        svg_text(WIDTH / 2, 38, title, 23, weight="bold"),
        svg_text(WIDTH / 2, 65, value_label, 14),
    ]

    plot_w = WIDTH - LEFT - RIGHT
    plot_h = HEIGHT - TOP - BOTTOM
    max_val = max(float(v) for v in values) or 1
    formatter = value_formatter or (lambda v: f"{v:,.0f}")

    if horizontal:
        row_h = plot_h / len(labels)
        label_space = 250
        bar_space = plot_w - label_space
        for i, (label, raw) in enumerate(zip(labels, values)):
            val = float(raw)
            y = TOP + i * row_h
            bar_w = bar_space * val / max_val
            parts.append(svg_text(LEFT + label_space - 12, y + row_h * .62,
                                  label, 13, anchor="end"))
            parts.append(
                f'<rect x="{LEFT + label_space}" y="{y + row_h * .2}" '
                f'width="{max(0, bar_w)}" height="{row_h * .55}" '
                f'fill="#3977a8"/>'
            )
            parts.append(svg_text(LEFT + label_space + bar_w + 8,
                                  y + row_h * .62, formatter(val), 12,
                                  anchor="start"))
    else:
        slot = plot_w / len(labels)
        for i, (label, raw) in enumerate(zip(labels, values)):
            val = float(raw)
            bar_h = plot_h * val / max_val
            x = LEFT + i * slot + slot * .18
            y = TOP + plot_h - bar_h
            parts.append(
                f'<rect x="{x}" y="{y}" width="{slot * .64}" '
                f'height="{bar_h}" fill="#3977a8"/>'
            )
            parts.append(svg_text(x + slot * .32, y - 10,
                                  formatter(val), 12))
            parts.append(svg_text(x + slot * .32, TOP + plot_h + 25,
                                  label, 12))

    parts.append(
        f'<line x1="{LEFT}" y1="{TOP + plot_h}" '
        f'x2="{WIDTH - RIGHT}" y2="{TOP + plot_h}" '
        f'stroke="#444" stroke-width="1"/>'
    )
    parts.append('</svg>')
    (OUTPUT / filename).write_text("\n".join(parts), encoding="utf-8")
    print(f"Created: {OUTPUT / filename}")


def main():
    # 1. Sales by source
    rows = read_csv("01_sales_by_source_results.csv")
    save_bar_chart(
        "01_sales_by_source.svg",
        "Sales by Source",
        [r["source_system"].upper() for r in rows],
        [r["total_sales"] for r in rows],
        "Total sales (CAD)",
        value_formatter=money,
    )

    # 2. Sales by region
    rows = read_csv("02_sales_by_region_results.csv")
    save_bar_chart(
        "02_sales_by_region.svg",
        "Sales by Region",
        [r["region"] for r in rows],
        [r["total_sales"] for r in rows],
        "Total sales (CAD)",
        value_formatter=money,
    )

    # 3. Top 10 products
    rows = read_csv("03_top_products_results.csv")
    save_bar_chart(
        "03_top_products.svg",
        "Top 10 Products by Sales",
        [r["product_name"] for r in rows],
        [r["total_sales"] for r in rows],
        "Total sales (CAD)",
        horizontal=True,
        value_formatter=money,
    )

    # 4. Sales by category and channel
    rows = read_csv("04_sales_by_category_channel_results.csv")
    save_bar_chart(
        "04_sales_by_category_channel.svg",
        "Sales by Category and Channel",
        [f'{r["category"]} / {r["channel"]}' for r in rows],
        [r["total_sales"] for r in rows],
        "Total sales (CAD)",
        value_formatter=money,
    )

    # 5. Daily sales
    rows = read_csv("05_sales_by_day_results.csv")
    save_bar_chart(
        "05_sales_by_day.svg",
        "Daily Sales",
        [r["sale_date"] for r in rows],
        [r["total_sales"] for r in rows],
        "Total sales (CAD)",
        value_formatter=money,
    )


if __name__ == "__main__":
    main()
