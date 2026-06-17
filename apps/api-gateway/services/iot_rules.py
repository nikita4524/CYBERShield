"""
IoT security rule definitions and evaluation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

SUSPICIOUS_DNS_PATTERNS = (
    "malware",
    "c2.",
    "botnet",
    "phish",
    "fake-",
    ".xyz",
    ".ru",
    ".tk",
    "router-login",
    "smartcam-update",
)

SUSPICIOUS_DNS_BLOCKLIST = {
    "malware-c2.xyz",
    "router-login.fake",
    "smartcam-update.ru",
    "botnet-command.tk",
    "phish-dns.xyz",
}

RULE_SCORES = {
    "unknown_device_alert": 40,
    "suspicious_dns": 35,
    "brute_force_attempt": 25,
    "device_offline": 15,
}

RULE_SEVERITY = {
    "unknown_device_alert": "high",
    "suspicious_dns": "high",
    "brute_force_attempt": "medium",
    "device_offline": "low",
}


@dataclass
class RuleMatch:
    rule_id: str
    severity: str
    description: str
    score_contribution: int


def _dns_is_suspicious(dns_query: str) -> bool:
    query = dns_query.lower().strip()
    if query in SUSPICIOUS_DNS_BLOCKLIST:
        return True
    return any(pattern in query for pattern in SUSPICIOUS_DNS_PATTERNS)


def evaluate_telemetry_rules(
    event_type: str,
    data: Dict[str, Any],
    *,
    device_known: bool,
    mac_address: Optional[str] = None,
) -> List[RuleMatch]:
    """Evaluate telemetry payload against IoT security rules."""
    matches: List[RuleMatch] = []

    if not device_known:
        mac = mac_address or data.get("mac_address") or "unknown"
        matches.append(
            RuleMatch(
                rule_id="unknown_device_alert",
                severity=RULE_SEVERITY["unknown_device_alert"],
                description=(
                    f"Unknown device ({mac}) sent telemetry on your network. "
                    "It is not registered in CyberShield. Disconnect it and verify "
                    "your Wi-Fi password."
                ),
                score_contribution=RULE_SCORES["unknown_device_alert"],
            )
        )

    if event_type == "traffic":
        dns_query = data.get("dns_query") or data.get("dns")
        if dns_query and _dns_is_suspicious(str(dns_query)):
            matches.append(
                RuleMatch(
                    rule_id="suspicious_dns",
                    severity=RULE_SEVERITY["suspicious_dns"],
                    description=(
                        f"Device attempted DNS lookup to suspicious domain "
                        f"'{dns_query}'. This may indicate malware or a compromised device."
                    ),
                    score_contribution=RULE_SCORES["suspicious_dns"],
                )
            )

    failed_logins = data.get("failed_logins")
    if failed_logins is not None:
        try:
            count = int(failed_logins)
        except (TypeError, ValueError):
            count = 0
        if count >= 5:
            matches.append(
                RuleMatch(
                    rule_id="brute_force_attempt",
                    severity=RULE_SEVERITY["brute_force_attempt"],
                    description=(
                        f"Detected {count} failed login attempts. "
                        "Change default credentials and enable account lockout."
                    ),
                    score_contribution=RULE_SCORES["brute_force_attempt"],
                )
            )

    return matches


def offline_rule_match(device_name: str) -> RuleMatch:
    return RuleMatch(
        rule_id="device_offline",
        severity=RULE_SEVERITY["device_offline"],
        description=(
            f"Device '{device_name}' has not reported telemetry recently. "
            "Check power, network connectivity, or possible tampering."
        ),
        score_contribution=RULE_SCORES["device_offline"],
    )
