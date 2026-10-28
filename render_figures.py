"""
Render Figure 4.1 High Level Architecture
      Figure 4.2 Methodology Block Diagram
as high-resolution PNGs using matplotlib only.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon

# ── shared helpers ──────────────────────────────────────────────────────────
BG       = "#0d1117"
TEXT     = "#e2e8f0"
MUTED    = "#94a3b8"
ARROW    = "#64748b"

def rbox(ax, cx, cy, w, h, text, fc, ec, fs=8.5, bold=False, radius=0.25, lw=1.8, alpha=1.0):
    p = FancyBboxPatch((cx-w/2, cy-h/2), w, h,
                       boxstyle=f"round,pad=0.04,rounding_size={radius}",
                       linewidth=lw, edgecolor=ec, facecolor=fc, alpha=alpha, zorder=3)
    ax.add_patch(p)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs,
            color=TEXT, zorder=4, weight="bold" if bold else "normal",
            multialignment="center")

def band(ax, x, y, w, h, label, fc, ec, lw=2):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle="round,pad=0.08,rounding_size=0.3",
                       linewidth=lw, edgecolor=ec, facecolor=fc, alpha=0.25, zorder=1)
    ax.add_patch(p)
    ax.text(x+w/2, y+h-0.18, label, ha="center", va="top",
            fontsize=9, color=ec, weight="bold", zorder=2)

def arr(ax, x1, y1, x2, y2, col=ARROW, lw=1.4, style="-|>"):
    ax.annotate("", xy=(x2,y2), xytext=(x1,y1),
                arrowprops=dict(arrowstyle=style, color=col, lw=lw), zorder=5)

def label(ax, x, y, text, fs=7.5, col=MUTED, ha="center"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=fs, color=col, zorder=6)

def diam(ax, cx, cy, w, h, text, fc, ec, fs=8):
    pts = [(cx, cy+h/2), (cx+w/2, cy), (cx, cy-h/2), (cx-w/2, cy)]
    poly = Polygon(pts, closed=True, linewidth=1.6, edgecolor=ec, facecolor=fc, zorder=3)
    ax.add_patch(poly)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs,
            color=TEXT, zorder=4, multialignment="center")


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 4.1 — HIGH LEVEL ARCHITECTURE
# ════════════════════════════════════════════════════════════════════════════
fig1, ax1 = plt.subplots(figsize=(20, 13))
ax1.set_xlim(0, 20); ax1.set_ylim(0, 13)
ax1.axis("off")
fig1.patch.set_facecolor(BG)
ax1.set_facecolor(BG)

# title
ax1.text(10, 12.6, "Figure 4.1  High Level Architecture", ha="center", va="top",
         fontsize=14, color=TEXT, weight="bold")
ax1.text(10, 12.25, "CyberShield AI  —  India-first Multi-Modal Cyber Threat Detection Platform",
         ha="center", va="top", fontsize=9, color=MUTED)

# ── Layer colours ──
C_FE  = "#1e3a5c"; E_FE  = "#3b82f6"   # Frontend  – blue
C_GW  = "#1a3d2b"; E_GW  = "#22c55e"   # API GW    – green
C_ML  = "#3d1b4e"; E_ML  = "#a855f7"   # ML layer  – purple
C_DB  = "#3d2800"; E_DB  = "#f59e0b"   # Data      – amber
C_EXT = "#1e293b"; E_EXT = "#64748b"   # External  – slate

# ── band backgrounds ──
band(ax1,  0.3, 9.9, 19.4, 2.0,  "PRESENTATION LAYER  (Next.js 14 / React / Tailwind CSS)", C_FE, E_FE)
band(ax1,  0.3, 7.5, 19.4, 1.9,  "API GATEWAY  (FastAPI / Python 3.13)", C_GW, E_GW)
band(ax1,  0.3, 4.0, 19.4, 3.0,  "INTELLIGENCE LAYER  (ML / AI Models)", C_ML, E_ML)
band(ax1,  0.3, 1.9, 8.5,  1.7,  "DATA LAYER  (PostgreSQL + SQLite dev)", C_DB, E_DB)
band(ax1,  9.2, 1.9, 10.5, 1.7,  "EXTERNAL SERVICES", C_EXT, E_EXT)

# ── FRONTEND boxes ──
pages = [
    ("Dashboard",    2.2), ("Threat\nAnalyzer", 5.0), ("Awareness\n& Quiz",  7.8),
    ("AI\nAssistant",10.6),("Incident\nReports",13.4),("Admin\nPanel",       16.2),
    ("Security\nHub",19.0-2.4+1.0),
]
for name, cx in pages:
    rbox(ax1, cx, 10.7, 2.6, 0.9, name, C_FE, E_FE, fs=8)

# ── GATEWAY boxes ──
gw_items = [
    ("/analyze\n(email,url,qr\naudio,video)", 2.8),
    ("/auth\n(JWT + OTP)", 6.0),
    ("/awareness\n(quiz/scenarios)", 9.2),
    ("/assistant\n(Chatbot)", 12.4),
    ("/incidents\n& reports", 15.6),
    ("/admin\n& demo", 18.4),
]
for name, cx in gw_items:
    rbox(ax1, cx, 8.2, 2.8, 1.0, name, C_GW, E_GW, fs=7.8)

# arrow: Frontend → Gateway
for cx in [2.8, 6.0, 9.2, 12.4, 15.6, 18.4]:
    arr(ax1, cx, 10.25, cx, 8.7)

# ── SCORING ENGINE (central hub) ──
rbox(ax1, 10.0, 6.35, 3.2, 0.85, "Hybrid Scoring Engine\n0.75 x AI + 0.25 x Rules", "#1a2d1a", E_GW, fs=8, bold=True)

# Gateway → Scoring Engine
arr(ax1, 6.0, 7.7, 9.0, 6.55)
arr(ax1, 10.0, 7.7, 10.0, 6.78)
arr(ax1, 15.6, 7.7, 11.6, 6.55)

# ── ML LAYER boxes ──
ml_items = [
    ("Phishing Email\nTF-IDF + Ensemble\n(LR + RF)",    2.2, 5.35),
    ("URL Heuristics\nRule-based\nDomain analysis",      5.4, 5.35),
    ("QR Decoder\nPyzbar + URL\nheuristics",             8.3, 5.35),
    ("Audio Deepfake\nCNN on Mel-Spec\n(TF / PyTorch)", 11.5, 5.35),
    ("Video Deepfake\nFrame CNN +\nFace crop",          14.7, 5.35),
    ("Groq LLM\n(Qwen3.8-27B)\nChatbot / Quiz",        17.8, 5.35),
]
for name, cx, cy in ml_items:
    rbox(ax1, cx, cy, 2.9, 1.05, name, C_ML, E_ML, fs=7.5)
    arr(ax1, cx, cy+0.53, cx if abs(cx-10)<3.5 else cx, 6.28 if abs(cx-10)<3.5 else 6.35,
        col=E_ML, lw=1.2)

# Scoring engine → Prevention
rbox(ax1, 10.0, 4.38, 3.2, 0.65, "Prevention Engine\nALLOW / WARN / QUARANTINE / BLOCK", "#1a2d1a", E_GW, fs=8)
arr(ax1, 10.0, 5.93, 10.0, 4.71)

# ── DATA LAYER ──
db_items = [
    ("Users &\nAuth Tokens",  1.4, 2.6),
    ("Analysis\nResults",     3.8, 2.6),
    ("Incidents\nLog",        6.2, 2.6),
    ("Quizzes &\nScenarios",  8.1-0.3, 2.6),
]
for name, cx, cy in db_items:
    rbox(ax1, cx, cy, 2.1, 0.75, name, C_DB, E_DB, fs=7.5)

# Gateway → DB
arr(ax1, 4.5, 7.5, 4.5, 3.0, col=E_DB, lw=1.0)

# ── EXTERNAL SERVICES ──
ext_items = [
    ("SMTP\n(Resend)",    10.2, 2.65),
    ("Groq API\nCloud",   12.8, 2.65),
    ("MQTT\nSimulation",  15.4, 2.65),
    ("PostgreSQL\n(Prod)",18.0, 2.65),
]
for name, cx, cy in ext_items:
    rbox(ax1, cx, cy, 2.2, 0.75, name, C_EXT, E_EXT, fs=7.5)

# Gateway → External
arr(ax1, 12.0, 7.5, 12.0, 3.1, col=ARROW, lw=1.0)

# ── User icon ──
ax1.text(0.7, 10.75, "User\nBrowser", ha="center", va="center",
         fontsize=7.5, color=MUTED)
arr(ax1, 1.1, 10.75, 1.5, 10.75)

plt.tight_layout(pad=0.3)
fig1.savefig(r"c:\Users\ADMIN\OneDrive\Desktop\capstone\cybershield-ai-main\fig4_1_architecture.png",
             dpi=180, bbox_inches="tight", facecolor=BG)
plt.close(fig1)
print("Saved fig4_1_architecture.png")


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 4.2 — METHODOLOGY BLOCK DIAGRAM
# ════════════════════════════════════════════════════════════════════════════
fig2, ax2 = plt.subplots(figsize=(18, 22))
ax2.set_xlim(0, 18); ax2.set_ylim(0, 22)
ax2.axis("off")
fig2.patch.set_facecolor(BG)
ax2.set_facecolor(BG)

ax2.text(9, 21.65, "Figure 4.2  Methodology Block Diagram", ha="center", va="top",
         fontsize=14, color=TEXT, weight="bold")
ax2.text(9, 21.3, "CyberShield AI  —  End-to-End Threat Detection Methodology",
         ha="center", va="top", fontsize=9, color=MUTED)

# ── colour scheme ──
C_IN   = "#1e3a5c"; E_IN   = "#3b82f6"
C_PRE  = "#1a3d2b"; E_PRE  = "#22c55e"
C_S1   = "#1e3d6b"; E_S1   = "#60a5fa"
C_S2   = "#3d1b4e"; E_S2   = "#a855f7"
C_FUS  = "#1a2d1a"; E_FUS  = "#22c55e"
C_OUT  = "#1e293b"; E_OUT  = "#94a3b8"
C_ACT  = "#7f1d1d"; E_ACT  = "#ef4444"
C_SAFE = "#14532d"; E_SAFE = "#22c55e"
C_WARN = "#713f12"; E_WARN = "#f59e0b"

# ── STEP 1: INPUT COLLECTION ──
band(ax2, 0.3, 19.0, 17.4, 1.85, "STEP 1  -  Input Collection & Validation", C_IN, E_IN)
rbox(ax2, 3.5, 19.7, 2.8, 0.8,  "Email\n(subject, body,\nsender, URLs)", C_IN, E_IN, fs=8)
rbox(ax2, 6.5, 19.7, 2.8, 0.8,  "URL / QR Code\n(raw string\nor image)", C_IN, E_IN, fs=8)
rbox(ax2, 9.5, 19.7, 2.8, 0.8,  "Audio File\n(WAV/MP3\nmax 10 MB)", C_IN, E_IN, fs=8)
rbox(ax2, 12.5, 19.7, 2.8, 0.8, "Video File\n(MP4/AVI\nmax 50 MB)", C_IN, E_IN, fs=8)
rbox(ax2, 15.5-0.5+0.8, 19.7, 2.2, 0.8, "Image\n(PNG/JPG\nmax 5 MB)", C_IN, E_IN, fs=8)

for cx in [3.5, 6.5, 9.5, 12.5, 15.8]:
    arr(ax2, cx, 19.3, cx, 18.9, col=E_IN)

# ── STEP 2: PRE-PROCESSING ──
band(ax2, 0.3, 16.7, 17.4, 2.0, "STEP 2  -  Pre-Processing", C_PRE, E_PRE)
rbox(ax2, 3.5, 17.5, 2.8, 0.85, "Text Cleaning\n+\nUrgency Extraction", C_PRE, E_PRE, fs=8)
rbox(ax2, 6.5, 17.5, 2.8, 0.85, "URL Parsing\n+\nDomain Tokenisation", C_PRE, E_PRE, fs=8)
rbox(ax2, 9.5, 17.5, 2.8, 0.85, "Mel-Spectrogram\n(128 x 128)\n16 kHz resample", C_PRE, E_PRE, fs=8)
rbox(ax2, 12.5, 17.5, 2.8, 0.85,"Frame Extraction\n1 FPS + Face Crop\n128 x 128", C_PRE, E_PRE, fs=8)
rbox(ax2, 15.8, 17.5, 2.2, 0.85,"Face Detect\n+\nResize", C_PRE, E_PRE, fs=8)

for cx in [3.5, 6.5, 9.5, 12.5, 15.8]:
    arr(ax2, cx, 18.9, cx, 17.93, col=E_PRE)
    arr(ax2, cx, 17.08, cx, 16.7, col=E_PRE)

# ── STEP 3: STAGE 1 — RULE-BASED ──
band(ax2, 0.3, 13.2, 17.4, 3.2, "STEP 3  -  Stage 1: Rule-Based Heuristics", C_S1, E_S1)

rbox(ax2, 3.5, 15.7, 2.8, 1.0,
     "Text Risk Score\nUrgency x0.40\nURL risk x0.35\nSender x0.25", C_S1, E_S1, fs=7.5)
rbox(ax2, 6.5, 15.7, 2.8, 1.0,
     "URL Heuristics\nIP domain | TLD\nSubdomains\nTyposquatting", C_S1, E_S1, fs=7.5)
rbox(ax2, 9.5, 15.7, 2.8, 1.0,
     "Silence Ratio\nZero-crossing\nMFCC variance\nPitch anomaly", C_S1, E_S1, fs=7.5)
rbox(ax2, 12.5, 15.7, 2.8, 1.0,
     "Frame Variance\nOptical flow\nCompression\nartefacts", C_S1, E_S1, fs=7.5)
rbox(ax2, 15.8, 15.7, 2.2, 1.0,
     "Face symmetry\nBlur metric\nColour dist.", C_S1, E_S1, fs=7.5)

for cx in [3.5, 6.5, 9.5, 12.5, 15.8]:
    arr(ax2, cx, 16.7, cx, 16.2, col=E_S1)
    arr(ax2, cx, 15.2, cx, 14.5, col=E_S1)

rbox(ax2, 9.0, 14.0, 13.8, 0.65, "Rule Scores  [0-1]  for each modality", C_S1, E_S1, fs=8.5, bold=True)
arr(ax2, 9.0, 13.67, 9.0, 13.2, col=E_S1)

# ── STEP 4: STAGE 2 — ML ──
band(ax2, 0.3, 9.8, 17.4, 3.1, "STEP 4  -  Stage 2: ML / AI Inference", C_S2, E_S2)

rbox(ax2, 3.5, 12.0, 2.8, 1.0,
     "TF-IDF Vectorizer\n(10K features)\nLR + RF Ensemble\nP(phishing)", C_S2, E_S2, fs=7.5)
rbox(ax2, 6.5, 12.0, 2.8, 1.0,
     "Blocklist check\n+ heuristic\nscore reused\nas AI score", C_S2, E_S2, fs=7.5)
rbox(ax2, 9.5, 12.0, 2.8, 1.0,
     "CNN on\nMel-Spectrograms\n(TF / PyTorch)\nP(synthetic)", C_S2, E_S2, fs=7.5)
rbox(ax2, 12.5, 12.0, 2.8, 1.0,
     "Frame CNN\nFace-crop input\n(TF / PyTorch)\nP(deepfake)", C_S2, E_S2, fs=7.5)
rbox(ax2, 15.8, 12.0, 2.2, 1.0,
     "Image CNN\nFace crop\nP(deepfake)", C_S2, E_S2, fs=7.5)

for cx in [3.5, 6.5, 9.5, 12.5, 15.8]:
    arr(ax2, cx, 13.2, cx, 12.5, col=E_S2)
    arr(ax2, cx, 11.5, cx, 10.5, col=E_S2)

rbox(ax2, 9.0, 10.1, 13.8, 0.65, "AI Probabilities  [0-1]  for each modality", C_S2, E_S2, fs=8.5, bold=True)
arr(ax2, 9.0, 9.77, 9.0, 9.8, col=E_S2)

# ── STEP 5: FUSION ──
band(ax2, 0.3, 7.3, 17.4, 2.2, "STEP 5  -  Hybrid Fusion  (Scoring Engine)", C_FUS, E_FUS)

rbox(ax2, 9.0, 8.8, 9.0, 0.7,
     "Final Score  =  0.75 x AI Probability  +  0.25 x Rule Score", C_FUS, E_FUS, fs=9, bold=True)
arr(ax2, 9.0, 9.8, 9.0, 9.15, col=E_FUS)
arr(ax2, 9.0, 8.45, 9.0, 8.0, col=E_FUS)

rbox(ax2, 4.5, 7.7, 3.5, 0.6, "Confidence Level\n(high / medium / low)", C_FUS, E_FUS, fs=8)
rbox(ax2, 9.0, 7.7, 3.5, 0.6, "Calibration Note\n(shown if uncertain)", C_FUS, E_FUS, fs=8)
rbox(ax2, 13.5, 7.7, 3.5, 0.6, "Contributing\nFactors list", C_FUS, E_FUS, fs=8)

arr(ax2, 9.0, 8.0, 4.5, 7.95, col=E_FUS, lw=1.0)
arr(ax2, 9.0, 8.0, 13.5, 7.95, col=E_FUS, lw=1.0)

arr(ax2, 9.0, 7.3, 9.0, 6.9, col=E_FUS)

# ── STEP 6: DECISION ──
diam(ax2, 9.0, 6.45, 6.0, 0.85, "Score Threshold?", C_FUS, E_FUS, fs=9)

arr(ax2, 6.0, 6.45, 4.0, 6.45); label(ax2, 5.0, 6.55, "0-30", fs=8)
arr(ax2, 12.0, 6.45, 14.5, 6.45); label(ax2, 13.2, 6.55, "70-100", fs=8)
arr(ax2, 9.0, 6.03, 9.0, 5.6); label(ax2, 9.2, 5.82, "31-69", fs=8)

rbox(ax2, 3.0, 6.45, 2.2, 0.65, "SAFE", C_SAFE, E_SAFE, fs=10, bold=True)
rbox(ax2, 9.0, 5.3, 2.5, 0.65, "SUSPICIOUS", C_WARN, E_WARN, fs=9, bold=True)
rbox(ax2, 15.5, 6.45, 2.5, 0.65, "DANGEROUS", C_ACT, E_ACT, fs=9, bold=True)

# ── STEP 7: PREVENTION ──
arr(ax2, 3.0, 6.12, 3.0, 5.3)
arr(ax2, 9.0, 4.97, 9.0, 4.5)
arr(ax2, 15.5, 6.12, 15.5, 5.3)

rbox(ax2, 3.0, 4.97, 2.2, 0.6, "ALLOW", C_SAFE, E_SAFE, fs=9, bold=True)
rbox(ax2, 9.0, 4.17, 2.5, 0.6, "WARN /\nRESTRICT", C_WARN, E_WARN, fs=8.5, bold=True)
rbox(ax2, 15.5, 4.97, 2.5, 0.6, "QUARANTINE\n/ BLOCK", C_ACT, E_ACT, fs=8.5, bold=True)

# ── STEP 8: EXPLAINABILITY ──
band(ax2, 0.3, 2.5, 17.4, 1.9, "STEP 6  -  Explainability & Persistence", C_IN, E_IN)

rbox(ax2, 3.5, 3.35, 2.8, 0.9, "Explanation\nSummary\n+ Highlights", C_IN, E_IN, fs=8)
rbox(ax2, 7.0, 3.35, 2.8, 0.9, "Flagged\nPhrases\n& URLs", C_IN, E_IN, fs=8)
rbox(ax2, 10.5, 3.35, 2.8, 0.9, "Incident\nLog\n(DB persist)", C_IN, E_IN, fs=8)
rbox(ax2, 14.0, 3.35, 2.8, 0.9, "PDF Report\n+\nEmail Alert", C_IN, E_IN, fs=8)

# prevention → explainability
for src, dst in [(3.0, 3.5), (9.0, 9.0), (15.5, 14.0)]:
    arr(ax2, src, 4.17 if src==9.0 else 4.67, dst, 3.8, col=E_IN, lw=1.0)

# ── STEP 9: FINAL RESPONSE ──
arr(ax2, 9.0, 2.5, 9.0, 2.15)
rbox(ax2, 9.0, 1.82, 13.0, 0.65,
     "JSON Response  ->  risk_score | risk_label | explanation | highlights | flagged_urls | action",
     C_IN, E_IN, fs=8.5, bold=True)

plt.tight_layout(pad=0.3)
fig2.savefig(r"c:\Users\ADMIN\OneDrive\Desktop\capstone\cybershield-ai-main\fig4_2_methodology.png",
             dpi=180, bbox_inches="tight", facecolor=BG)
plt.close(fig2)
print("Saved fig4_2_methodology.png")
