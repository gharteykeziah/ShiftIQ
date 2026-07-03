"""
privacy_policy.py — ShiftIQ privacy policy content.

Single source of truth for the privacy policy text.
Served via GET /api/privacy (JSON) and GET /privacy (HTML) in api.py.

Update this file whenever data practices change.
Last updated: 2026-07-02
"""

LAST_UPDATED = "2026-07-02"
APP_NAME = "ShiftIQ"
CONTACT_EMAIL = "kaghartey@email.meredith.edu"

# Plain-text sections — used by the JSON endpoint and rendered into HTML
SECTIONS = [
    {
        "title": "What we collect",
        "body": (
            "When you create an account, we collect your email address and a "
            "securely hashed version of your password. We never store your "
            "password in plain text. Within the app, we store the financial "
            "data you enter: your current balance, income sources (jobs), "
            "expenses, and daily financial snapshots used to show your history. "
            "We do not collect your name, phone number, address, or any "
            "government-issued identification."
        ),
    },
    {
        "title": "Why we collect it",
        "body": (
            "Your email address identifies your account and allows you to log "
            "in. Your financial data powers the app — projections, simulations, "
            "and insights are calculated from the data you provide. We do not "
            "sell your data, share it with advertisers, or use it for any "
            "purpose other than operating the app for you."
        ),
    },
    {
        "title": "Who can see your data",
        "body": (
            "Only you. Every piece of financial data stored in ShiftIQ is "
            "tied to your account and is never visible to other users. "
            f"The {APP_NAME} team may access anonymised, aggregated statistics "
            "to monitor app performance, but we do not access individual "
            "account data except when required to resolve a support issue "
            "you have raised with us."
        ),
    },
    {
        "title": "How your data is stored",
        "body": (
            "Your data is stored in a secured database. Passwords are hashed "
            "using bcrypt before storage — the original password is never "
            "written to disk. Financial data is stored in your account's "
            "private database partition. All data is transmitted over HTTPS."
        ),
    },
    {
        "title": "How long we keep your data",
        "body": (
            "We keep your data for as long as your account is active. "
            "If you delete your account, all your data — email, financial "
            "records, and history — is permanently deleted within 30 days."
        ),
    },
    {
        "title": "Your rights",
        "body": (
            "You can request a copy of all data we hold about you at any time. "
            "You can request deletion of your account and all associated data. "
            "You can correct any data stored in the app directly through "
            "the app interface. To make a request, email us at "
            f"{CONTACT_EMAIL}."
        ),
    },
    {
        "title": "Contact",
        "body": (
            f"Questions about this policy? Email {CONTACT_EMAIL}. "
            f"We aim to respond within 5 business days."
        ),
    },
]


def as_dict() -> dict:
    """Return the policy as a structured dictionary (for the JSON endpoint)."""
    return {
        "app": APP_NAME,
        "last_updated": LAST_UPDATED,
        "contact": CONTACT_EMAIL,
        "sections": SECTIONS,
    }


def as_html() -> str:
    """Return the policy as a self-contained HTML page (for the browser endpoint)."""
    sections_html = "\n".join(
        f"<section>\n  <h2>{s['title']}</h2>\n  <p>{s['body']}</p>\n</section>"
        for s in SECTIONS
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{APP_NAME} — Privacy Policy</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 48px auto;
            padding: 0 24px; color: #1a1a1a; line-height: 1.6; }}
    h1   {{ font-size: 1.8rem; margin-bottom: 4px; }}
    .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 40px; }}
    h2   {{ font-size: 1.1rem; margin-top: 32px; }}
    p    {{ margin-top: 8px; }}
    a    {{ color: #0066cc; }}
  </style>
</head>
<body>
  <h1>{APP_NAME} Privacy Policy</h1>
  <p class="meta">Last updated: {LAST_UPDATED} &nbsp;·&nbsp;
     Contact: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p>
  {sections_html}
</body>
</html>"""
