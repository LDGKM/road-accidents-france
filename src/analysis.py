"""All the analyses of the project: each function answers one question,
returns a pandas DataFrame and (when relevant) saves a figure.

    python src/analysis.py        # runs everything, writes figures/ and results/

The functions are also imported by the notebook, which shows the same
tables and charts with comments.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "accidents.duckdb"
FIG = ROOT / "figures"
RES = ROOT / "results"
YEARS = list(range(2019, 2025))
HAUT_RHIN = "68"
MULHOUSE = "68224"          # INSEE code of the commune of Mulhouse

# One consistent look for every chart
INK, MUTED, GRID = "#1f2933", "#6b7280", "#e5e7eb"
BLUE, RED, ORANGE, GREEN, PURPLE, GREY = "#2563eb", "#dc2626", "#ea8c2c", "#16a34a", "#7c3aed", "#9ca3af"
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 200, "savefig.bbox": "tight",
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "xtick.color": MUTED, "ytick.color": MUTED,
    "legend.frameon": False,
})


def con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(DB.as_posix(), read_only=True)


def q(sql: str, **params) -> pd.DataFrame:
    """Run a SQL query on the database and return a DataFrame."""
    with con() as c:
        return c.execute(sql, params).df()


def save(fig: plt.Figure, name: str) -> None:
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)


# ---------------------------------------------------------------- 0. data quality
def data_quality() -> pd.DataFrame:
    """How complete are the key fields? (share of missing values, metropolitan France)."""
    df = q("""
        SELECT 'Accident: GPS coordinates'   AS field, avg((lat IS NULL OR lat = 0)::INT) AS missing FROM acc_metro
        UNION ALL SELECT 'Accident: hour',          avg((hour IS NULL)::INT)        FROM acc_metro
        UNION ALL SELECT 'Accident: weather',       avg((atm IS NULL)::INT)         FROM acc_metro
        UNION ALL SELECT 'Place: speed limit (valid 10-130)', avg((speed_limit IS NULL)::INT) FROM acc_full
        UNION ALL SELECT 'Person: severity',        avg((severity IS NULL)::INT)    FROM people
        UNION ALL SELECT 'Person: age',             avg((age IS NULL)::INT)         FROM people
        UNION ALL SELECT 'Person: sex',             avg((sex IS NULL)::INT)         FROM people
        UNION ALL SELECT 'Person: travel mode',     avg((mode = 'Other / unknown')::INT) FROM people
    """)
    df["missing"] = (100 * df["missing"]).round(2)
    return df.rename(columns={"missing": "missing_%"})


def validation_vs_onisr() -> pd.DataFrame:
    """Our killed counts vs the official ONISR figures for metropolitan France.
    (Official values: ONISR annual reports 'La sécurité routière en France'.)"""
    official = {2019: 3244, 2020: 2541, 2021: 2944, 2022: 3267, 2023: 3167}
    df = q("SELECT year, sum(killed)::INT AS killed_ours FROM acc_full GROUP BY year ORDER BY year")
    df["killed_onisr"] = df["year"].map(official)
    return df


# ---------------------------------------------------------------- 1. trend
def yearly_trend() -> pd.DataFrame:
    """Accidents and deaths per year, France vs Haut-Rhin."""
    return q("""
        SELECT year,
               count(*)                                   AS accidents_fr,
               sum(killed)::INT                           AS killed_fr,
               count(*) FILTER (WHERE dep = $d)           AS accidents_68,
               sum(killed) FILTER (WHERE dep = $d)::INT   AS killed_68
        FROM acc_full GROUP BY year ORDER BY year""", d=HAUT_RHIN)


def fig_trend(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for ax, col, title in ((axes[0], "accidents", "Injury accidents (index 2019 = 100)"),
                           (axes[1], "killed", "People killed (index 2019 = 100)")):
        for suffix, color, label in (("fr", BLUE, "Metropolitan France"), ("68", RED, "Haut-Rhin")):
            s = df[f"{col}_{suffix}"]
            ax.plot(df["year"], 100 * s / s.iloc[0], marker="o", color=color, lw=2, label=label)
        ax.axhline(100, color=MUTED, lw=0.8, ls="--")
        ax.set_title(title)
        ax.set_xticks(YEARS)
        ax.annotate("Covid\nlockdowns", (2020, 100 * df[f"{col}_fr"].iloc[1] / df[f"{col}_fr"].iloc[0]),
                    xytext=(2020.3, 70), fontsize=8, color=MUTED, arrowprops=dict(arrowstyle="-", color=MUTED))
    axes[0].legend(loc="lower right")
    axes[0].set_ylim(60, 130); axes[1].set_ylim(60, 160)
    save(fig, "01_trend")


# ---------------------------------------------------------------- 2. when
def hour_weekday() -> pd.DataFrame:
    """Accidents and fatality rate by hour and weekday (metropolitan France, 2019-2024)."""
    return q("""
        SELECT weekday, hour, count(*) AS accidents, avg(fatal::INT) AS fatal_rate
        FROM acc_full WHERE hour IS NOT NULL GROUP BY ALL ORDER BY weekday, hour""")


def fig_when(df: pd.DataFrame) -> None:
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    order = [1, 2, 3, 4, 5, 6, 0]                  # DuckDB: 0 = Sunday
    grid = df.pivot(index="weekday", columns="hour", values="accidents").loc[order]
    by_hour = df.groupby("hour").apply(lambda g: np.average(g.fatal_rate, weights=g.accidents), include_groups=False)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"width_ratios": [1.6, 1]})
    im = a1.imshow(grid.values / len(YEARS), aspect="auto", cmap="Blues")
    a1.set_yticks(range(7), days); a1.set_xticks(range(0, 24, 3), [f"{h}h" for h in range(0, 24, 3)])
    a1.grid(False); a1.set_title("Accidents per year, by weekday and hour")
    fig.colorbar(im, ax=a1, fraction=0.03, pad=0.02)
    a2.bar(by_hour.index, 100 * by_hour.values, color=[RED if h < 6 else GREY for h in by_hour.index])
    a2.set_title("Share of accidents that are fatal, by hour")
    a2.set_xticks(range(0, 24, 3), [f"{h}h" for h in range(0, 24, 3)]); a2.set_ylabel("%")
    save(fig, "02_when")


# ---------------------------------------------------------------- 3. who
def killed_by_mode() -> pd.DataFrame:
    """People killed per year by travel mode."""
    return q("""
        SELECT year, mode, count(*) FILTER (WHERE severity = 2) AS killed
        FROM people GROUP BY ALL ORDER BY year, killed DESC""")


def fig_modes(df: pd.DataFrame) -> pd.DataFrame:
    wide = df.pivot(index="year", columns="mode", values="killed").fillna(0)
    change = pd.DataFrame({"2019": wide.loc[2019], "2024": wide.loc[2024]})
    change["change_%"] = (100 * (change["2024"] / change["2019"] - 1)).round(0)
    show = ["Car", "Motorcycle", "Pedestrian", "Bicycle", "E-scooter", "E-bike"]
    colors = [BLUE, ORANGE, PURPLE, GREEN, RED, "#0d9488"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.8))
    for m, c in zip(show, colors):
        a1.plot(wide.index, wide[m], marker="o", lw=2, color=c, label=m)
    a1.set_title("People killed per year, by travel mode"); a1.set_xticks(YEARS); a1.set_yscale("log")
    a1.set_yticks([20, 50, 100, 200, 500, 1000]); a1.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); a1.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    a1.legend(ncol=2, fontsize=8)
    ch = change.loc[show, "change_%"]
    a2.barh(show[::-1], ch[::-1], color=[RED if v > 0 else BLUE for v in ch[::-1]])
    a2.axvline(0, color=INK, lw=0.8); a2.set_title("Change in deaths, 2024 vs 2019 (%)")
    for i, v in enumerate(ch[::-1]):
        a2.text(v + (3 if v >= 0 else -3), i, f"{v:+.0f}%", va="center", ha="left" if v >= 0 else "right", fontsize=9)
    a2.set_xlim(min(ch.min() - 25, -40), ch.max() + 40)
    save(fig, "03_modes")
    return change.loc[show]


def killed_rate_by_age() -> pd.DataFrame:
    """Deaths per 100,000 inhabitants per year, by age group and sex (pop. 2023)."""
    return q("""
        WITH k AS (
            SELECT LEAST(5 * (age // 5), 95) AS age_lo, sex, count(*) / 6.0 AS killed_per_year
            FROM people WHERE severity = 2 AND age IS NOT NULL AND sex IN (1, 2) GROUP BY ALL
        ), p AS (SELECT age_lo, sex, sum(population) AS pop FROM population GROUP BY ALL)
        SELECT p.age_lo, p.sex, COALESCE(k.killed_per_year, 0) AS killed_per_year,
               100000 * COALESCE(k.killed_per_year, 0) / p.pop AS rate_per_100k
        FROM p LEFT JOIN k USING (age_lo, sex) ORDER BY sex, age_lo""")


def fig_age(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for sex, color, label in ((1, BLUE, "Men"), (2, RED, "Women")):
        d = df[df.sex == sex]
        ax.plot(d.age_lo + 2, d.rate_per_100k, marker="o", color=color, lw=2, label=label)
    ax.set_title("Road deaths per 100,000 inhabitants per year, by age")
    ax.set_xlabel("age"); ax.legend(); ax.set_xticks(range(0, 100, 10))
    save(fig, "04_age")


# ---------------------------------------------------------------- 4. where
def by_department() -> pd.DataFrame:
    """Deaths per million inhabitants per year, by department (2019-2024 average)."""
    return q("""
        WITH k AS (SELECT dep, sum(killed) / 6.0 AS killed_per_year, count(*) / 6.0 AS acc_per_year
                   FROM acc_full GROUP BY dep),
             p AS (SELECT dep, sum(population) AS pop FROM population GROUP BY dep)
        SELECT dep, pop, killed_per_year, acc_per_year,
               1e6 * killed_per_year / pop AS killed_per_million,
               rank() OVER (ORDER BY 1e6 * killed_per_year / pop) AS rank_safest
        FROM k JOIN p USING (dep) ORDER BY killed_per_million""")


def fig_map(df: pd.DataFrame) -> None:
    gj = json.loads((ROOT / "data" / "raw" / "departements.geojson").read_text(encoding="utf-8"))
    vals = df.set_index("dep")["killed_per_million"]
    cmap = plt.get_cmap("OrRd"); lo, hi = vals.min(), vals.max()
    fig, ax = plt.subplots(figsize=(6.4, 6.2))
    for f in gj["features"]:
        code = f["properties"]["code"]
        if code not in vals.index:
            continue
        geoms = f["geometry"]["coordinates"] if f["geometry"]["type"] == "MultiPolygon" else [f["geometry"]["coordinates"]]
        for poly in geoms:
            xy = np.array(poly[0])
            ax.fill(xy[:, 0], xy[:, 1], color=cmap((vals[code] - lo) / (hi - lo)),
                    ec=INK if code == HAUT_RHIN else "white", lw=2 if code == HAUT_RHIN else 0.4, zorder=3 if code == HAUT_RHIN else 2)
    ax.set_aspect(1 / np.cos(np.radians(46.5))); ax.axis("off"); ax.set_xlim(-5.3, 11.2)
    ax.set_title("Road deaths per million inhabitants per year (2019-2024)")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(lo, hi))
    fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.01)
    r = df.set_index("dep").loc[HAUT_RHIN]
    ax.annotate(f"Haut-Rhin: {r.killed_per_million:.0f}\n(rank {int(r.rank_safest)} of 96)", (7.3, 47.85),
                xytext=(8.4, 49.9), fontsize=9, arrowprops=dict(arrowstyle="-", color=INK))
    save(fig, "05_map_departments")


def profile_68_vs_france() -> pd.DataFrame:
    """How do accidents in Haut-Rhin differ from the national picture?"""
    df = q("""
        SELECT CASE WHEN dep = $d THEN 'Haut-Rhin' ELSE 'France (other depts)' END AS area,
               avg(in_town::INT)                         AS in_town,
               avg((lum IN (3, 4, 5))::INT)              AS at_night,
               avg((road_cat = 1)::INT)                  AS on_motorway,
               avg(has_motorcycle::INT)                  AS with_motorcycle,
               avg((has_bicycle OR has_escooter)::INT)   AS with_bike_or_escooter,
               avg((pedestrians > 0)::INT)               AS with_pedestrian,
               avg(fatal::INT)                           AS fatal,
               sum(killed) / count(*)                    AS killed_per_accident
        FROM acc_full GROUP BY area ORDER BY area DESC""", d=HAUT_RHIN)
    return df.set_index("area").T.round(3)


def haut_rhin_points() -> pd.DataFrame:
    return q("""SELECT lat, lon, fatal, com FROM acc_full
                WHERE dep = $d AND lat BETWEEN 47.3 AND 48.4 AND lon BETWEEN 6.8 AND 7.7""", d=HAUT_RHIN)


def fig_haut_rhin(pts: pd.DataFrame) -> None:
    gj = json.loads((ROOT / "data" / "raw" / "communes-68.geojson").read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(6, 7))
    for f in gj["features"]:
        geoms = f["geometry"]["coordinates"] if f["geometry"]["type"] == "MultiPolygon" else [f["geometry"]["coordinates"]]
        for poly in geoms:
            xy = np.array(poly[0])
            hl = f["properties"]["code"] == MULHOUSE
            ax.fill(xy[:, 0], xy[:, 1], color="#eef2ff" if hl else "#f8fafc", ec="#cbd5e1", lw=0.3)
    nf = pts[~pts.fatal]; fa = pts[pts.fatal]
    ax.scatter(nf.lon, nf.lat, s=4, color=BLUE, alpha=0.35, lw=0, label=f"injury accident ({len(nf):,})")
    ax.scatter(fa.lon, fa.lat, s=22, color=RED, ec="white", lw=0.5, label=f"fatal accident ({len(fa)})")
    ax.set_aspect(1 / np.cos(np.radians(47.8))); ax.axis("off"); ax.legend(loc="lower left", fontsize=8)
    ax.set_title("Haut-Rhin: every injury accident, 2019-2024")
    ax.annotate("Mulhouse", (7.33, 47.75), xytext=(7.55, 47.62), fontsize=9, arrowprops=dict(arrowstyle="-", color=INK))
    ax.annotate("Colmar", (7.36, 48.08), xytext=(7.55, 48.16), fontsize=9, arrowprops=dict(arrowstyle="-", color=INK))
    save(fig, "06_haut_rhin_map")


def recording_completeness() -> pd.DataFrame:
    """Deaths are almost never missed by the police, minor injury accidents
    often are. Comparing the two per department shows where non-fatal
    accidents are under-recorded: a low 'injured per death' ratio means
    many non-fatal accidents never reach the database."""
    return q("""
        WITH k AS (SELECT dep, count(*) / 6.0 AS acc, sum(killed) / 6.0 AS killed, sum(injured) / 6.0 AS injured
                   FROM acc_full GROUP BY dep),
             p AS (SELECT dep, sum(population) AS pop FROM population GROUP BY dep)
        SELECT dep, 1e6 * acc / pop AS accidents_per_million, 1e6 * killed / pop AS killed_per_million,
               injured / killed AS injured_per_death,
               rank() OVER (ORDER BY injured / killed DESC) AS rank_injured_per_death
        FROM k JOIN p USING (dep) ORDER BY injured_per_death DESC""")


def fig_completeness(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.scatter(df.accidents_per_million, df.killed_per_million, s=22, color=GREY, lw=0)
    for dep, name, color in (("68", "Haut-Rhin", RED), ("67", "Bas-Rhin", ORANGE), ("75", "Paris", BLUE),
                             ("69", "Rhône", BLUE), ("13", "Bouches-du-Rhône", BLUE)):
        r = df.set_index("dep").loc[dep]
        ax.scatter(r.accidents_per_million, r.killed_per_million, s=60, color=color, ec="white", zorder=3)
        ax.annotate(name, (r.accidents_per_million, r.killed_per_million), xytext=(6, -12 if dep == "67" else 4),
                    textcoords="offset points", fontsize=9)
    ax.set_xscale("log")
    ax.set_xticks([300, 500, 1000, 2000]); ax.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("recorded injury accidents per million inhabitants per year (log scale)")
    ax.set_ylabel("deaths per million per year")
    ax.set_title("Recorded accidents vs deaths, by department (2019-2024)")
    save(fig, "07_recording_completeness")


def cities() -> pd.DataFrame:
    """Recorded injury accidents per year in the three largest Alsatian cities."""
    return q("""
        SELECT CASE com WHEN '67482' THEN 'Strasbourg' WHEN '68224' THEN 'Mulhouse' WHEN '68066' THEN 'Colmar' END AS city,
               year, count(*) AS accidents, sum(killed)::INT AS killed
        FROM acc_full WHERE com IN ('67482', '68224', '68066') GROUP BY ALL ORDER BY city, year""")


# ---------------------------------------------------------------- 5. what makes an accident fatal
def model_data() -> pd.DataFrame:
    return q("""
        SELECT fatal::INT AS fatal, year,
               CASE WHEN lum = 1 THEN 'day' WHEN lum = 2 THEN 'dusk/dawn'
                    WHEN lum = 5 THEN 'night, lit' WHEN lum IN (3, 4) THEN 'night, unlit' END AS light,
               NOT in_town AS outside_town,
               CASE WHEN speed_limit <= 50 THEN '<=50' WHEN speed_limit <= 70 THEN '70'
                    WHEN speed_limit <= 90 THEN '80-90' ELSE '110-130' END AS speed_band,
               weekday IN (0, 6) AS weekend,
               atm IN (2, 3, 4, 5, 6) AS bad_weather,
               col = 7 AS single_vehicle, col = 1 AS head_on,
               has_motorcycle, has_bicycle, has_escooter, has_heavy, pedestrians > 0 AS pedestrian,
               hit_obstacle
        FROM acc_full
        WHERE lum IS NOT NULL AND speed_limit IS NOT NULL AND col IS NOT NULL AND atm IS NOT NULL
        ORDER BY acc_id      -- fixed order, so the random train/test split is reproducible""")


if __name__ == "__main__":
    RES.mkdir(exist_ok=True)
    dq = data_quality(); dq.to_csv(RES / "data_quality.csv", index=False); print(dq, "\n")
    val = validation_vs_onisr(); val.to_csv(RES / "validation_onisr.csv", index=False); print(val, "\n")
    tr = yearly_trend(); tr.to_csv(RES / "yearly_trend.csv", index=False); fig_trend(tr); print(tr, "\n")
    hw = hour_weekday(); fig_when(hw)
    km = killed_by_mode(); ch = fig_modes(km); ch.to_csv(RES / "killed_by_mode_change.csv"); print(ch, "\n")
    ag = killed_rate_by_age(); ag.to_csv(RES / "killed_rate_by_age.csv", index=False); fig_age(ag)
    dep = by_department(); dep.to_csv(RES / "departments.csv", index=False); fig_map(dep)
    print(dep[dep.dep == HAUT_RHIN], "\n")
    prof = profile_68_vs_france(); prof.to_csv(RES / "profile_68_vs_france.csv"); print(prof, "\n")
    fig_haut_rhin(haut_rhin_points())
    rc = recording_completeness(); rc.to_csv(RES / "recording_completeness.csv", index=False); fig_completeness(rc)
    print(rc[rc.dep.isin(["68", "67", "75"])], "\n", rc.injured_per_death.describe())
    ci = cities(); ci.to_csv(RES / "alsace_cities.csv", index=False); print(ci.pivot(index="year", columns="city", values="accidents"))
