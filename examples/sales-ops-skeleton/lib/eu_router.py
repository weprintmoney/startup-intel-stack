"""
EU/EEA routing logic for the <YOUR_COMPANY> sales-ops pipeline.

EU contacts are never sent SMTP email. They are flagged for LinkedIn-only
outreach and generate a Slack action item for manual follow-up.
"""

# All 27 EU member states + EEA (Norway, Iceland, Liechtenstein) + UK
# UK is post-Brexit but treated as GDPR-covered for safety.
EU_EEA_UK_CODES = {
    # EU member states
    "AT",  # Austria
    "BE",  # Belgium
    "BG",  # Bulgaria
    "HR",  # Croatia
    "CY",  # Cyprus
    "CZ",  # Czech Republic
    "DK",  # Denmark
    "EE",  # Estonia
    "FI",  # Finland
    "FR",  # France
    "DE",  # Germany
    "GR",  # Greece
    "HU",  # Hungary
    "IE",  # Ireland
    "IT",  # Italy
    "LV",  # Latvia
    "LT",  # Lithuania
    "LU",  # Luxembourg
    "MT",  # Malta
    "NL",  # Netherlands
    "PL",  # Poland
    "PT",  # Portugal
    "RO",  # Romania
    "SK",  # Slovakia
    "SI",  # Slovenia
    "ES",  # Spain
    "SE",  # Sweden
    # EEA (non-EU)
    "NO",  # Norway
    "IS",  # Iceland
    "LI",  # Liechtenstein
    # UK — post-Brexit, GDPR-equivalent (UK GDPR)
    "GB",
}


def is_eu(country_code: str) -> bool:
    """Return True if country_code is in EU/EEA/UK (GDPR-covered)."""
    return country_code.upper().strip() in EU_EEA_UK_CODES


def get_linkedin_action(contact: dict) -> str:
    """Return a formatted Slack mrkdwn message describing required LinkedIn action.

    Args:
        contact: Enriched lead dict with at minimum contact_name, company_name,
                 linkedin_url, country_code, and icp_segment fields.
    """
    name = contact.get("contact_name", "Unknown contact")
    company = contact.get("company_name", "Unknown company")
    title = contact.get("contact_title", "")
    linkedin = contact.get("linkedin_url", "")
    country = contact.get("country_code", "").upper()
    segment = contact.get("icp_segment", "")
    lead_id = contact.get("id", "")

    title_line = f" ({title})" if title else ""
    linkedin_line = f"\n  LinkedIn: {linkedin}" if linkedin else ""
    segment_line = f"\n  ICP segment: `{segment}`" if segment else ""
    id_line = f"\n  Lead ID: `{lead_id}`" if lead_id else ""

    return (
        f":eu: *EU Contact — LinkedIn outreach required*\n"
        f"  *{name}*{title_line} at *{company}* (country: `{country}`){linkedin_line}"
        f"{segment_line}{id_line}\n"
        f"  Action: Connect on LinkedIn and reference <YOUR_COMPANY>'s relevance to their stack. "
        f"Do *not* send email — GDPR applies."
    )
