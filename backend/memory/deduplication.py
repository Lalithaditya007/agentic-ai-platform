"""
3-Step Deduplication Logic
============================
Per spec Section 18 & 21:
  Step 1: Redis domain hash lookup (fastest — O(1))
  Step 2: PostgreSQL workflow_runs lookup (exact domain match)
  Step 3: ChromaDB semantic similarity (fuzzy match > 0.92)
"""

import hashlib
from typing import Optional


async def check_deduplication(company_domain: str, company_name: str) -> dict:
    """
    3-step deduplication check.
    Returns: {"skip": bool, "reason": str, "flag_for_review": bool}
    """
    # Step 1: Redis domain hash lookup
    try:
        from memory.redis_client import redis_get
        domain_hash = hashlib.md5(company_domain.lower().strip().encode()).hexdigest()
        redis_key = f"company:domain:{domain_hash}"
        cached = await redis_get(redis_key)
        if cached:
            return {
                "skip": True,
                "reason": "redis_cache_hit",
                "flag_for_review": False,
            }
    except Exception:
        pass  # Redis unavailable — continue to Step 2

    # Step 2: PostgreSQL lookup
    try:
        from database.models import AsyncSessionLocal, Company
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Company)
                .where(Company.domain == company_domain)
                .where(Company.validation_status.in_(["validated", "enriched"]))
            )
            existing = result.scalar_one_or_none()
            if existing:
                return {
                    "skip": True,
                    "reason": "db_already_processed",
                    "flag_for_review": False,
                }
    except Exception:
        pass  # DB error — continue to Step 3

    # Step 3: ChromaDB semantic similarity
    try:
        from memory.chromadb_client import chroma_query
        results = chroma_query(
            collection_name="company_knowledge",
            query_text=f"{company_name} {company_domain}",
            n_results=1,
        )
        if results and results[0].get("distance", 0) > 0.92:
            return {
                "skip": False,
                "reason": "semantic_similar",
                "flag_for_review": True,
            }
    except Exception:
        pass  # ChromaDB unavailable — allow company through

    return {"skip": False, "reason": "new_company", "flag_for_review": False}


async def mark_company_seen(company_domain: str, ttl_days: int = 7):
    """Cache the company domain in Redis after processing."""
    try:
        from memory.redis_client import redis_set, TTL_COMPANY_DOMAIN
        domain_hash = hashlib.md5(company_domain.lower().strip().encode()).hexdigest()
        redis_key = f"company:domain:{domain_hash}"
        await redis_set(redis_key, "1", ttl_seconds=ttl_days * 86400)
    except Exception:
        pass
