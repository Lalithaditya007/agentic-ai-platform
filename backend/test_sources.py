import sys
sys.path.insert(0, ".")

from capabilities.builtin.sec_edgar_search import SecEdgarSearchPlugin
from capabilities.builtin.wikidata_search import WikidataCompanySearchPlugin

# --- SEC EDGAR (fixed) ---
edgar = SecEdgarSearchPlugin()
r1 = edgar.execute({"query": "hospital", "limit": 5})
print("EDGAR success:", r1["success"], "count:", len(r1["data"]), "error:", r1.get("error",""))
for c in r1["data"][:3]:
    print(" -", c["name"], "|", c.get("industry",""), "|", c.get("headquarters",""))

# --- Wikidata SPARQL ---
wd = WikidataCompanySearchPlugin()
r2 = wd.execute({"industry": ["Healthcare", "Hospital"], "geography": ["Europe"], "limit": 8})
print("Wikidata success:", r2["success"], "count:", len(r2["data"]), "error:", r2.get("error",""))
for c in r2["data"][:5]:
    print(" -", c["name"], "|", c.get("headquarters",""), "|", c.get("employee_count",""))

# --- Wikidata US tech ---
r3 = wd.execute({"industry": ["Software", "SaaS"], "geography": ["United States"], "limit": 8})
print("Wikidata US Tech success:", r3["success"], "count:", len(r3["data"]))
for c in r3["data"][:5]:
    print(" -", c["name"], "|", c.get("domain",""))
