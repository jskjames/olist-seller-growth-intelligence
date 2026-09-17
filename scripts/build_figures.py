"""Generate the README chart from audited exported cohort metrics."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LEADS = pd.read_csv(ROOT / "outputs" / "lead_channel_metrics.csv").set_index("origin")
SELLERS = pd.read_csv(ROOT / "outputs" / "seller_channel_metrics.csv").set_index("origin")
ORIGINS = ["paid_search", "organic_search", "social"]
LABELS = ["Paid search", "Organic search", "Social"]
PALETTE = ["#206d65", "#8cae9a", "#d98965"]

fig, axes = plt.subplots(1, 2, figsize=(11.7, 4.1), facecolor="#f7f7f2")
for ax in axes:
    ax.set_facecolor("#f7f7f2")
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#cbd8d0")
    ax.grid(axis="y", color="#dce6dd", alpha=.9)
    ax.tick_params(axis="both", colors="#475b54", length=0, labelsize=9)
    ax.set_axisbelow(True)

x = np.arange(3)
lead_rate = [LEADS.loc[o, "conversion_90d"] * 100 for o in ORIGINS]
low = [LEADS.loc[o, "ci_low"] * 100 for o in ORIGINS]
high = [LEADS.loc[o, "ci_high"] * 100 for o in ORIGINS]
axes[0].bar(x, lead_rate, color=PALETTE, width=.62)
axes[0].errorbar(x, lead_rate, yerr=[np.array(lead_rate)-low, np.array(high)-lead_rate],
                 fmt="none", ecolor="#1a2a27", capsize=4, lw=1)
axes[0].set_ylim(0, 13.5)
axes[0].set_yticks([0, 4, 8, 12], ["0%", "4%", "8%", "12%"])
axes[0].set_xticks(x, [f"{label}\nn = {LEADS.loc[o, 'eligible_leads']:,.0f}" for label, o in zip(LABELS, ORIGINS)])
axes[0].set_title("Qualified leads won within 90 days", loc="left", pad=17, fontsize=12, color="#203f38")
for xi, value, high_bound in zip(x, lead_rate, high):
    axes[0].text(xi, high_bound+.35, f"{value:.1f}%", ha="center", fontsize=10, weight="bold", color="#1d443d")

activation = [SELLERS.loc[o, "observed_sale_share"] * 100 for o in ORIGINS]
axes[1].bar(x, activation, color=PALETTE, width=.62)
axes[1].set_ylim(0, 70)
axes[1].set_yticks([0, 20, 40, 60], ["0%", "20%", "40%", "60%"])
axes[1].set_xticks(x, [f"{label}\nn = {SELLERS.loc[o, 'matured_wins']:,.0f}" for label, o in zip(LABELS, ORIGINS)])
axes[1].set_title("Won sellers with a recorded sale in 90 days", loc="left", pad=17, fontsize=12, color="#203f38")
for xi, value, o in zip(x, activation, ORIGINS):
    axes[1].text(xi, value+2, f"{value:.1f}%", ha="center", fontsize=10, weight="bold", color="#1d443d")

fig.subplots_adjust(left=.075, right=.98, bottom=.27, top=.83, wspace=.24)
dest = ROOT / "assets" / "channel-comparison.png"
dest.parent.mkdir(exist_ok=True)
fig.savefig(dest, dpi=165, facecolor=fig.get_facecolor())
print(dest)
