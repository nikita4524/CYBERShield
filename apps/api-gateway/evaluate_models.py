"""
CyberShield AI — Email Phishing Model + URL/QR Engine Evaluation
================================================================
Tasks covered:
  1. Inspect model internals
  2. 80/20 split retrain → Accuracy / Precision / Recall / F1 / Confusion Matrix
  3. Test 10 brand-new unseen emails (never in training data)
  4. Test 15 unseen URLs across safe / suspicious / dangerous
  5. Live API tests for /analyze/email and /analyze/url
  6. Final report with all problems found

Run from apps/api-gateway/:
    python evaluate_models.py
"""

import sys
import json
import pickle
import warnings
import textwrap
import traceback
import os

warnings.filterwarnings("ignore")
sys.path.insert(0, ".")

# ── colour helpers (ANSI) ─────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; RST = "\033[0m"
def ok(s):   return f"{G}PASS{RST}  {s}"
def fail(s): return f"{R}FAIL{RST}  {s}"
def warn(s): return f"{Y}WARN{RST}  {s}"
def hdr(s):  return f"\n{B}{'='*70}\n  {s}\n{'='*70}{RST}"

# ─────────────────────────────────────────────────────────────────
# TASK 1 — Inspect model internals
# ─────────────────────────────────────────────────────────────────
print(hdr("TASK 1 — Model Internals Inspection"))

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
VEC_PATH  = os.path.join(MODEL_DIR, "phishing_tfidf_vectorizer.pkl")
CLF_PATH  = os.path.join(MODEL_DIR, "phishing_classifier.pkl")

try:
    with open(VEC_PATH, "rb") as f: vectorizer = pickle.load(f)
    with open(CLF_PATH, "rb") as f: classifier = pickle.load(f)

    vocab_size = len(vectorizer.vocabulary_)
    ngram      = vectorizer.ngram_range
    max_feat   = vectorizer.max_features
    clf_type   = type(classifier).__name__
    estimators = getattr(classifier, "estimators_", None)
    est_names  = [type(e).__name__ for e in estimators] if estimators else ["n/a"]

    print(f"  Vectorizer  : TfidfVectorizer")
    print(f"  Vocab size  : {vocab_size} tokens  (max_features={max_feat})")
    print(f"  N-gram range: {ngram}")
    print(f"  Classifier  : {clf_type}")
    print(f"  Sub-models  : {', '.join(est_names)}")

    # Try to get training sample count from shape
    try:
        import numpy as np
        dummy = vectorizer.transform(["test"])
        print(f"  Feature dim : {dummy.shape[1]}")
    except Exception: pass

    print(f"\n  {ok('Both model files loaded successfully')}")
except Exception as e:
    print(f"  {fail(str(e))}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────
# Training data (exact 40 samples from phish_model.py create_demo_model)
# We use this ONLY to know what NOT to put in our test set.
# ─────────────────────────────────────────────────────────────────
TRAINING_DATA = {
    "phishing": [
        "urgent your account has been suspended click here to verify immediately your account will be blocked",
        "dear customer verify your sbi account kyc update required enter password",
        "congratulations you have won prize money claim your reward click link",
        "URGENT security alert your hdfc bank account login credentials required",
        "your account will be suspended within 24 hours complete kyc verification",
        "dear user your otp for transaction enter your otp immediately",
        "income tax refund approved click here to claim your tds refund",
        "suspicious activity detected on your account verify now to avoid suspension",
        "your debit card has been blocked enter card details to unblock",
        "limited time offer claim your cashback verify upi id now",
        "dear customer your kyc has expired update immediately or account will close",
        "click here to verify your credentials account blocking in 24 hours urgent",
        "unauthorized access detected on your account confirm your password now",
        "your sbi net banking will be suspended verify your account immediately",
        "government scheme cashback verify upi account claim money now",
        "enter your credit card cvv number to complete verification process",
        "you have been selected for insurance claim verify your aadhaar pan",
        "loan approved instantly transfer fee to receive amount enter bank details",
        "your phone number is linked to fraud unlink by sharing otp immediately",
        "gpay phonepe paytm cashback offer verify account get reward now",
    ],
    "safe": [
        "your account statement for january is ready please check online banking",
        "thank you for your transaction payment successful amount debited",
        "your fixed deposit has matured please contact branch for renewal",
        "meeting scheduled for tomorrow please review the attached agenda",
        "your order has been shipped tracking number provided below",
        "newsletter january 2024 new features updates from our team",
        "reminder your emi payment is due on 15th of this month",
        "your card ending 1234 was used for transaction at amazon",
        "welcome to our service your account has been created successfully",
        "please find attached the quarterly report for your review",
        "your appointment has been confirmed for tomorrow at 10am",
        "thank you for contacting customer support ticket number created",
        "your subscription renewal is due next month current plan active",
        "important announcement upcoming maintenance scheduled for weekend",
        "your profile has been updated successfully changes will reflect shortly",
        "invoice number 12345 payment received thank you for your business",
        "your request has been processed successfully please allow 24 hours",
        "new security feature enabled two factor authentication is now active",
        "your salary has been credited account balance updated successfully",
        "greetings from our team wishing you a happy new year ahead",
    ],
}

# ─────────────────────────────────────────────────────────────────
# TASK 2 — 80/20 train-test split + metrics
# ─────────────────────────────────────────────────────────────────
print(hdr("TASK 2 — 80/20 Split Retrain + Evaluation Metrics"))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)
import numpy as np

X_all = TRAINING_DATA["phishing"] + TRAINING_DATA["safe"]
y_all = [1] * len(TRAINING_DATA["phishing"]) + [0] * len(TRAINING_DATA["safe"])

X_train, X_test, y_train, y_test = train_test_split(
    X_all, y_all, test_size=0.20, random_state=42, stratify=y_all
)

print(f"  Total samples : {len(X_all)}  (phishing={sum(y_all)}, safe={len(y_all)-sum(y_all)})")
print(f"  Train set     : {len(X_train)} samples")
print(f"  Test set      : {len(X_test)}  samples")
print(f"  Test labels   : phishing={sum(y_test)}, safe={len(y_test)-sum(y_test)}")

# Retrain on 80%
vec_80 = TfidfVectorizer(
    max_features=10000, ngram_range=(1,2), min_df=1,
    max_df=0.95, strip_accents="unicode", lowercase=True, sublinear_tf=True,
)
X_tr_vec = vec_80.fit_transform(X_train)
X_te_vec = vec_80.transform(X_test)

lr = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
clf_80 = VotingClassifier(estimators=[("lr", lr), ("rf", rf)], voting="soft")
clf_80.fit(X_tr_vec, y_train)

y_pred = clf_80.predict(X_te_vec)
y_prob = clf_80.predict_proba(X_te_vec)[:, 1]

acc  = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred, zero_division=0)
rec  = recall_score(y_test, y_pred, zero_division=0)
f1   = f1_score(y_test, y_pred, zero_division=0)
cm   = confusion_matrix(y_test, y_pred)

print(f"\n  {'Metric':<12} {'Value':>8}")
print(f"  {'-'*22}")
print(f"  {'Accuracy':<12} {acc:>8.4f}  ({acc*100:.1f}%)")
print(f"  {'Precision':<12} {prec:>8.4f}")
print(f"  {'Recall':<12} {rec:>8.4f}")
print(f"  {'F1-Score':<12} {f1:>8.4f}")

print(f"\n  Confusion Matrix:")
print(f"                 Predicted")
print(f"                 Safe    Phish")
print(f"  Actual Safe  [ {cm[0][0]:>4}    {cm[0][1]:>4} ]")
print(f"  Actual Phish [ {cm[1][0]:>4}    {cm[1][1]:>4} ]")
tn,fp,fn,tp = cm.ravel()
print(f"\n  True Negatives (safe→safe)   : {tn}")
print(f"  False Positives (safe→phish) : {fp}  {'⚠️ False alarms' if fp>0 else '✅'}")
print(f"  False Negatives (phish→safe) : {fn}  {'⚠️ Missed phish' if fn>0 else '✅'}")
print(f"  True Positives (phish→phish) : {tp}")

print(f"\n  Per-sample breakdown (test set):")
print(f"  {'Label':<8} {'Predicted':<12} {'Prob':>6}  {'Status':<6}  Text (first 60 chars)")
print(f"  {'-'*85}")
for xi, (text, true, pred, prob) in enumerate(zip(X_test, y_test, y_pred, y_prob)):
    true_s = "phish" if true == 1 else "safe"
    pred_s = "phish" if pred == 1 else "safe"
    status = "✅" if true == pred else "❌"
    snippet = text[:60].replace("\n", " ")
    print(f"  {true_s:<8} {pred_s:<12} {prob:>6.3f}  {status}      {snippet}")

# Overall verdict
if f1 >= 0.90:
    print(f"\n  {ok(f'F1={f1:.3f} — model generalises well on its own split')}")
elif f1 >= 0.70:
    print(f"\n  {warn(f'F1={f1:.3f} — acceptable but small dataset limits confidence')}")
else:
    print(f"\n  {fail(f'F1={f1:.3f} — model struggles even on its own data split')}")

# ─────────────────────────────────────────────────────────────────
# TASK 3 — 10 brand-new unseen email samples
# ─────────────────────────────────────────────────────────────────
print(hdr("TASK 3 — 10 Unseen Email Samples (never in training data)"))

# These are written fresh — NOT paraphrases of training samples.
# Different phrasing, scenarios, Indian context variety.
UNSEEN_EMAILS = [
    # ── 5 phishing (label=1) ──────────────────────────────────
    {
        "label": 1, "type": "phishing",
        "subject": "Your PAN card is linked to illegal transactions",
        "body": "Dear taxpayer, CBDT has flagged your PAN card for suspicious transactions worth Rs 4.5 lakh. You must submit your Aadhaar number and bank details within 2 hours to avoid arrest. Click http://cbdt-verify.xyz/pan to comply.",
        "sender": "notice@cbdt-india.xyz",
    },
    {
        "label": 1, "type": "phishing",
        "subject": "Exclusive: Double your investment via government crypto scheme",
        "body": "Honorable citizen, PM Digital India has launched a new crypto investment scheme. Send Rs 5000 via UPI to receive Rs 10000 back within 24 hours. This is a limited offer. UPI ID: pmscheme@ybl. Share your transaction screenshot to claim.",
        "sender": "offers@pm-digitalindia.net",
    },
    {
        "label": 1, "type": "phishing",
        "subject": "IRCTC Account Suspended – Immediate Action Required",
        "body": "Your IRCTC account has been suspended due to multiple failed login attempts. To restore access, verify your identity by entering your username, password, and date of birth at http://irctc-restore.online/verify. Failure to verify within 6 hours will result in permanent deletion.",
        "sender": "support@irctc-restore.online",
    },
    {
        "label": 1, "type": "phishing",
        "subject": "You have a pending KYC on your Jio number",
        "body": "Dear Jio customer, your mobile number will be deactivated in 24 hours as your KYC documents are incomplete. Download the attached form and share your Aadhaar front and back photos along with your OTP to noreply@jio-kyc-update.com to avoid disconnection.",
        "sender": "noreply@jio-kyc-update.com",
    },
    {
        "label": 1, "type": "phishing",
        "subject": "Prize Winner: Rs 25 Lakh Amazon Lucky Draw",
        "body": "Congratulations! Your mobile number has been selected as a winner in the Amazon India 25th Anniversary Lucky Draw. You have won Rs 25,00,000. To claim your prize, pay a processing fee of Rs 1850 to our agent via PhonePe: 9876543210. Contact Mr. Sharma at 8800112233.",
        "sender": "winner@amazon-lucky-india.com",
    },
    # ── 5 legitimate (label=0) ───────────────────────────────
    {
        "label": 0, "type": "safe",
        "subject": "Your Zerodha account statement for March 2025",
        "body": "Dear Investor, please find attached your consolidated account statement for March 2025. Your portfolio value as of 31 March 2025 is Rs 1,42,850. For any queries, log in to kite.zerodha.com or call 080-40402020.",
        "sender": "statements@zerodha.com",
    },
    {
        "label": 0, "type": "safe",
        "subject": "Team outing confirmed for Friday",
        "body": "Hi everyone, just confirming our team outing this Friday at 6pm. We will meet at the main lobby. Dinner is arranged at Barbeque Nation, Koramangala. Please confirm your attendance by replying to this email. See you all there!",
        "sender": "hr.events@techcorp.in",
    },
    {
        "label": 0, "type": "safe",
        "subject": "NEFT transfer of Rs 45,000 credited to your account",
        "body": "Dear Account Holder, a NEFT transfer of Rs 45,000 has been successfully credited to your savings account ending 7823 on 15-Mar-2025 at 14:32 IST. Available balance: Rs 78,340. If you did not initiate this, please call 1800-200-3000.",
        "sender": "alerts@icicibank.com",
    },
    {
        "label": 0, "type": "safe",
        "subject": "Your Swiggy order #SW2094821 is on the way",
        "body": "Your order from Burger King has been picked up by your delivery partner Ravi. Estimated delivery: 25 minutes. Track your order live in the Swiggy app. Order total: Rs 485. Payment: Paid via UPI.",
        "sender": "no-reply@swiggy.in",
    },
    {
        "label": 0, "type": "safe",
        "subject": "Quarterly security review — please update your password",
        "body": "Hi, as part of our quarterly IT security review, all employees are requested to update their corporate portal password by 31st March. Please log in to internal.company.com using your existing credentials and update your password under Settings > Security. Contact IT helpdesk at ext 1234 for assistance.",
        "sender": "it-security@company.com",
    },
]

# Evaluate using the FULL model (trained on all 40 samples) — production model
print(f"  Evaluating {len(UNSEEN_EMAILS)} unseen emails using the production model (all 40 training samples)\n")

from utils.text_preprocessing import build_combined_text

unseen_labels, unseen_preds, unseen_probs = [], [], []

print(f"  {'#':<3} {'Type':<9} {'Pred':<9} {'Prob':>6}  {'ML':>5}  {'Status'}  Subject")
print(f"  {'-'*90}")

for i, sample in enumerate(UNSEEN_EMAILS, 1):
    combined = build_combined_text(
        sample["subject"], sample["body"],
        sample["sender"], []
    )
    vec = vectorizer.transform([combined])
    proba = classifier.predict_proba(vec)[0]
    prob_phish = float(proba[1]) if len(proba) > 1 else float(proba[0])
    pred = 1 if prob_phish >= 0.50 else 0

    unseen_labels.append(sample["label"])
    unseen_preds.append(pred)
    unseen_probs.append(prob_phish)

    true_s = sample["type"]
    pred_s = "phish" if pred == 1 else "safe"
    status = "✅" if pred == sample["label"] else "❌ WRONG"
    subj   = sample["subject"][:55]
    print(f"  {i:<3} {true_s:<9} {pred_s:<9} {prob_phish:>6.3f}  {'ML':>5}  {status:<8}  {subj}")

# Metrics on unseen set
u_acc  = accuracy_score(unseen_labels, unseen_preds)
u_prec = precision_score(unseen_labels, unseen_preds, zero_division=0)
u_rec  = recall_score(unseen_labels, unseen_preds, zero_division=0)
u_f1   = f1_score(unseen_labels, unseen_preds, zero_division=0)
u_cm   = confusion_matrix(unseen_labels, unseen_preds)

print(f"\n  Unseen Email Metrics:")
print(f"  {'Accuracy':<12}: {u_acc:.4f}  ({u_acc*100:.1f}%)")
print(f"  {'Precision':<12}: {u_prec:.4f}")
print(f"  {'Recall':<12}: {u_rec:.4f}")
print(f"  {'F1-Score':<12}: {u_f1:.4f}")
print(f"\n  Confusion Matrix (unseen):")
u_tn,u_fp,u_fn,u_tp = u_cm.ravel()
print(f"  True Negatives (safe→safe)   : {u_tn}")
print(f"  False Positives (safe→phish) : {u_fp}  {'⚠️' if u_fp>0 else '✅'}")
print(f"  False Negatives (phish→safe) : {u_fn}  {'⚠️ MISSED PHISHING' if u_fn>0 else '✅'}")
print(f"  True Positives (phish→phish) : {u_tp}")

# ─────────────────────────────────────────────────────────────────
# TASK 4 — URL/QR engine: 15 unseen URLs
# ─────────────────────────────────────────────────────────────────
print(hdr("TASK 4 — URL/QR Heuristic Engine: 15 Unseen URLs"))

from services.url_analyzer import url_analyzer

# Ground-truth categories: safe=0, suspicious=1, dangerous=2
URL_TEST_CASES = [
    # ── SAFE (expected score < 30) ─────────────────────────────
    {"url": "https://www.irctc.co.in/nget/train-search",     "expected": "safe",       "note": "Legit IRCTC"},
    {"url": "https://www.zerodha.com/portfolio",             "expected": "safe",       "note": "Legit broker"},
    {"url": "https://www.npci.org.in/what-we-do/upi",       "expected": "safe",       "note": "Legit NPCI"},
    {"url": "https://incometax.gov.in/iec/foportal/",        "expected": "safe",       "note": "Legit govt"},
    {"url": "https://github.com/cybershield/repo",           "expected": "safe",       "note": "Legit github"},
    # ── SUSPICIOUS (expected 30–69) ────────────────────────────
    {"url": "https://new-fintech-startup-india.com/invest",  "expected": "suspicious", "note": "Unknown domain"},
    {"url": "https://bit.ly/3mKxPqR",                       "expected": "suspicious", "note": "URL shortener"},
    {"url": "https://mybank-customer-portal.info/login",     "expected": "suspicious", "note": "Suspicious TLD + keywords"},
    {"url": "https://tax-refund-portal.online/claim",        "expected": "suspicious", "note": "Suspicious TLD"},
    {"url": "https://secure.payments-india.net/upi",         "expected": "suspicious", "note": "Unknown + keywords"},
    # ── DANGEROUS (expected ≥ 70) ──────────────────────────────
    {"url": "http://sbi-kyc-alert.xyz/update",               "expected": "dangerous",  "note": "SBI abuse + .xyz + HTTP"},
    {"url": "http://192.168.100.50/hdfc/login",              "expected": "dangerous",  "note": "IP address + bank"},
    {"url": "http://icici-netbanking-verify.tk/confirm",     "expected": "dangerous",  "note": "ICICI abuse + .tk + HTTP"},
    {"url": "javascript:document.cookie",                    "expected": "dangerous",  "note": "Dangerous scheme"},
    {"url": "http://crackspider.us/toolbar/install.php",     "expected": "dangerous",  "note": "In blocklist (ISCX dataset)"},
]

def score_to_label(score):
    if score < 30:   return "safe"
    if score >= 70:  return "dangerous"
    return "suspicious"

url_labels, url_preds = [], []
label_map = {"safe": 0, "suspicious": 1, "dangerous": 2}

print(f"  {'#':<3} {'Expected':<12} {'Got':<12} {'Score':>6}  {'Status':<8}  Note / Top flag")
print(f"  {'-'*90}")

for i, tc in enumerate(URL_TEST_CASES, 1):
    r = url_analyzer.analyze(tc["url"])
    score = int(round(r.probability * 100))
    got   = score_to_label(score)
    exp   = tc["expected"]
    status = "✅" if got == exp else "❌ WRONG"
    top_flag = r.flags[0] if r.flags else "none"
    url_labels.append(label_map[exp])
    url_preds.append(label_map[got])
    note = tc["note"]
    print(f"  {i:<3} {exp:<12} {got:<12} {score:>6}  {status:<8}  {note} [{top_flag}]")

# Per-category accuracy
for cat, cid in label_map.items():
    indices = [j for j,l in enumerate(url_labels) if l == cid]
    correct = sum(1 for j in indices if url_preds[j] == cid)
    total   = len(indices)
    pct     = correct/total*100 if total else 0
    marker  = "✅" if pct == 100 else ("⚠️" if pct >= 60 else "❌")
    print(f"\n  {cat.upper()} accuracy : {correct}/{total} ({pct:.0f}%) {marker}")

overall_url_acc = sum(1 for a,b in zip(url_labels,url_preds) if a==b) / len(url_labels)
print(f"\n  Overall URL accuracy: {overall_url_acc*100:.1f}%  ({sum(1 for a,b in zip(url_labels,url_preds) if a==b)}/{len(url_labels)})")

# ─────────────────────────────────────────────────────────────────
# TASK 5 — Live API tests
# ─────────────────────────────────────────────────────────────────
print(hdr("TASK 5 — Live API Tests"))

import urllib.request
import urllib.error
import json as jsonlib

API = "http://localhost:8000/api/v1"

def api_post(path, payload, timeout=20):
    url  = f"{API}{path}"
    data = jsonlib.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return jsonlib.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        return None, f"HTTP {e.code}: {body}"
    except Exception as ex:
        return None, str(ex)

# ── 5a: Email API ──────────────────────────────────────────────
print("\n  5a — /analyze/email (4 samples: 2 phishing, 2 safe)\n")

EMAIL_API_TESTS = [
    {
        "subject": "Your PAN card is linked to illegal transactions",
        "body": "Dear taxpayer, CBDT has flagged your PAN card. Submit Aadhaar and bank details within 2 hours to avoid arrest.",
        "sender": "notice@cbdt-india.xyz",
        "urls": ["http://cbdt-verify.xyz/pan"],
        "expected": "dangerous", "type": "phishing",
    },
    {
        "subject": "You have a pending KYC on your Jio number",
        "body": "Your Jio number will be deactivated in 24 hours. Share your Aadhaar photos and OTP to avoid disconnection.",
        "sender": "noreply@jio-kyc-update.com",
        "urls": [],
        "expected": "dangerous", "type": "phishing",
    },
    {
        "subject": "Your Zerodha account statement for March 2025",
        "body": "Dear Investor, your portfolio value is Rs 1,42,850. Log in to kite.zerodha.com for details.",
        "sender": "statements@zerodha.com",
        "urls": ["https://kite.zerodha.com"],
        "expected": "safe", "type": "safe",
    },
    {
        "subject": "NEFT transfer of Rs 45,000 credited to your account",
        "body": "A NEFT transfer of Rs 45,000 has been credited to your savings account ending 7823. Balance: Rs 78,340.",
        "sender": "alerts@icicibank.com",
        "urls": [],
        "expected": "safe", "type": "safe",
    },
]

email_api_pass = 0
print(f"  {'#':<3} {'Type':<9} {'Expected':<12} {'Got':<12} {'Score':>6}  {'Action':<12} Status")
print(f"  {'-'*75}")
for i, t in enumerate(EMAIL_API_TESTS, 1):
    payload = {"subject": t["subject"], "body": t["body"],
               "sender": t["sender"], "urls": t["urls"]}
    resp, err = api_post("/analyze/email", payload)
    if err:
        print(f"  {i:<3} {t['type']:<9} {t['expected']:<12} {'ERR':<12}      -  {'':<12} ❌  {err[:50]}")
    else:
        got    = resp.get("risk_label", "?")
        score  = resp.get("risk_score", -1)
        action = resp.get("action", "?")
        status = "✅" if got == t["expected"] else "❌ WRONG"
        if got == t["expected"]: email_api_pass += 1
        print(f"  {i:<3} {t['type']:<9} {t['expected']:<12} {got:<12} {score:>6}  {action:<12} {status}")

print(f"\n  Email API: {email_api_pass}/{len(EMAIL_API_TESTS)} correct")

# ── 5b: URL API ──────────────────────────────────────────────
print("\n  5b — /analyze/url (5 samples)\n")

URL_API_TESTS = [
    {"url": "https://www.irctc.co.in/nget/train-search", "expected": "safe"},
    {"url": "https://bit.ly/3mKxPqR",                   "expected": "suspicious"},
    {"url": "http://sbi-kyc-alert.xyz/update",           "expected": "dangerous"},
    {"url": "http://192.168.100.50/hdfc/login",          "expected": "dangerous"},
    {"url": "javascript:document.cookie",                "expected": "dangerous"},
]

url_api_pass = 0
print(f"  {'#':<3} {'Expected':<12} {'Got':<12} {'Score':>6}  {'Action':<12} URL")
print(f"  {'-'*85}")
for i, t in enumerate(URL_API_TESTS, 1):
    resp, err = api_post("/analyze/url", {"url": t["url"]})
    if err:
        print(f"  {i:<3} {t['expected']:<12} {'ERR':<12}      -  {'':<12} {t['url'][:40]}  ❌  {err[:40]}")
    else:
        got    = resp.get("risk_label", "?")
        score  = resp.get("risk_score", -1)
        action = resp.get("action", "?")
        status = "✅" if got == t["expected"] else "❌ WRONG"
        if got == t["expected"]: url_api_pass += 1
        print(f"  {i:<3} {t['expected']:<12} {got:<12} {score:>6}  {action:<12} {t['url'][:40]}  {status}")

print(f"\n  URL API: {url_api_pass}/{len(URL_API_TESTS)} correct")

# ─────────────────────────────────────────────────────────────────
# TASK 6 — Final Report
# ─────────────────────────────────────────────────────────────────
print(hdr("TASK 6 — Final Report & Problems Found"))

print(f"""
  ┌─────────────────────────────────────────────────────────────────┐
  │  EMAIL PHISHING MODEL                                           │
  ├─────────────────────────────────────────────────────────────────┤
  │  Training set size       : 40 samples (20 phishing + 20 safe)  │
  │  Vocabulary size         : {vocab_size:<6} tokens                       │
  │  Classifier              : VotingClassifier (LR + RF)          │
  │                                                                 │
  │  80/20 Split Metrics (on held-out training subset):            │
  │    Accuracy  : {acc*100:>5.1f}%                                       │
  │    Precision : {prec*100:>5.1f}%                                       │
  │    Recall    : {rec*100:>5.1f}%                                       │
  │    F1-Score  : {f1*100:>5.1f}%                                       │
  │                                                                 │
  │  Unseen Email Metrics (10 brand-new samples):                  │
  │    Accuracy  : {u_acc*100:>5.1f}%                                       │
  │    Precision : {u_prec*100:>5.1f}%                                       │
  │    Recall    : {u_rec*100:>5.1f}%                                       │
  │    F1-Score  : {u_f1*100:>5.1f}%                                       │
  │    Missed phishing (FN) : {u_fn}                                    │
  │    False alarms  (FP)   : {u_fp}                                    │
  ├─────────────────────────────────────────────────────────────────┤
  │  URL/QR ENGINE                                                  │
  ├─────────────────────────────────────────────────────────────────┤
  │  Type           : Pure heuristic (no ML training required)     │
  │  Blocklist size : 34,577 domains (ISCX 2016)                   │
  │  Overall acc    : {overall_url_acc*100:.1f}% on 15 unseen URLs               │
  └─────────────────────────────────────────────────────────────────┘
""")

print("  PROBLEMS FOUND:")
problems = []

if f1 < 0.85:
    problems.append(f"[EMAIL] 80/20 F1={f1:.2f} — model struggles on its own held-out split. Root cause: only 40 training samples total. With 80% train = 32 samples, the TF-IDF vocabulary is too sparse.")

if u_fn > 0:
    missed = [UNSEEN_EMAILS[j]["subject"] for j in range(len(UNSEEN_EMAILS)) if unseen_labels[j]==1 and unseen_preds[j]==0]
    problems.append(f"[EMAIL] {u_fn} phishing email(s) missed on unseen data:\n         → " + "\n         → ".join(missed))

if u_fp > 0:
    falsepos = [UNSEEN_EMAILS[j]["subject"] for j in range(len(UNSEEN_EMAILS)) if unseen_labels[j]==0 and unseen_preds[j]==1]
    problems.append(f"[EMAIL] {u_fp} safe email(s) wrongly flagged as phishing:\n         → " + "\n         → ".join(falsepos))

wrong_urls = [URL_TEST_CASES[j] for j in range(len(URL_TEST_CASES)) if url_labels[j] != url_preds[j]]
if wrong_urls:
    for w in wrong_urls:
        exp_s = ["safe","suspicious","dangerous"][label_map[w["expected"]]]
        got_s = ["safe","suspicious","dangerous"][url_preds[URL_TEST_CASES.index(w)]]
        problems.append(f"[URL]   '{w['url'][:60]}' expected={exp_s} got={got_s} — {w['note']}")

problems.append("[EMAIL] Training data is 40 hand-written sentences — model memorises patterns rather than generalising. Recommend retraining on SpamAssassin (6K) or Enron (500K) dataset.")
problems.append("[EMAIL] TF-IDF vocabulary has only " + str(vocab_size) + " tokens — insufficient for real-world phishing diversity.")
problems.append("[URL]   No ML model — purely heuristic. Works well for known patterns but cannot detect novel zero-day phishing domains with clean structure.")

for pi, p in enumerate(problems, 1):
    print(f"\n  {pi}. {p}")

print(f"\n  {'='*70}")
print(f"  SUMMARY: Email F1={f1:.2f} (split) / {u_f1:.2f} (unseen) | URL acc={overall_url_acc*100:.0f}%")
print(f"  {'='*70}\n")
