"""
Wikidata SPARQL Company Search Capability
==========================================
Queries Wikidata's public SPARQL endpoint to find companies by industry,
country, and size. Completely free, no API key required, no rate limiting
for reasonable usage.

Wikidata has structured data on 1M+ organizations worldwide including:
  - Industry (linked to industry taxonomy)
  - Country / headquarters
  - Employee count (where filed)
  - Official website
  - Stock exchange ticker

SPARQL endpoint: https://query.wikidata.org/sparql
"""

from typing import Any
from capabilities.base import CapabilityPlugin


# Maps common ICP industry strings to Wikidata Q-IDs (verified)
# Wikidata uses Q-IDs to identify specific entity types
# Verify at: https://www.wikidata.org/wiki/Special:Search
INDUSTRY_Q_IDS = {
    "healthcare":           ["Q16917", "Q1029099"],   # hospital, health care provider
    "hospital":             ["Q16917"],                # hospital (health care facility)
    "pharmaceutical":       ["Q507443"],               # pharmaceutical company
    "software":             ["Q1058914"],              # software company
    "saas":                 ["Q1058914"],              # software company
    "technology":           ["Q1058914", "Q4830453"],  # software company + business
    "cybersecurity":        ["Q1058914"],              # software company
    "fintech":              ["Q837171", "Q1058914"],   # payment service + software
    "banking":              ["Q22687"],                # bank
    "financial services":   ["Q22687", "Q837171"],     # bank + payment service
    "insurance":            ["Q43183"],                # insurance company
    "manufacturing":        ["Q4830453"],              # business enterprise
    "retail":               ["Q507294"],               # retail company
    "logistics":            ["Q1893893"],              # logistics company
    "real estate":          ["Q1589009"],              # real estate company
    "education":            ["Q2385804"],              # educational institution
    "media":                ["Q1664720"],              # media company
    "telecom":              ["Q1301983"],              # telecommunications company
    "energy":               ["Q6881511"],              # energy company
    "automotive":           ["Q786820"],               # automotive company
    "consulting":           ["Q4830453"],              # business enterprise
    "legal":                ["Q7075"],                 # law firm
    "b2b":                  ["Q4830453"],              # business enterprise
}

# Country → Wikidata Q-ID
COUNTRY_Q_IDS = {
    "us": "Q30", "united states": "Q30", "usa": "Q30", "america": "Q30",
    "uk": "Q145", "united kingdom": "Q145", "england": "Q145", "britain": "Q145",
    "germany": "Q183", "de": "Q183",
    "france": "Q142", "fr": "Q142",
    "india": "Q668", "in": "Q668",
    "canada": "Q16", "ca": "Q16",
    "australia": "Q408", "au": "Q408",
    "singapore": "Q334", "sg": "Q334",
    "netherlands": "Q55", "nl": "Q55",
    "sweden": "Q34", "se": "Q34",
    "israel": "Q801",
    "uae": "Q878", "dubai": "Q878",
    "ireland": "Q27",
    "switzerland": "Q39",
}


def _get_industry_q_ids(industry_list: list[str]) -> list[str]:
    result = []
    for ind in industry_list:
        key = ind.lower().strip()
        for k, qids in INDUSTRY_Q_IDS.items():
            if k in key or key in k:
                result.extend(qids)
    return list(dict.fromkeys(result))  # dedupe, preserve order


def _get_country_q_ids(geo_list: list[str]) -> list[str]:
    result = []
    for g in geo_list:
        key = g.lower().strip()
        if key in COUNTRY_Q_IDS:
            result.append(COUNTRY_Q_IDS[key])
    return list(dict.fromkeys(result))


class WikidataCompanySearchPlugin(CapabilityPlugin):

    @property
    def capability_id(self) -> str:
        return "company_data.wikidata_search"

    @property
    def display_name(self) -> str:
        return "Wikidata Company Search (Global)"

    @property
    def description(self) -> str:
        return "Search Wikidata's structured database of 1M+ global organizations by industry and country. Free, no API key, returns real companies with domains and employee counts."

    def health_check(self) -> bool:
        return True  # Always available — public SPARQL endpoint

    def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            input: {
                "industry": list[str],
                "geography": list[str],
                "employee_min": int (optional),
                "limit": int (default 20)
            }
        Returns:
            {"success": bool, "data": list[dict], "source": "wikidata"}
        """
        industry = input.get("industry", [])
        geography = input.get("geography", [])
        limit = min(input.get("limit", 20), 50)

        industry_qids = _get_industry_q_ids(industry)
        country_qids = _get_country_q_ids(geography)

        # Default: any business enterprise if we can't map
        if not industry_qids:
            industry_qids = ["Q4830453"]  # business enterprise

        try:
            import requests

            # Build SPARQL query
            industry_filter = " ".join(f"wd:{q}" for q in industry_qids[:4])
            country_filter = ""
            if country_qids:
                country_values = " ".join(f"wd:{q}" for q in country_qids[:3])
                country_filter = f"?company wdt:P17 ?country .\nVALUES ?country {{ {country_values} }}"

            # Build UNION of direct instance-of checks instead of path traversal
            # wdt:P31/wdt:P279* causes full graph scan → timeout
            # Using UNION { ?company wdt:P31 wd:Qxxx } is 10x faster
            union_parts = " UNION ".join(
                f"{{ ?company wdt:P31 wd:{q} . }}"
                for q in industry_qids[:4]
            )

            country_clause = ""
            if country_qids:
                country_values = " ".join(f"wd:{q}" for q in country_qids[:3])
                country_clause = f"OPTIONAL {{ ?company wdt:P17 ?country . FILTER(?country IN ({', '.join(f'wd:{q}' for q in country_qids[:3])})) }}"
            else:
                country_clause = "OPTIONAL { ?company wdt:P17 ?country . }"

            sparql = f"""SELECT DISTINCT ?company ?companyLabel ?website ?employees ?countryLabel WHERE {{
  {union_parts}
  OPTIONAL {{ ?company wdt:P856 ?website . }}
  OPTIONAL {{ ?company wdt:P1128 ?employees . }}
  {country_clause}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT {limit}
"""

            resp = requests.get(
                "https://query.wikidata.org/sparql",
                params={"query": sparql, "format": "json"},
                headers={
                    "User-Agent": "XLVenture-Platform/1.0 (contact@xlventure.com)",
                    "Accept": "application/sparql-results+json",
                },
                timeout=30,
            )


            if resp.status_code != 200:
                return {
                    "success": False, "data": [], "source": "wikidata",
                    "error": f"SPARQL HTTP {resp.status_code}"
                }

            bindings = resp.json().get("results", {}).get("bindings", []) or []

            companies = []
            seen_names: set[str] = set()

            for row in bindings:
                name = row.get("companyLabel", {}).get("value", "")
                if not name or name.startswith("Q") or name in seen_names:
                    continue
                seen_names.add(name)

                website = row.get("website", {}).get("value", "")
                domain = ""
                if website:
                    # Extract domain from URL
                    import re
                    m = re.match(r"https?://(?:www\.)?([^/]+)", website)
                    domain = m.group(1) if m else ""

                emp_raw = row.get("employees", {}).get("value", "")
                emp = int(emp_raw) if emp_raw and emp_raw.isdigit() else None

                country = row.get("countryLabel", {}).get("value", "")
                industry_label = row.get("industryLabel", {}).get("value", "")

                companies.append({
                    "name": name,
                    "domain": domain,
                    "website": website,
                    "industry": industry_label or (industry[0] if industry else ""),
                    "headquarters": country,
                    "employee_count": emp,
                    "source": "wikidata",
                    "trigger_source": "web_discovery",
                    "trigger_confidence": 0.70,
                    "trigger_detail": f"Wikidata-verified company in {industry_label or 'target industry'}",
                })

            return {"success": True, "data": companies, "source": "wikidata"}

        except Exception as e:
            return {"success": False, "data": [], "source": "wikidata", "error": str(e)}
