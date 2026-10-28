"""
Rule-based URL heuristics engine.

Used by the email phishing analyzer to score individual URLs found in
email bodies/headers. Shares the same blocklist as url_analyzer.py.

Changes from the original:
  - Blocklist check: flags any domain in the shared bad-domain list.
  - Unknown-domain baseline: non-whitelisted URLs start at 0.15 so a
    structurally clean phishing URL doesn't score 0.0 just because it
    avoids the obvious keyword traps.
  - Legitimate-domain penalty no longer goes below 0.
"""

import re
import ipaddress
from typing import Dict, List
from urllib.parse import urlparse, unquote

from utils.text_preprocessing import (
    SUSPICIOUS_TLDS,
    URL_SHORTENERS,
    LEGITIMATE_DOMAINS,
    INDIAN_BANKS,
    FINANCIAL_SCAM_PHRASES,
)


# ── Domain blocklist (shared with url_analyzer) ───────────────────

def _get_blocklist():
    """
    Return the module-level blocklist loaded by url_analyzer.
    Importing here (lazily) avoids circular imports while sharing the
    single loaded frozenset instead of reading the CSV twice.
    """
    try:
        from services.url_analyzer import _DOMAIN_BLOCKLIST
        return _DOMAIN_BLOCKLIST
    except Exception:
        return frozenset()


# Keywords that shouldn't appear in legitimate bank domains
PHISHING_DOMAIN_KEYWORDS = [
    "verify", "secure", "login", "account", "update",
    "confirm", "kyc", "alert", "notification", "banking",
    "netbank", "online", "support", "helpdesk", "customer",
]

# Unknown-domain starting score (non-whitelisted URLs)
_UNKNOWN_BASELINE = 0.15


class URLHeuristicsEngine:
    """
    Analyzes URLs using rule-based heuristics.
    Returns risk probability and detailed flags.
    """

    def analyze(self, url: str) -> Dict:
        """
        Analyze a URL and return risk assessment.

        Returns:
            {
                probability: float (0-1),
                flags: list of triggered rules,
                details: dict of analysis details,
                highlights: list of flagged elements
            }
        """
        result = {
            "probability": 0.0,
            "flags": [],
            "details": {},
            "highlights": [],
        }

        if not url:
            result["flags"].append("empty_url")
            result["probability"] = 0.70
            return result

        url = url.strip()

        # ── Parse ─────────────────────────────────────────────────
        try:
            parsed = urlparse(url)
        except Exception:
            result["flags"].append("unparseable_url")
            result["probability"] = 0.75
            return result

        domain = (parsed.hostname or parsed.netloc or "").lower()
        path = parsed.path.lower()
        query = parsed.query.lower()
        scheme = parsed.scheme.lower()

        # Remove port from domain if present (fallback for older urlparse)
        if ":" in domain:
            domain = domain.split(":")[0]

        if not domain:
            result["flags"].append("invalid_url_no_hostname")
            result["probability"] = 0.75
            result["highlights"].append({
                "type": "structure",
                "value": url[:100],
                "reason": "URL has no valid hostname",
            })
            return result

        result["details"]["domain"] = domain
        result["details"]["scheme"] = scheme
        result["details"]["path"] = path

        is_legitimate = self._is_legitimate_domain(domain)

        # Start from baseline for unknown domains
        risk_score = 0.0 if is_legitimate else _UNKNOWN_BASELINE

        # ── Blocklist check ───────────────────────────────────────
        blocklist = _get_blocklist()
        bare = domain.lstrip("www.")
        if not is_legitimate and (bare in blocklist or domain in blocklist):
            risk_score = max(risk_score, 0.85)
            result["flags"].append("blocklisted_domain")
            result["highlights"].append({
                "type": "domain",
                "value": domain,
                "reason": "Domain is on the known-malicious blocklist",
            })

        # ── Rule 1: No HTTPS ──────────────────────────────────────
        if scheme == "http":
            risk_score += 0.10
            result["flags"].append("non_https")
            result["highlights"].append({
                "type": "scheme",
                "value": "HTTP",
                "reason": "Unencrypted connection — legitimate banking sites always use HTTPS",
            })

        # ── Rule 2: IP address instead of domain ─────────────────
        if self._is_ip_address(domain):
            risk_score += 0.30
            result["flags"].append("ip_address_domain")
            result["highlights"].append({
                "type": "domain",
                "value": domain,
                "reason": "IP address used instead of domain name — strong phishing indicator",
            })

        # ── Rule 3: Suspicious TLD ────────────────────────────────
        tld_flag = self._check_suspicious_tld(domain)
        if tld_flag:
            risk_score += 0.20
            result["flags"].append(f"suspicious_tld:{tld_flag}")
            result["highlights"].append({
                "type": "domain",
                "value": domain,
                "reason": f"Uses suspicious TLD '{tld_flag}' commonly associated with free/scam domains",
            })

        # ── Rule 4: URL shortener ─────────────────────────────────
        if self._is_url_shortener(domain):
            risk_score += 0.15
            result["flags"].append("url_shortener")
            result["highlights"].append({
                "type": "domain",
                "value": domain,
                "reason": "URL shortener detected — destination may be hidden",
            })

        # ── Rule 5: Excessive subdomains ──────────────────────────
        subdomain_count = domain.count(".")
        if subdomain_count > 3:
            risk_score += 0.15
            result["flags"].append("excessive_subdomains")
            result["details"]["subdomain_count"] = subdomain_count
            result["highlights"].append({
                "type": "domain",
                "value": domain,
                "reason": f"Excessive subdomains ({subdomain_count}) used to disguise malicious domain",
            })

        # ── Rule 6: Bank name in non-official domain ──────────────
        bank_flag = self._check_bank_name_abuse(domain)
        if bank_flag:
            risk_score += 0.35
            result["flags"].append(f"bank_name_abuse:{bank_flag}")
            result["highlights"].append({
                "type": "domain",
                "value": domain,
                "reason": f"Bank name '{bank_flag}' found in non-official domain — likely impersonation",
            })

        # ── Rule 7: Keyword stuffing in domain ────────────────────
        domain_keywords = self._check_domain_keyword_stuffing(domain)
        if len(domain_keywords) >= 2:
            risk_score += min(0.35, 0.15 + 0.05 * len(domain_keywords))
            result["flags"].append("domain_keyword_stuffing")
            result["details"]["domain_keywords"] = domain_keywords
            result["highlights"].append({
                "type": "domain",
                "value": domain,
                "reason": f"Suspicious keywords in domain: {', '.join(domain_keywords)}",
            })

        # ── Rule 8: Long URL ──────────────────────────────────────
        url_length = len(url)
        if url_length > 200:
            risk_score += 0.10
            result["flags"].append("excessively_long_url")
            result["details"]["url_length"] = url_length

        # ── Rule 9: Suspicious path keywords ─────────────────────
        path_flags = self._check_path_keywords(path)
        if path_flags:
            risk_score += 0.10
            result["flags"].append("suspicious_path_keywords")
            result["details"]["path_flags"] = path_flags
            result["highlights"].append({
                "type": "path",
                "value": path,
                "reason": f"Suspicious path keywords: {', '.join(path_flags)}",
            })

        # ── Rule 10: Double slash in path (redirection trick) ─────
        if "//" in path[1:]:
            risk_score += 0.10
            result["flags"].append("double_slash_redirection")

        # ── Rule 11: UPI-specific checks ─────────────────────────
        if url.startswith("upi://"):
            upi_risk = self._check_upi_url(url)
            risk_score += upi_risk["risk_score"]
            result["flags"].extend(upi_risk["flags"])
            result["details"]["upi_analysis"] = upi_risk

        # ── Rule 12: Homoglyph characters ─────────────────────────
        if self._has_homoglyphs(domain):
            risk_score += 0.25
            result["flags"].append("homoglyph_characters")
            result["highlights"].append({
                "type": "domain",
                "value": domain,
                "reason": "Look-alike characters detected in domain (e.g., '0' for 'o', '1' for 'l')",
            })

        # ── Legitimate domain bonus ───────────────────────────────
        # Floor at 0 — never go negative.
        if is_legitimate:
            risk_score = max(0.0, risk_score - 0.30)

        # Clamp to [0, 1]
        result["probability"] = max(0.0, min(1.0, risk_score))

        return result

    # ── Private helpers ───────────────────────────────────────────

    def _is_ip_address(self, domain: str) -> bool:
        try:
            ipaddress.ip_address(domain)
            return True
        except ValueError:
            return False

    def _is_legitimate_domain(self, domain: str) -> bool:
        for legit in LEGITIMATE_DOMAINS:
            if domain == legit or domain.endswith("." + legit):
                return True
        return False

    def _check_suspicious_tld(self, domain: str) -> str:
        for tld in SUSPICIOUS_TLDS:
            if domain.endswith(tld):
                return tld
        return ""

    def _is_url_shortener(self, domain: str) -> bool:
        return domain in URL_SHORTENERS

    def _check_bank_name_abuse(self, domain: str) -> str:
        if self._is_legitimate_domain(domain):
            return ""
        for bank in INDIAN_BANKS:
            if bank in domain:
                return bank
        return ""

    def _check_domain_keyword_stuffing(self, domain: str) -> List[str]:
        if self._is_legitimate_domain(domain):
            return []
        base_domain = domain.split(".")[0]
        return [kw for kw in PHISHING_DOMAIN_KEYWORDS if kw in base_domain]

    def _check_path_keywords(self, path: str) -> List[str]:
        suspicious = [
            "login", "signin", "verify", "confirm", "secure",
            "account", "update", "kyc", "validate", "authenticate",
            "banking", "netbanking", "credit-card", "debit-card",
        ]
        return [kw for kw in suspicious if kw in path]

    def _check_upi_url(self, url: str) -> Dict:
        result = {"risk_score": 0.0, "flags": [], "parsed": {}}

        query_start = url.find("?")
        if query_start == -1:
            result["flags"].append("malformed_upi_url")
            result["risk_score"] = 0.3
            return result

        query_str = url[query_start + 1:]
        params = {}
        for param in query_str.split("&"):
            if "=" in param:
                k, v = param.split("=", 1)
                params[k] = unquote(v)

        result["parsed"] = params

        vpa = params.get("pa", "")
        if not vpa or "@" not in vpa:
            result["flags"].append("invalid_vpa_format")
            result["risk_score"] += 0.25
        else:
            vpa_domain = vpa.split("@")[1] if "@" in vpa else ""
            known_handles = {
                "oksbi", "okhdfcbank", "okicici", "okaxis", "ybl", "upi",
                "paytm", "paytmbank", "gpay", "idfcbank", "aubank",
                "sbi", "hdfc", "icici", "axis", "kotak",
            }
            if vpa_domain not in known_handles:
                result["flags"].append(f"unusual_upi_handle:{vpa_domain}")
                result["risk_score"] += 0.1

        payee_name = params.get("pn", "")
        if not payee_name:
            result["flags"].append("missing_payee_name")
            result["risk_score"] += 0.1
        elif len(payee_name) < 2:
            result["flags"].append("suspicious_short_payee_name")
            result["risk_score"] += 0.15

        return result

    def _has_homoglyphs(self, domain: str) -> bool:
        base = domain.split(".")[0]
        for bank in ["sbi", "hdfc", "icici", "axis", "kotak"]:
            normalized = re.sub(r"0", "o", re.sub(r"1", "l", re.sub(r"3", "e", base)))
            if bank in normalized and bank not in base:
                return True
        return False


# Singleton instance
url_heuristics = URLHeuristicsEngine()
