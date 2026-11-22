"""Connection tests that tell the user WHAT is wrong, not just 'HTTP 401'.

The OpenRouter case that motivated this: a *management* key can read account info
(`/auth/key` answers 200) but every model call returns 401 "User not found".
"""

from __future__ import annotations

from typing import Any

import httpx

BASE = "https://openrouter.ai/api/v1"
MANAGEMENT_HINT = (
    "This is a management key. Those cannot run models. "
    "Create a normal key at openrouter.ai/keys (the 'Create key' button, not 'Management key') and paste it here."
)


def explain_401(message: str = "") -> str:
    """Friendlier text for an inference 401, stored with failed price lookups."""
    return (
        "OpenRouter refused the key (401 'User not found'). Usually it is a management key or a key from a deleted "
        "account: create a normal API key at openrouter.ai/keys. " + (f"[{message[:80]}]" if message else "")
    ).strip()


def check_openrouter(
    key: str,
    model: str = "anthropic/claude-haiku-5.5",
    search_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free",
    spec_model: str = "inclusionai/ling-3.2-flash:free",
) -> dict[str, Any]:
    """Run the same calls the app makes and report each one."""
    key = (key or "").strip()
    if not key:
        return {"ok": False, "message": "No key saved yet.", "steps": []}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    steps: list[dict[str, Any]] = []

    def chat(label: str, name: str, web: bool = False) -> bool:
        body: dict[str, Any] = {"model": name, "messages": [{"role": "user", "content": "Reply with: ok"}], "max_tokens": 5}
        if web:
            body["plugins"] = [{"id": "web", "max_results": 1}]  # same plugin the price lookup uses
        try:
            response = httpx.post(f"{BASE}/chat/completions", headers=headers, json=body, timeout=60)
        except Exception as exc:
            steps.append({"name": label, "ok": False, "detail": f"request failed: {type(exc).__name__}"})
            return False
        if response.status_code == 200:
            steps.append({"name": label, "ok": True, "detail": name})
            return True
        try:
            message = response.json().get("error", {}).get("message", "")
        except Exception:
            message = ""
        steps.append({"name": label, "ok": False, "detail": f"HTTP {response.status_code}: {message[:120]}"})
        return False

    management = False
    try:
        info = httpx.get(f"{BASE}/auth/key", headers=headers, timeout=20)
        if info.status_code == 200:
            management = bool((info.json().get("data") or {}).get("is_management_key"))
            steps.append({"name": "Key accepted", "ok": True, "detail": "management key" if management else "normal key"})
        else:
            steps.append({"name": "Key accepted", "ok": False, "detail": f"HTTP {info.status_code}"})
            return {"ok": False, "message": "OpenRouter does not recognise this key. Check it was copied completely.", "steps": steps}
    except Exception as exc:
        return {"ok": False, "message": f"Could not reach OpenRouter ({type(exc).__name__}).", "steps": steps}

    spec_ok = chat("Specs + description model", spec_model) if spec_model else True
    price_ok = chat("Algerian price model (web search)", search_model.removesuffix(":online"), web=True)
    verdict_ok = chat("Verdict model", model)

    if verdict_ok and price_ok and spec_ok:
        return {"ok": True, "message": "Key works for specs, Algerian prices and verdicts.", "steps": steps}
    if management and not (verdict_ok or price_ok or spec_ok):
        return {"ok": False, "message": MANAGEMENT_HINT, "steps": steps}
    failed = [s["name"] for s in steps if not s["ok"] and s["name"] != "Key accepted"]
    return {
        "ok": False,
        "message": "These calls failed: " + ", ".join(failed) + ". Check the model names (a free model may be rate limited, retry in a minute) and your credit balance.",
        "steps": steps,
    }
