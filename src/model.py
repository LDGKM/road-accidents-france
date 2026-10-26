"""Which circumstances make an injury accident more likely to be fatal?

    python src/model.py

Logistic regression on ~300,000 accidents (metropolitan France 2019-2024).
Target: 1 if at least one person died within 30 days, else 0.
Output: odds ratios with 95% confidence intervals (results/odds_ratios.csv),
a forest plot (figures/08_odds_ratios.png) and an out-of-sample check
(ROC AUC on a 25% hold-out).

Odds ratios describe associations, not causes: e.g. motorway accidents
look less deadly once speed is accounted for, but that does not mean
motorways make crashes safer.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from analysis import BLUE, FIG, GREY, INK, RED, RES, model_data, save

FORMULA = ("fatal ~ C(light, Treatment('day')) + outside_town + C(speed_band, Treatment('<=50'))"
           " + weekend + bad_weather + single_vehicle + head_on + has_motorcycle + has_bicycle"
           " + has_escooter + has_heavy + pedestrian + hit_obstacle + C(year)")

LABELS = {
    "C(light, Treatment('day'))[T.dusk/dawn]": "Dusk or dawn (vs daylight)",
    "C(light, Treatment('day'))[T.night, lit]": "Night, street lights on",
    "C(light, Treatment('day'))[T.night, unlit]": "Night, no street lights",
    "outside_town[T.True]": "Outside built-up area",
    "C(speed_band, Treatment('<=50'))[T.70]": "Speed limit 70 (vs <=50)",
    "C(speed_band, Treatment('<=50'))[T.80-90]": "Speed limit 80-90",
    "C(speed_band, Treatment('<=50'))[T.110-130]": "Speed limit 110-130",
    "weekend[T.True]": "Weekend",
    "bad_weather[T.True]": "Rain, snow, fog or wind",
    "single_vehicle[T.True]": "Single vehicle, no collision",
    "head_on[T.True]": "Head-on collision",
    "has_motorcycle[T.True]": "Motorcycle involved",
    "has_bicycle[T.True]": "Bicycle or e-bike involved",
    "has_escooter[T.True]": "E-scooter involved",
    "has_heavy[T.True]": "Heavy vehicle involved",
    "pedestrian[T.True]": "Pedestrian involved",
    "hit_obstacle[T.True]": "Fixed obstacle hit (tree, wall...)",
}


def fit() -> tuple[pd.DataFrame, dict]:
    df = model_data()
    for c in ("outside_town", "weekend", "bad_weather", "single_vehicle", "head_on", "has_motorcycle",
              "has_bicycle", "has_escooter", "has_heavy", "pedestrian", "hit_obstacle"):
        df[c] = df[c].fillna(False).astype(bool)

    # 1) out-of-sample check: fit on 75%, score the remaining 25%
    train, test = train_test_split(df, test_size=0.25, random_state=42, stratify=df["fatal"])
    m_train = smf.logit(FORMULA, data=train).fit(disp=False)
    auc = roc_auc_score(test["fatal"], m_train.predict(test))

    # 2) final model on all accidents, for the odds ratios
    m = smf.logit(FORMULA, data=df).fit(disp=False)
    ci = m.conf_int()
    ors = pd.DataFrame({"odds_ratio": np.exp(m.params), "ci_low": np.exp(ci[0]), "ci_high": np.exp(ci[1]),
                        "p_value": m.pvalues})
    ors = ors.loc[[k for k in LABELS if k in ors.index]]
    ors.index = [LABELS[k] for k in ors.index]
    stats = {"n_accidents": int(len(df)), "fatal_rate": float(df["fatal"].mean()),
             "auc_holdout": float(auc), "pseudo_r2": float(m.prsquared)}
    return ors.sort_values("odds_ratio"), stats


def fig_odds(ors: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 5.4))
    y = np.arange(len(ors))
    colors = [RED if lo > 1 else BLUE if hi < 1 else GREY for lo, hi in zip(ors.ci_low, ors.ci_high)]
    ax.errorbar(ors.odds_ratio, y, xerr=[ors.odds_ratio - ors.ci_low, ors.ci_high - ors.odds_ratio],
                fmt="none", ecolor=INK, elinewidth=1, capsize=2)
    ax.scatter(ors.odds_ratio, y, color=colors, s=40, zorder=3)
    ax.axvline(1, color=INK, lw=0.8, ls="--")
    ax.set_xscale("log"); ax.set_xticks([0.3, 0.5, 1, 2, 3, 5]); ax.set_xticklabels(["0.3", "0.5", "1", "2", "3", "5"])
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_yticks(y, ors.index); ax.set_xlabel("odds ratio of a fatal outcome (log scale, 95% CI)")
    ax.set_title("What makes an injury accident fatal?")
    for yi, v in zip(y, ors.odds_ratio):
        ax.text(ors.ci_high.max() * 1.15, yi, f"x{v:.2f}", va="center", fontsize=8, color=INK)
    save(fig, "08_odds_ratios")


if __name__ == "__main__":
    ors, stats = fit()
    RES.mkdir(exist_ok=True)
    ors.round(3).to_csv(RES / "odds_ratios.csv")
    (RES / "model_stats.json").write_text(json.dumps(stats, indent=2))
    fig_odds(ors)
    print(ors.round(2)); print(stats)
