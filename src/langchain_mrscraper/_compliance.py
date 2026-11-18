"""Shared compliance copy for high-risk scraping tools."""

COMPLIANCE_MANUAL_SCRAPER_TITLE = "Compliance & Legal Risk"

COMPLIANCE_MANUAL_SCRAPER_WARNING = (
    "WARNING: Scraping login-protected pages carries serious legal and compliance "
    "risks. Many websites explicitly prohibit automated access in their Terms of "
    "Service, and bypassing authentication to scrape content may expose you to legal "
    "action including lawsuits, account termination, and financial penalties. By "
    "proceeding on scraping login-protected pages, you confirm that you have read "
    "and understood the target website's Terms of Service, and you fully accept all "
    "legal, financial, and ethical responsibility for your actions."
)


def manual_scraper_tool_description(capability: str) -> str:
    """Build a tool description with the manual-scraper compliance warning."""
    return (
        f"{capability}\n\n"
        f"{COMPLIANCE_MANUAL_SCRAPER_TITLE}\n"
        f"{COMPLIANCE_MANUAL_SCRAPER_WARNING}"
    )
