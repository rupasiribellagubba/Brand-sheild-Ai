"""Evidence summaries. Rule-based by default; optional LLM (never the sole detector)."""
import json
import os
import urllib.request


def rule_based_summary(cand, assessment):
    top = sorted([i for i in assessment["indicators"] if i["contribution"] > 0],
                 key=lambda i: -i["contribution"])[:3]
    kind = "social-media profile" if cand["kind"] == "social" else "mobile app"
    text = f"This {kind} '{cand['name']}' scored {assessment['score']}/100 ({assessment['level']} risk). "
    if assessment.get("official_match"):
        text += "It matches an official identifier and is treated as the brand's own. "
    elif top:
        text += "Main contributing signals: " + "; ".join(f"{i['label']} (+{i['contribution']}) - {i['detail']}" for i in top) + " "
    else:
        text += "No significant risk signals were found. "
    return text + "These are similarity signals, not confirmed fraud; please review manually."


def generate_summary(cand, assessment):
    """Returns (summary, source, warning)."""
    fallback = rule_based_summary(cand, assessment)
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return fallback, "rule-based", "LLM not configured (set ANTHROPIC_API_KEY to enable optional AI summaries)."
    prompt = ("Write a neutral 3-sentence analyst summary of this brand-impersonation risk assessment. "
              "Do not claim fraud is confirmed.\n" + json.dumps(
                  {"candidate": {k: cand.get(k) for k in ("kind", "name", "username", "platform", "url", "developer", "app_id")},
                   "score": assessment["score"], "level": assessment["level"],
                   "indicators": [{"label": i["label"], "contribution": i["contribution"], "detail": i["detail"]}
                                  for i in assessment["indicators"]]}))
    body = json.dumps({"model": os.getenv("LLM_MODEL", "claude-sonnet-4-5"), "max_tokens": 300,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        text = "".join(b.get("text", "") for b in data.get("content", [])).strip()
        if not text:
            raise ValueError("empty LLM response")
        return text, "llm", None
    except Exception as exc:  # network, auth, quota, parse - always fall back
        return fallback, "rule-based", f"LLM unavailable ({type(exc).__name__}); showing rule-based summary."
