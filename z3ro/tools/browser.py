"""Z3RO — Web Research and Browsing Tool.

Implements Section 2 & 9.1:
- Capability: 'web_research' (Allowed by default, No human approval needed).
- Adheres to robots.txt etiquette, rate-limiter, and safety boundaries.
"""

import urllib.request
import urllib.parse
import json
import re
from typing import Dict, Any, Optional
from z3ro.economy.limits import limits_manager
from z3ro.compliance.jurisdiction_rules import jurisdiction_evaluator


class BrowserTool:
    """Safely executes web research queries and fetches public information."""

    USER_AGENT = "Z3RO-Autonomous-Agent/2.0 (ResearchBot)"

    def fetch_url(self, url: str, timeout: int = 10) -> Dict[str, Any]:
        """Fetch content from a URL with safety and compliance checks."""
        # 1. Pre-flight permission check
        allowed, reason = limits_manager.check_can_execute("web_research")
        if not allowed:
            return {"success": False, "error": reason}

        # 2. Jurisdiction domain check
        comp_ok, comp_violation = jurisdiction_evaluator.check_url_and_robots(url)
        if not comp_ok and comp_violation:
            return {"success": False, "error": f"Compliance Blocked: {comp_violation.reason}"}

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content_type = response.headers.get_content_type()
                raw_bytes = response.read(65536)  # Read at most 64KB
                text = raw_bytes.decode("utf-8", errors="ignore")

                # Strip HTML tags simply
                clean_text = re.sub(r"<[^>]+>", " ", text)
                clean_text = re.sub(r"\s+", " ", clean_text).strip()

                limits_manager.record_action_executed()
                return {
                    "success": True,
                    "url": url,
                    "content_type": content_type,
                    "text": clean_text[:4000],
                }
        except Exception as e:
            limits_manager.record_action_failed_or_rejected()
            return {"success": False, "error": str(e)}

    def search_web(self, query: str) -> Dict[str, Any]:
        """Perform a simple web research query via DuckDuckGo Instant Answer API."""
        allowed, reason = limits_manager.check_can_execute("web_research")
        if not allowed:
            return {"success": False, "error": reason}

        try:
            encoded = urllib.parse.quote_plus(query)
            api_url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(api_url, headers={"User-Agent": self.USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                abstract = data.get("AbstractText", "")
                heading = data.get("Heading", "")
                related = [t.get("Text") for t in data.get("RelatedTopics", []) if isinstance(t, dict) and t.get("Text")]

                limits_manager.record_action_executed()
                return {
                    "success": True,
                    "query": query,
                    "heading": heading,
                    "abstract": abstract,
                    "related_snippets": related[:5],
                }
        except Exception as e:
            limits_manager.record_action_failed_or_rejected()
            return {"success": False, "error": str(e)}


# Global browser tool singleton
browser_tool = BrowserTool()
