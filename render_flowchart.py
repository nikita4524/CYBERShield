"""
Render Phishing Email Detection — Two-Stage Hybrid flowchart as PNG
using matplotlib patches and annotations (no external dependencies beyond matplotlib).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(16, 22))
ax.set_xlim(0, 16)
ax.set_ylim(0, 22)
ax.axis("off")
fig.patch.set_facecolor("#0f172a")

# ── colour palette ────────────────────────────────────────────────
BG         = "#0f172a"
STAGE1_BG  = "#1a3a5c"
STAGE1_BD  = "#3b82f6"
STAGE2_BG  = "#2d1b4e"
STAGE2_BD  = "#8b5cf6"
BLEND_BG   = "#14532d"
BLEND_BD   = "#22c55e"
BOX_BG     = "#1e293b"
BOX_BD     = "#475569"
TEXT_COL   = "#f1f5f9"
ARROW_COL  = "#94a3b8"

SAFE_COL   = "#16a34a"
SUSP_COL   = "#ca8a04"
DANG_COL   = "#dc2626"
ACT_BG     = "#1e293b"


def box(ax, x, y, w, h, label, bg=BOX_BG, bd=BOX_BD, fontsize=9, radius=0.3, bold=False):
    patch = FancyBboxPatch((x - w/2, y - h/2), w, h,
                           boxstyle=f"round,pad=0.05,rounding_size={radius}",
                           linewidth=1.5, edgecolor=bd, facecolor=bg, zorder=3)
    ax.add_patch(patch)
    weight = "bold" if bold else "normal"
    ax.text(x, y, label, ha="center", va="center", fontsize=fontsize,
            color=TEXT_COL, zorder=4, weight=weight,
            multialignment="center")


def section_bg(ax, x, y, w, h, label, bg, bd):
    patch = FancyBboxPatch((x, y), w, h,
                           boxstyle="round,pad=0.1,rounding_size=0.4",
                           linewidth=2, edgecolor=bd, facecolor=bg,
                           alpha=0.45, zorder=1)
    ax.add_patch(patch)
    ax.text(x + w/2, y + h - 0.22, label, ha="center", va="top",
            fontsize=10, color=bd, weight="bold", zorder=2)


def arrow(ax, x1, y1, x2, y2, col=ARROW_COL):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=col, lw=1.5),
                zorder=5)


def diamond(ax, x, y, w, h, label, bg=BOX_BG, bd=BOX_BD, fontsize=8.5):
    from matplotlib.patches import Polygon
    pts = [(x, y+h/2), (x+w/2, y), (x, y-h/2), (x-w/2, y)]
    poly = Polygon(pts, closed=True, linewidth=1.5,
                   edgecolor=bd, facecolor=bg, zorder=3)
    ax.add_patch(poly)
    ax.text(x, y, label, ha="center", va="center",
            fontsize=fontsize, color=TEXT_COL, zorder=4,
            multialignment="center")


# ════════════════════════════════════════════════════════════════════
# INPUT
# ════════════════════════════════════════════════════════════════════
box(ax, 8, 21.3, 5, 0.7, "EMAIL INPUT\nSubject  |  Body  |  Sender  |  URLs",
    bg="#1e3a5c", bd="#60a5fa", fontsize=9, bold=True)
arrow(ax, 8, 20.95, 8, 20.55)
box(ax, 8, 20.2, 5, 0.6, "Extract Components",
    bg=BOX_BG, bd=BOX_BD, fontsize=9)

# ════════════════════════════════════════════════════════════════════
# STAGE 1 background
# ════════════════════════════════════════════════════════════════════
section_bg(ax, 0.4, 13.6, 15.2, 5.9,
           "STAGE 1  -  Rule-Based Heuristics",
           STAGE1_BG, STAGE1_BD)

# three analysis boxes
arrow(ax, 8, 19.9, 4, 18.85)
arrow(ax, 8, 19.9, 8, 18.85)
arrow(ax, 8, 19.9, 12, 18.85)

box(ax, 4,  18.5, 3.8, 0.9,
    "TEXT ANALYSIS\nUrgency phrases\nCredential requests\nFinancial scam language",
    bg="#1e3d6b", bd=STAGE1_BD, fontsize=8)
box(ax, 8,  18.5, 3.8, 0.9,
    "URL ANALYSIS\nSuspicious TLD  |  IP domain\nURL shortener  |  Typosquatting\nBank name abuse",
    bg="#1e3d6b", bd=STAGE1_BD, fontsize=8)
box(ax, 12, 18.5, 3.8, 0.9,
    "SENDER ANALYSIS\nFreemail domain\nLookalike domain\nDomain mismatch",
    bg="#1e3d6b", bd=STAGE1_BD, fontsize=8)

# arrows to weight box
arrow(ax, 4,  18.05, 6.2, 17.4)
arrow(ax, 8,  18.05, 8,   17.4)
arrow(ax, 12, 18.05, 9.8, 17.4)

box(ax, 8, 17.0, 5.5, 0.75,
    "Weighted Score\nText × 0.40   ·   URL × 0.35   ·   Sender × 0.25",
    bg="#1e3a5c", bd=STAGE1_BD, fontsize=8.5)

arrow(ax, 8, 16.62, 8, 16.15)

diamond(ax, 8, 15.75, 4.5, 0.75,
        "Multiple Strong Signals?",
        bg="#1e293b", bd=STAGE1_BD, fontsize=8.5)

# boost branches
arrow(ax, 6.25, 15.75, 4.5, 15.75)
ax.text(5.5, 15.85, "≥ 3", fontsize=7.5, color=ARROW_COL, ha="center")
box(ax, 3.5, 15.75, 2.2, 0.55, "Boost → 0.85",
    bg="#1a3a5c", bd=STAGE1_BD, fontsize=8)

arrow(ax, 9.75, 15.75, 11.5, 15.75)
ax.text(10.6, 15.85, "≥ 2", fontsize=7.5, color=ARROW_COL, ha="center")
box(ax, 12.5, 15.75, 2.2, 0.55, "Boost → 0.60",
    bg="#1a3a5c", bd=STAGE1_BD, fontsize=8)

arrow(ax, 8, 15.37, 8, 14.9)
ax.text(8.15, 15.12, "< 2", fontsize=7.5, color=ARROW_COL, ha="left")
box(ax, 8, 14.6, 2.8, 0.55, "Keep weighted score",
    bg=BOX_BG, bd=BOX_BD, fontsize=8)

# merge to Rule Score
arrow(ax, 3.5, 15.47, 3.5, 14.1);  arrow(ax, 3.5, 14.1, 6.2, 13.85)
arrow(ax, 12.5, 15.47, 12.5, 14.1); arrow(ax, 12.5, 14.1, 9.8, 13.85)
arrow(ax, 8, 14.32, 8, 13.85)

box(ax, 8, 13.55, 3, 0.55, "Rule Score  [0 – 1]",
    bg="#1a3a5c", bd=STAGE1_BD, fontsize=9, bold=True)

# ════════════════════════════════════════════════════════════════════
# STAGE 2 background
# ════════════════════════════════════════════════════════════════════
section_bg(ax, 0.4, 8.5, 15.2, 4.4,
           "STAGE 2  -  ML Classifier  (TF-IDF + Ensemble)",
           STAGE2_BG, STAGE2_BD)

arrow(ax, 8, 13.27, 8, 12.85)

diamond(ax, 8, 12.45, 4.5, 0.75,
        "Trained Model Available?\n(.pkl files on disk)",
        bg="#1e293b", bd=STAGE2_BD, fontsize=8)

# YES path
arrow(ax, 8, 12.07, 8, 11.6)
ax.text(8.1, 11.82, "YES", fontsize=7.5, color=ARROW_COL)
box(ax, 8, 11.25, 4.5, 0.65,
    "TF-IDF Vectorizer\n10 000 features  ·  Bigrams  ·  sublinear_tf",
    bg="#3d1b4e", bd=STAGE2_BD, fontsize=8)

arrow(ax, 8, 10.92, 8, 10.45)
box(ax, 8, 10.1, 4.5, 0.65,
    "Ensemble: Logistic Regression + Random Forest\nSoft-voting  →  P(phishing)",
    bg="#3d1b4e", bd=STAGE2_BD, fontsize=8)

arrow(ax, 8, 9.77, 8, 9.3)
box(ax, 8, 9.0, 3, 0.55, "AI Probability  [0 – 1]",
    bg="#2d1b4e", bd=STAGE2_BD, fontsize=9, bold=True)

# NO fallback
arrow(ax, 10.25, 12.45, 13.5, 12.45)
ax.text(11.8, 12.55, "NO / Fallback", fontsize=7.5, color=ARROW_COL, ha="center")
box(ax, 13.5, 12.45, 2.8, 0.65,
    "Fallback:\nUse Rule Score\nas AI score",
    bg="#2d1b4e", bd=STAGE2_BD, fontsize=8)
arrow(ax, 13.5, 12.12, 13.5, 9.0); arrow(ax, 13.5, 9.0, 9.5, 9.0)

# ════════════════════════════════════════════════════════════════════
# BLEND background
# ════════════════════════════════════════════════════════════════════
section_bg(ax, 0.4, 3.8, 15.2, 4.5,
           "Final Blend  -  75% AI  +  25% Rules",
           BLEND_BG, BLEND_BD)

arrow(ax, 8, 8.72, 8, 8.25)
box(ax, 8, 7.9, 6, 0.65,
    "Final Score  =  0.75 × AI Score  +  0.25 × Rule Score",
    bg="#1a3d2b", bd=BLEND_BD, fontsize=9, bold=True)

arrow(ax, 8, 7.57, 8, 7.1)
diamond(ax, 8, 6.7, 4.5, 0.75,
        "Score Threshold\n(0 – 100)",
        bg="#1e293b", bd=BLEND_BD, fontsize=8.5)

# three outcome arrows
arrow(ax, 5.75, 6.7, 3.5, 6.7)
ax.text(4.6, 6.82, "≤ 30", fontsize=7.5, color=ARROW_COL, ha="center")
box(ax, 2.4, 6.7, 2.0, 0.55, "SAFE",
    bg="#14532d", bd=SAFE_COL, fontsize=9, bold=True)

arrow(ax, 8, 6.32, 8, 5.85)
ax.text(8.12, 6.08, "31–69", fontsize=7.5, color=ARROW_COL)
box(ax, 8, 5.55, 2.2, 0.55, "SUSPICIOUS",
    bg="#713f12", bd=SUSP_COL, fontsize=9, bold=True)

arrow(ax, 10.25, 6.7, 12.5, 6.7)
ax.text(11.3, 6.82, "≥ 70", fontsize=7.5, color=ARROW_COL, ha="center")
box(ax, 13.5, 6.7, 2.0, 0.55, "DANGEROUS",
    bg="#7f1d1d", bd=DANG_COL, fontsize=9, bold=True)

# action arrows
arrow(ax, 2.4, 6.42, 2.4, 5.55)
box(ax, 2.4, 5.2, 2.0, 0.6, "ALLOW",
    bg="#14532d", bd=SAFE_COL, fontsize=9)

arrow(ax, 8, 5.27, 8, 4.8)
box(ax, 8, 4.45, 2.0, 0.6, "WARN",
    bg="#713f12", bd=SUSP_COL, fontsize=9)

arrow(ax, 13.5, 6.42, 13.5, 5.55)
box(ax, 13.5, 5.2, 2.2, 0.6, "QUARANTINE",
    bg="#7f1d1d", bd=DANG_COL, fontsize=9)

# ════════════════════════════════════════════════════════════════════
# OUTPUT
# ════════════════════════════════════════════════════════════════════
arrow(ax, 2.4, 4.9, 2.4, 4.15);   arrow(ax, 2.4, 4.15, 5.8, 3.85)
arrow(ax, 8, 4.15, 8, 3.85)
arrow(ax, 13.5, 4.9, 13.5, 4.15); arrow(ax, 13.5, 4.15, 10.2, 3.85)

box(ax, 8, 3.55, 6.5, 0.6,
    "RESPONSE  -  Risk Score | Label | Explanation | Highlighted Phrases | Flagged URLs",
    bg="#1e3a5c", bd="#60a5fa", fontsize=8.5, bold=True)

plt.tight_layout(pad=0)
out_path = r"c:\Users\ADMIN\OneDrive\Desktop\capstone\cybershield-ai-main\phishing_flowchart.png"
plt.savefig(out_path, dpi=180, bbox_inches="tight",
            facecolor=fig.get_facecolor())
plt.close()
print("Saved:", out_path)
