"""Local retail sales dashboard. Run with: python app.py"""

from __future__ import annotations

import math
import html
import random
import sqlite3
import threading
import webbrowser
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DATABASE_PATH = ROOT / "retail_forecast.sqlite3"
HOST = "127.0.0.1"
PORT = 8000
DATASET_VERSION = "synthetic-inr-2013-2025-v1"
DEPARTMENT_NAMES = {
    1: "Clothing", 2: "Sports & Outdoors", 3: "Home & Kitchen",
    4: "Electronics", 5: "Grocery", 6: "Health & Beauty",
    7: "Toys & Games", 8: "Seasonal & Garden",
}
STORE_NAMES = {
    1: "Mumbai Central", 2: "Delhi Connaught Place", 3: "Bengaluru Indiranagar",
    4: "Chennai T. Nagar", 5: "Hyderabad Banjara Hills", 6: "Kolkata Salt Lake",
    7: "Pune Camp", 8: "Ahmedabad CG Road", 9: "Jaipur MI Road",
    10: "Kochi Marine Drive", 11: "Lucknow Hazratganj", 12: "Chandigarh Sector 17",
}

ALLOWED_FIELDS = {
    "day", "month", "year", "store", "dept", "type", "weekly_sales", "size",
    "is_holiday", "temperature", "fuel_price", "markdown1", "markdown2",
    "markdown3", "markdown4", "markdown5", "cpi", "unemployment",
}


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def generate_synthetic_sales(connection: sqlite3.Connection) -> int:
    """Seed a compact, repeatable synthetic INR dataset for 2013–2025."""
    generator = random.Random(20251123)
    insert_sql = "insert into sales values (" + ",".join("?" for _ in range(18)) + ")"
    rows = []
    for year in range(2013, 2026):
        current = date(year, 1, 1)
        while current.weekday() != 4:
            current += timedelta(days=1)
        week_number = 0
        while current.year == year:
            week_number += 1
            holiday = int((current.month == 11 and current.day >= 20) or
                          (current.month == 12 and current.day >= 20))
            seasonal_factor = 1 + 0.14 * math.sin(2 * math.pi * (week_number - 10) / 52)
            for store in range(1, 13):
                store_type = (store - 1) % 3 + 1
                size = 28000 + store * 2700
                store_factor = 0.84 + store * 0.027
                for department in range(1, 9):
                    department_factor = 0.76 + department * 0.075
                    holiday_factor = 1.13 if holiday else 1.0
                    year_factor = 1 + (year - 2013) * 0.008
                    weekly_sales = round(
                        (4200 + department * 850) * store_factor * department_factor
                        * seasonal_factor * holiday_factor * year_factor
                        * generator.uniform(0.91, 1.09), 2
                    )
                    temperature = round(42 + 24 * math.sin(2 * math.pi * (week_number - 12) / 52)
                                        + store * 0.35 + generator.uniform(-3, 3), 2)
                    fuel_price = round(1.7 + (year - 2013) * 0.035 + generator.uniform(-0.08, 0.08), 2)
                    cpi = round(135 + (year - 2013) * 2.1 + generator.uniform(-1.5, 1.5), 3)
                    unemployment = round(max(3.2, 7.1 - (year - 2013) * 0.17
                                              + generator.uniform(-0.25, 0.25)), 3)
                    rows.append((current.day, current.month, year, store, department,
                                 store_type, weekly_sales, size, holiday, temperature, fuel_price,
                                 None, None, None, None, None, cpi, unemployment))
            current += timedelta(days=7)
    connection.executemany(insert_sql, rows)
    return len(rows)


def ensure_database() -> int:
    connection = connect_db()
    connection.execute("""create table if not exists sales(
        day integer, month integer, year integer, store integer, dept integer,
        type integer, weekly_sales real, size integer, is_holiday integer,
        temperature real, fuel_price real, markdown1 real, markdown2 real,
        markdown3 real, markdown4 real, markdown5 real, cpi real,
        unemployment real
    )""")
    connection.execute("create table if not exists app_metadata (key text primary key, value text)")
    version = connection.execute("select value from app_metadata where key = 'dataset_version'").fetchone()
    try:
        if not version or version[0] != DATASET_VERSION:
            connection.execute("delete from sales")
            generate_synthetic_sales(connection)
            connection.execute(
                "insert or replace into app_metadata(key,value) values('dataset_version',?)",
                (DATASET_VERSION,),
            )
        connection.execute(
            "create index if not exists idx_sales_date_store_dept "
            "on sales(year, month, day, store, dept)"
        )
        connection.commit()
    except Exception:
        connection.rollback()
        connection.close()
        raise
    count = connection.execute("select count(*) from sales").fetchone()[0]
    connection.close()
    return count


def query_all(sql: str, values=()) -> list[sqlite3.Row]:
    connection = connect_db()
    try:
        return connection.execute(sql, values).fetchall()
    finally:
        connection.close()


def query_one(sql: str, values=()):
    connection = connect_db()
    try:
        return connection.execute(sql, values).fetchone()
    finally:
        connection.close()


def options_for(field: str, where: str = "", values=()) -> list[int]:
    if field not in ALLOWED_FIELDS:
        raise ValueError("Unknown filter field")
    sql = f"select distinct {field} from sales"
    if where:
        sql += f" where {where}"
    sql += f" order by {field}"
    return [row[0] for row in query_all(sql, values) if row[0] is not None]


def selected_int(params: dict, name: str, options: list[int], fallback=None):
    raw = params.get(name, [""])[0]
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = fallback
    if value not in options:
        value = options[0] if options else None
    return value


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def department_name(value) -> str:
    try:
        department = int(value)
    except (TypeError, ValueError):
        return str(value)
    return DEPARTMENT_NAMES.get(department, f"Department {department}")


def store_name(value) -> str:
    try:
        store = int(value)
    except (TypeError, ValueError):
        return str(value)
    name = STORE_NAMES.get(store)
    return f"{name} · Store {store}" if name else f"Store {store}"


def money(value) -> str:
    amount = int(round(float(value or 0)))
    sign = "-" if amount < 0 else ""
    digits = str(abs(amount))
    if len(digits) > 3:
        prefix, last_three = digits[:-3], digits[-3:]
        groups = []
        while prefix:
            groups.insert(0, prefix[-2:])
            prefix = prefix[:-2]
        digits = ",".join(groups + [last_three])
    return f"₹{sign}{digits}"


def select_control(label: str, name: str, choices: list, selected=None) -> str:
    safe_label = esc(label)
    pieces = [f'<label class="filter"><span>{safe_label}</span>',
              f'<select name="{esc(name)}" onchange="this.form.requestSubmit()">']
    for value in choices:
        is_selected = " selected" if value == selected else ""
        if name == "store" and isinstance(value, int):
            display_value = store_name(value)
        elif name == "dept" and isinstance(value, int):
            display_value = department_name(value)
        else:
            display_value = value
        pieces.append(f'<option value="{esc(value)}"{is_selected}>{esc(display_value)}</option>')
    pieces.extend(["</select>", "</label>"])
    return "".join(pieces)


def filter_bar(page: str, params: dict, include_store=True, include_department=True) -> str:
    years = options_for("year")
    year = selected_int(params, "year", years, 2010)
    months = options_for("month", "year = ?", (year,)) if year else []
    month = selected_int(params, "month", months, 2)
    days = options_for("day", "year = ? and month = ?", (year, month)) if month else []
    day = selected_int(params, "day", days, 5)
    stores = options_for("store", "year = ? and month = ? and day = ?", (year, month, day))
    departments = options_for("dept", "year = ? and month = ? and day = ?", (year, month, day))
    store_raw = params.get("store", ["All stores"])[0]
    dept_raw = params.get("dept", ["All departments"])[0]
    store_selected = int(store_raw) if store_raw.isdigit() and int(store_raw) in stores else "All stores"
    dept_selected = int(dept_raw) if dept_raw.isdigit() and int(dept_raw) in departments else "All departments"
    parts = [f'<form class="filters" method="get"><input type="hidden" name="page" value="{esc(page)}">',
             select_control("Year", "year", years, year),
             select_control("Month", "month", months, month),
             select_control("Week", "day", days, day)]
    if include_store:
        parts.append(select_control("Store", "store", ["All stores", *stores], store_selected))
    if include_department:
        parts.append(select_control("Department", "dept", ["All departments", *departments], dept_selected))
    parts.append('<button class="button" type="submit">Apply filters</button>')
    parts.append(f'<a class="button button-quiet" href="/?page={esc(page)}">Clear filters</a></form>')
    return "".join(parts)


def date_filter(params: dict) -> tuple[int | None, int | None, int | None]:
    years = options_for("year")
    year = selected_int(params, "year", years, 2010)
    months = options_for("month", "year = ?", (year,)) if year else []
    month = selected_int(params, "month", months, 2)
    days = options_for("day", "year = ? and month = ?", (year, month)) if month else []
    day = selected_int(params, "day", days, 5)
    return year, month, day


def ranking(rows: list[sqlite3.Row], name: str, value_name="weekly_sales") -> str:
    if not rows:
        return '<p class="empty">No sales were found for those filters.</p>'
    maximum = max(abs(float(row[value_name] or 0)) for row in rows) or 1
    output = ['<div class="rank-list">']
    for row in rows:
        label = row[name]
        if name == "store":
            label = store_name(label)
        elif name == "dept":
            label = department_name(label)
        amount = float(row[value_name] or 0)
        width = max(2, min(100, abs(amount) / maximum * 100))
        output.append(
            '<div class="rank-row">'
            f'<div class="rank-label">{esc(label)}</div>'
            f'<div class="track"><div class="fill" style="width:{width:.1f}%"></div></div>'
            f'<strong>{money(amount)}</strong></div>'
        )
    output.append("</div>")
    return "".join(output)


def overview(params: dict) -> str:
    year, month, day = date_filter(params)
    if year is None:
        return '<p class="empty">The sales dataset has no available records.</p>'
    store_selection = params.get("store", ["All stores"])[0]
    dept_selection = params.get("dept", ["All departments"])[0]
    store = int(store_selection) if store_selection.isdigit() else None
    dept = int(dept_selection) if dept_selection.isdigit() else None

    where = "year = ? and month = ? and day = ?"
    values = [year, month, day]
    if dept is not None:
        where += " and dept = ?"
        values.append(dept)
    if store is not None:
        where += " and store = ?"
        values.append(store)
    top_stores = query_all(
        f"select store, sum(weekly_sales) weekly_sales from sales where {where} "
        "group by store order by weekly_sales desc limit 10", values)
    where = "year = ? and month = ? and day = ?"
    values = [year, month, day]
    if store is not None:
        where += " and store = ?"
        values.append(store)
    if dept is not None:
        where += " and dept = ?"
        values.append(dept)
    top_departments = query_all(
        f"select dept, sum(weekly_sales) weekly_sales from sales where {where} "
        "group by dept order by weekly_sales desc limit 10", values)
    where = "year = ? and month = ? and day = ?"
    values = [year, month, day]
    if store is not None:
        where += " and store = ?"
        values.append(store)
    if dept is not None:
        where += " and dept = ?"
        values.append(dept)
    total = query_one(
        f"select sum(weekly_sales) total, count(distinct store) stores "
        f"from sales where {where}", values)

    return (
        filter_bar("overview", params)
        + '<section class="metric-grid">'
        + f'<div class="metric"><span>Total weekly sales</span><strong>{money(total["total"])}</strong></div>'
        + f'<div class="metric"><span>Stores reporting</span><strong>{total["stores"] or 0}</strong></div>'
        + f'<div class="metric"><span>Selected week</span><strong>{month:02d}/{day:02d}/{year}</strong></div>'
        + '</section><section class="panel-grid">'
        + '<article class="panel"><div class="panel-heading"><h2>Top stores</h2>'
        + '<span>By weekly sales</span></div>' + ranking(top_stores, "store") + '</article>'
        + '<article class="panel"><div class="panel-heading"><h2>Top departments</h2>'
        + '<span>By weekly sales</span></div>' + ranking(top_departments, "dept") + '</article>'
        + '</section>'
    )


def comparison(params: dict) -> str:
    year, month, day = date_filter(params)
    if year is None:
        return '<p class="empty">The sales dataset has no available records.</p>'
    rows = query_all(
        "select store, sum(weekly_sales) weekly_sales from sales "
        "where year = ? and month = ? and day = ? group by store order by weekly_sales desc",
        (year, month, day))
    best = rows[:10]
    lowest = list(reversed(rows[-10:]))
    return (
        filter_bar("comparison", params, include_store=False, include_department=False)
        + '<section class="panel-grid">'
        + '<article class="panel"><div class="panel-heading"><h2>Highest sales</h2>'
        + '<span>Top stores for the selected week</span></div>' + ranking(best, "store") + '</article>'
        + '<article class="panel"><div class="panel-heading"><h2>Lowest sales</h2>'
        + '<span>Stores with the lowest weekly totals</span></div>' + ranking(lowest, "store") + '</article>'
        + '</section>'
    )


def features(params: dict) -> str:
    year, month, day = date_filter(params)
    if year is None:
        return '<p class="empty">The sales dataset has no available records.</p>'
    type_rows = query_all(
        "select type, avg(weekly_sales) weekly_sales from sales "
        "where year = ? and month = ? and day = ? group by type order by type",
        (year, month, day))
    holiday_rows = query_all(
        "select case when is_holiday = 1 then 'Holiday week' else 'Regular week' end label, "
        "avg(weekly_sales) weekly_sales from sales where year = ? and month = ? and day = ? "
        "group by is_holiday order by is_holiday", (year, month, day))
    size_rows = query_all(
        "select case when size < 100000 then 'Small' when size < 150000 then 'Medium' "
        "else 'Large' end label, avg(weekly_sales) weekly_sales from sales "
        "where year = ? and month = ? and day = ? group by label "
        "order by avg(weekly_sales) desc", (year, month, day))

    def simple_table(rows, first_column, heading):
        body = "".join(f'<tr><td>{esc(row[first_column])}</td><td>{money(row["weekly_sales"])}</td></tr>'
                       for row in rows)
        return (f'<article class="panel"><h2>{heading}</h2><table><thead><tr>'
                f'<th>{heading.rsplit(" ", 1)[-1]}</th><th>Average sales</th></tr></thead>'
                f'<tbody>{body}</tbody></table></article>')

    return (
        filter_bar("features", params, include_store=False, include_department=False)
        + '<section class="panel-grid">'
        + simple_table(type_rows, "type", "Average sales by store type")
        + simple_table(holiday_rows, "label", "Average sales by holiday")
        + simple_table(size_rows, "label", "Average sales by store size")
        + '</section>'
    )


def data_overview() -> str:
    stats = query_one("select count(*) records, min(year) first_year, max(year) last_year, "
                      "count(distinct store) stores, count(distinct dept) departments from sales")
    return (
        '<section class="metric-grid">'
        f'<div class="metric"><span>Sales records</span><strong>{stats["records"]:,}</strong></div>'
        f'<div class="metric"><span>Years covered</span><strong>{stats["first_year"]}–{stats["last_year"]}</strong></div>'
        f'<div class="metric"><span>Stores</span><strong>{stats["stores"]}</strong></div>'
        f'<div class="metric"><span>Departments</span><strong>{stats["departments"]}</strong></div>'
        '</section><article class="panel source-panel"><h2>Local data source</h2>'
        '<p>Sales data is generated locally as synthetic weekly records from 2013 through 2025. '
        'All sales amounts are originally generated in Indian rupees.</p>'
        f'<p class="path">Database file: <code>{esc(DATABASE_PATH.name)}</code></p></article>'
    )


def forecast_page(params: dict) -> str:
    stores = options_for("store")
    if not stores:
        return '<p class="empty">The sales dataset has no available records.</p>'
    raw_store = params.get("store", [""])[0]
    store = selected_int(params, "store", stores, stores[0])
    departments = options_for("dept", "store = ?", (store,))
    if not departments:
        return '<p class="empty">No departments are available for this store.</p>'
    department = selected_int(params, "dept", departments, departments[0])
    controls = (
        '<form class="filters" method="get"><input type="hidden" name="page" value="forecast">'
        + select_control("Store", "store", stores, store)
        + select_control("Department", "dept", departments, department)
        + '<button class="button" type="submit">Update estimate</button>'
        + '<a class="button button-quiet" href="/?page=forecast">Clear filters</a></form>'
    )
    history = query_all(
        "select year, month, day, weekly_sales from sales "
        "where store = ? and dept = ? order by year desc, month desc, day desc limit 4",
        (store, department),
    )
    if not history:
        return controls + '<p class="empty">No recent sales are available for this selection.</p>'

    average_sales = sum(float(row["weekly_sales"] or 0) for row in history) / len(history)
    history_rows = "".join(
        f'<tr><td>{int(row["year"]):04d}-{int(row["month"]):02d}-{int(row["day"]):02d}</td>'
        f'<td>{money(row["weekly_sales"])}</td></tr>'
        for row in history
    )
    return (
        controls
        + '<section class="forecast-result"><div class="forecast-kicker">FOUR-WEEK BASELINE</div>'
        + f'<div class="forecast-value">{money(average_sales)}</div>'
        + f'<p>Estimated weekly sales for {esc(store_name(store))}, '
        + f'{esc(department_name(department))}, '
        + f'based on {len(history)} most recent available weeks.</p>'
        + '<p class="forecast-method">This is a historical average, not a trained machine-learning forecast.</p></section>'
        + '<article class="panel history-panel"><div class="panel-heading"><h2>Recent sales history</h2>'
        + '<span>Used for the baseline estimate</span></div><table><thead><tr><th>Week</th>'
        + '<th>Weekly sales</th></tr></thead><tbody>' + history_rows + '</tbody></table></article>'
    )


def about_page() -> str:
    stats = query_one(
        "select count(*) records, min(year) first_year, max(year) last_year, "
        "count(distinct store) stores, count(distinct dept) departments from sales"
    )
    return (
        '<section class="metric-grid">'
        + f'<div class="metric"><span>Sales records</span><strong>{stats["records"]:,}</strong></div>'
        + f'<div class="metric"><span>Years covered</span><strong>{stats["first_year"]}–{stats["last_year"]}</strong></div>'
        + f'<div class="metric"><span>Stores</span><strong>{stats["stores"]}</strong></div>'
        + '</section><section class="panel-grid">'
        + '<article class="panel"><h2>What this dashboard does</h2>'
        + '<p>Explore weekly sales rankings, compare store performance, and review how store type, '
        + 'holiday weeks, and store size relate to sales.</p></article>'
        + '<article class="panel"><h2>Data and storage</h2>'
        + '<p>The dashboard creates repeatable synthetic weekly data from 2013 through 2025 and '
        + 'stores it locally in SQLite. Branch names are illustrative labels for the sample stores.</p></article>'
        + '<article class="panel"><h2>Currency and forecast</h2>'
        + '<p>Sales values are generated directly in Indian rupees; no currency conversion is '
        + 'applied. Forecasts use a simple average of the selected store and '
        + 'department’s four most recent available weeks.</p></article>'
        + '</section>'
    )


PAGES = {
    "overview": ("Sales overview", "Rank stores and departments for a selected week.", overview),
    "comparison": ("Store comparison", "Compare the strongest and weakest weekly store totals.", comparison),
    "features": ("Feature analysis", "Explore weekly sales across store and holiday attributes.", features),
    "data": ("Data overview", "A summary of the local sales data behind the dashboard.", data_overview),
    "forecast": ("Sales forecast", "Estimate weekly sales from a store’s recent history.", forecast_page),
    "about": ("About", "Learn about the dataset, currency display, and forecast method.", about_page),
}


def render_page(page_key: str, params: dict) -> bytes:
    if page_key not in PAGES:
        page_key = "overview"
    title, description, renderer = PAGES[page_key]
    nav_items = [("data", "Data overview"), ("overview", "Sales overview"),
                 ("comparison", "Store comparison"), ("features", "Feature analysis"),
                 ("forecast", "Sales forecast"), ("about", "About")]
    nav = "".join(
        f'<a class="nav-link{" active" if key == page_key else ""}" href="/?page={key}">{label}</a>'
        for key, label in nav_items
    )
    body = renderer(params) if page_key in {"overview", "comparison", "features", "forecast"} else renderer()
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Retail Sales Analytics</title>
<style>
:root {{ color-scheme: dark; --ink:#CDCBCA; --muted:#A7A5A4; --crimson:#D41514; --crimson-dark:#790B0B; --line:#342727; --surface:#111010; --canvas:#080808; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; min-height:100vh; background:radial-gradient(circle at 96% 0%,#1b0808 0,transparent 23%),var(--canvas); color:var(--ink); font:15px/1.5 "Segoe UI",Arial,sans-serif; }}
.shell {{ min-height:100vh; }}
.topbar {{ min-height:84px; display:flex; align-items:center; justify-content:space-between; gap:24px; padding:14px clamp(18px,5vw,76px); border-bottom:1px solid var(--line); background:rgba(8,8,8,.94); }}
.brand {{ display:flex; align-items:center; gap:12px; color:#CDCBCA; text-decoration:none; white-space:nowrap; }}
.brand-mark {{ width:39px; height:39px; display:grid; place-items:center; border:2px solid var(--crimson); border-radius:50% 50% 50% 12px; color:#CDCBCA; font-weight:900; letter-spacing:-.08em; }}
.brand-copy strong {{ display:block; font-size:13px; letter-spacing:.1em; }} .brand-copy small {{ display:block; color:#A7A5A4; font-size:10px; letter-spacing:.14em; margin-top:2px; }}
.top-nav {{ display:flex; align-items:center; justify-content:flex-end; flex-wrap:wrap; gap:10px; }}
.nav-link {{ min-width:118px; padding:7px 15px; border:1px solid #6b3736; border-radius:999px; text-decoration:none; text-align:center; color:#CDCBCA; font-size:13px; }}
.nav-link:hover {{ background:#1d0b0b; border-color:#EE7672; }} .nav-link.active {{ color:#CDCBCA; border-color:var(--crimson); background:linear-gradient(100deg,#D41514,#790B0B); }}
main {{ width:min(1550px,100%); margin:auto; padding:52px clamp(20px,5vw,76px) 64px; }}
.page-hero {{ min-height:225px; display:flex; justify-content:space-between; align-items:center; gap:32px; padding:4px 0 30px; margin-bottom:16px; border-bottom:1px solid #332121; position:relative; overflow:hidden; }}
.page-hero::after {{ content:""; position:absolute; right:2%; top:-135px; width:280px; height:280px; border:24px solid #501111; border-radius:50%; opacity:.38; box-shadow:0 0 0 22px rgba(212,21,20,.14); pointer-events:none; }}
.hero-copy {{ max-width:940px; position:relative; z-index:1; }}
.eyebrow {{ color:#F17470; font-size:11px; font-weight:800; letter-spacing:.18em; }}
.page-title {{ font-family:Impact,"Arial Narrow",sans-serif; font-size:clamp(42px,6vw,82px); font-weight:900; line-height:.98; letter-spacing:.015em; margin:11px 0 18px; text-transform:uppercase; }}
.hero-ribbon {{ display:flex; align-items:center; gap:13px; width:fit-content; max-width:100%; padding:9px 19px; border-radius:999px; color:#CDCBCA; background:linear-gradient(100deg,#D41514,#690909); font-size:14px; }}
.ribbon-mark {{ font-family:Impact,"Arial Narrow",sans-serif; font-size:14px; font-weight:800; letter-spacing:.05em; white-space:nowrap; }}
.filters {{ display:flex; flex-wrap:wrap; align-items:end; gap:12px; padding:15px; margin:0 0 20px; background:var(--surface); border:1px solid #482121; border-radius:8px; }}
.filter {{ display:grid; gap:5px; min-width:115px; color:#CDCBCA; font-size:12px; font-weight:700; }}
select {{ min-width:115px; border:1px solid #5d3b3a; border-radius:5px; background:#0b0b0b; color:#CDCBCA; padding:9px 30px 9px 10px; font:inherit; }}
select:focus {{ outline:2px solid var(--crimson); outline-offset:1px; }}
.button {{ border:1px solid #E34C48; border-radius:5px; padding:9px 16px; background:#D41514; color:#CDCBCA; font:inherit; font-weight:700; cursor:pointer; }}
.button:hover {{ background:#EF322D; }}
.button-quiet {{ display:inline-block; border-color:#5a5654; background:transparent; color:#CDCBCA; text-align:center; text-decoration:none; }} .button-quiet:hover {{ background:#1b1a19; border-color:#CDCBCA; }}
.metric-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:0; margin:24px 0 30px; }}
.metric {{ display:flex; min-width:0; min-height:88px; flex-direction:column; justify-content:center; padding:10px clamp(14px,2vw,26px); animation:metric-enter 360ms cubic-bezier(.2,.7,.25,1) both; }}
.metric + .metric {{ border-left:1px solid var(--line); }}
.metric:nth-child(2) {{ animation-delay:45ms; }} .metric:nth-child(3) {{ animation-delay:90ms; }}
@keyframes metric-enter {{ from {{ opacity:0; transform:translateY(7px); }} to {{ opacity:1; transform:translateY(0); }} }}
@media(prefers-reduced-motion:reduce) {{ .metric {{ animation:none; }} }}
.metric span {{ display:block; color:var(--muted); font-size:10px; font-weight:700; letter-spacing:.11em; text-transform:uppercase; }} .metric strong {{ display:block; margin-top:6px; color:var(--ink); font-family:"Segoe UI",Arial,sans-serif; font-size:clamp(25px,3vw,34px); font-weight:650; font-variant-numeric:tabular-nums; line-height:1.15; letter-spacing:-.035em; }}
.panel-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); align-items:start; gap:18px; }}
.panel {{ min-width:0; background:linear-gradient(145deg,#151313,#0b0909 68%); border:1px solid #3a2424; border-radius:8px; padding:21px; }}
.panel h2 {{ font-family:Impact,"Arial Narrow",sans-serif; font-size:23px; font-weight:700; line-height:1.2; letter-spacing:.02em; margin:0 0 4px; text-transform:uppercase; }}
.panel-heading {{ display:flex; justify-content:space-between; align-items:baseline; gap:10px; margin-bottom:18px; padding-bottom:12px; border-bottom:1px solid #3a2525; }}
.panel-heading span {{ color:#A7A5A4; font-size:12px; }}
.rank-list {{ display:grid; gap:14px; }} .rank-row {{ display:grid; grid-template-columns:82px minmax(60px,1fr) 92px; align-items:center; gap:10px; }}
.rank-label {{ font-size:13px; font-weight:700; }} .rank-row strong {{ text-align:right; font-size:13px; font-variant-numeric:tabular-nums; }}
.track {{ height:9px; overflow:hidden; border-radius:99px; background:#292020; }} .fill {{ height:100%; border-radius:99px; background:linear-gradient(90deg,#D41514,#F06460); }}
table {{ width:100%; border-collapse:collapse; margin-top:12px; }} th,td {{ padding:10px 8px; text-align:left; border-bottom:1px solid #332323; }} th {{ color:#F1807B; font-size:11px; letter-spacing:.08em; text-transform:uppercase; }} td:last-child {{ font-variant-numeric:tabular-nums; font-weight:700; }}
.source-panel {{ margin-top:18px; }} .source-panel p {{ margin:10px 0 0; color:#CDCBCA; }} .path {{ color:#A7A5A4; }} code {{ padding:2px 5px; border-radius:4px; background:#201313; color:#CDCBCA; }}
.notice {{ display:flex; gap:14px; align-items:flex-start; border-color:#82221f; background:linear-gradient(120deg,#2b1010,#0b0909); }} .notice-mark {{ display:grid; place-items:center; flex:0 0 28px; height:28px; border:1px solid #D41514; border-radius:50%; color:#CDCBCA; font-weight:800; }}
.notice p {{ margin:7px 0 0; color:#CDCBCA; }} .empty {{ padding:20px; border:1px solid var(--line); border-radius:8px; background:var(--surface); }}
.forecast-result {{ margin:0 0 18px; padding:26px clamp(20px,4vw,42px); border:1px solid #D41514; border-radius:8px; background:linear-gradient(110deg,#6d0c0c,#1c0b0b 70%,#0b0909); }}
.forecast-kicker {{ color:#F1B6B3; font-size:11px; font-weight:800; letter-spacing:.14em; }}
.forecast-value {{ margin:7px 0; color:#CDCBCA; font-family:Impact,"Arial Narrow",sans-serif; font-size:clamp(38px,6vw,64px); line-height:1.1; }}
.forecast-result p {{ margin:4px 0; color:#CDCBCA; }} .forecast-result .forecast-method {{ color:#A7A5A4; font-size:12px; }}
.history-panel {{ max-width:720px; }}
@media(max-width:900px) {{ .topbar {{ align-items:flex-start; flex-direction:column; }} .top-nav {{ justify-content:flex-start; }} .metric-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .metric:nth-child(n+3) {{ border-top:1px solid var(--line); }} .metric:nth-child(odd) {{ border-left:0; }} .panel-grid {{ grid-template-columns:1fr; }} }}
@media(max-width:620px) {{ .topbar {{ padding:14px 16px; }} .top-nav {{ width:100%; flex-wrap:nowrap; overflow-x:auto; padding-bottom:4px; }} .nav-link {{ min-width:108px; }} main {{ padding:30px 16px 40px; }} .page-hero {{ min-height:190px; }} .page-title {{ font-size:46px; }} .hero-ribbon {{ align-items:flex-start; flex-direction:column; gap:2px; border-radius:10px; }} .metric-grid {{ grid-template-columns:1fr; }} .metric {{ display:flex; align-items:baseline; justify-content:space-between; gap:14px; padding:14px 4px; }} .metric + .metric,.metric:nth-child(odd) {{ border-left:0; border-top:1px solid var(--line); }} .metric strong {{ margin-top:0; text-align:right; font-size:24px; }} .filters {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); }} .filter,select {{ min-width:0; width:100%; }} .button {{ grid-column:1/-1; }} .rank-row {{ grid-template-columns:65px minmax(35px,1fr) 78px; gap:7px; }} }}
</style></head>
<body><div class="shell"><header class="topbar">
<a class="brand" href="/?page=overview"><span class="brand-mark">RA</span><span class="brand-copy"><strong>RETAIL / ANALYTICS</strong><small>WEEKLY SALES INTELLIGENCE</small></span></a>
<nav class="top-nav" aria-label="Main navigation">{nav}</nav></header>
<main><section class="page-hero"><div class="hero-copy"><div class="eyebrow">RETAIL INTELLIGENCE&nbsp; / &nbsp;WEEKLY PERFORMANCE</div>
<h1 class="page-title">{esc(title.upper())}</h1><div class="hero-ribbon"><span class="ribbon-mark">SALES, IN FOCUS</span><span>{esc(description)}</span></div></div></section>
{body}</main></div></body></html>'''
    return document.encode("utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        page_key = params.get("page", ["overview"])[0]
        try:
            body = render_page(page_key, params)
            status = 200
        except Exception as error:
            print(f"Dashboard request failed: {error}")
            body = render_page("about", {})
            status = 500
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")


def main():
    record_count = ensure_database()
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    address = f"http://{HOST}:{PORT}"
    print(f"Retail Sales Analytics is ready: {address}")
    print(f"Loaded {record_count:,} sales records. Press Ctrl+C to stop.")
    threading.Timer(0.8, lambda: webbrowser.open(address)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
