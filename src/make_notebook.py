"""Build and execute notebooks/road_accidents.ipynb (the guided tour of the analysis)."""
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    md("# Road accidents in France and in Haut-Rhin, 2019–2024\n"
       "Guided tour of the analysis. Every table comes from a SQL query on the DuckDB database "
       "built by `src/build_db.py`; every chart is produced by a function of `src/analysis.py`.\n\n"
       "Data: ONISR national road-accident file (BAAC), INSEE population estimates. Scope: metropolitan France."),
    code("import sys; sys.path.insert(0, '../src')\n"
         "from IPython.display import Image\n"
         "import pandas as pd; pd.set_option('display.precision', 3)\n"
         "from analysis import *\n"
         "from model import fit, fig_odds"),
    md("## 0. Can we trust the data?\nShare of missing values on the fields we use, then our yearly death counts "
       "compared with the official ONISR figures."),
    code("data_quality()"),
    code("validation_vs_onisr()"),
    md("Our counts match the official figures exactly for 2019–2023 (2024 was not yet published as a final figure "
       "when this was written), so the cleaning keeps every accident."),
    md("## 1. Trend\nAccidents fell during the 2020 lockdowns and have not returned to 2019 levels; deaths have."),
    code("tr = yearly_trend(); tr"),
    code("fig_trend(tr); Image('../figures/01_trend.png')"),
    md("Haut-Rhin counts are small (20–36 deaths a year), so year-to-year swings are mostly noise."),
    md("## 2. When\nBusiest at the evening rush hour; deadliest between 3 and 6 a.m. (about 11% of accidents fatal, vs 4.5–5.5% during the day)."),
    code("hw = hour_weekday(); fig_when(hw); Image('../figures/02_when.png')"),
    md("## 3. Who"),
    code("km = killed_by_mode(); fig_modes(km)"),
    code("Image('../figures/03_modes.png')"),
    code("ag = killed_rate_by_age(); fig_age(ag); Image('../figures/04_age.png')"),
    md("Young men (20–24) and people over 80 have the highest death rates."),
    md("## 4. Where"),
    code("dep = by_department(); dep.head(10)"),
    code("dep[dep.dep == '68']"),
    code("fig_map(dep); Image('../figures/05_map_departments.png')"),
    code("profile_68_vs_france()"),
    code("fig_haut_rhin(haut_rhin_points()); Image('../figures/06_haut_rhin_map.png')"),
    md("### A warning about the denominator\nDeaths are almost always recorded; minor accidents are not. "
       "Haut-Rhin has a higher *share* of fatal accidents than France, yet fewer deaths per inhabitant: "
       "it records fewer non-fatal accidents per inhabitant. The city counts make it visible."),
    code("rc = recording_completeness(); fig_completeness(rc); Image('../figures/07_recording_completeness.png')"),
    code("cities().pivot(index='year', columns='city', values='accidents')"),
    md("Mulhouse records fewer accidents than Colmar, a smaller city, and about 15 times fewer than Strasbourg, "
       "which is only about three times its size. That points to under-recording of non-fatal accidents in "
       "Mulhouse rather than safer streets, a hypothesis to check with local police or city data."),
    md("## 5. What makes an accident fatal?\nLogistic regression on ~300,000 accidents. "
       "Odds ratios above 1 increase the odds that someone dies; they are associations, not causes."),
    code("ors, stats = fit(); stats"),
    code("ors.round(2)"),
    code("fig_odds(ors); Image('../figures/08_odds_ratios.png')"),
    md("## Conclusions\n"
       "* About 3,000 people die every year on metropolitan French roads; the number is flat since 2019.\n"
       "* Two thirds of deaths happen outside built-up areas, which hold only a third of accidents.\n"
       "* Deaths of e-scooter riders went from 11 to 47 a year; injured e-scooter users quadrupled.\n"
       "* Haut-Rhin is among the safer departments (36 deaths per million, rank 11 of 96).\n"
       "* Pedestrians, heavy vehicles, fixed obstacles and head-on collisions multiply the odds of a fatal outcome by 2.5 to 3."),
]
nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3"}})
path = ROOT / "notebooks" / "road_accidents.ipynb"
NotebookClient(nb, timeout=900, resources={"metadata": {"path": str(path.parent)}}).execute()
nbf.write(nb, path)
print("written", path)
