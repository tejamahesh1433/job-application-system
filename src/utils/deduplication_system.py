"""
Deduplication System - Find duplicate job postings using semantic similarity
"""

import logging
from typing import List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
from utils.database import Job

logger = logging.getLogger(__name__)

class DeduplicationSystem:
    """Handles identification of duplicate jobs using semantic search"""

    def __init__(self, db: Session):
        self.db = db

    async def find_duplicates(self, job_title: str, company_name: str, embedding: List[float], threshold: float = 0.9) -> List[Job]:
        """
        Find potential duplicates in the database
        Uses pgvector for semantic similarity if available
        """
        
        # 1. First check for exact matches (Title + Company)
        exact_matches = self.db.query(Job).filter(
            Job.job_title.ilike(job_title),
            Job.company_name.ilike(company_name)
        ).all()
        
        if exact_matches:
            return exact_matches
            
        # 2. Try semantic search if embedding is provided
        # Note: Requires pgvector extension in Postgres
        try:
            # Simplified vector similarity search (conceptually)
            # In a real pgvector setup, we'd use <=> or <-> operators
            query = text("""
                SELECT id, job_title, company_name, 
                       (embedding <=> :embedding) as distance
                FROM jobs
                WHERE company_name ILIKE :company
                ORDER BY distance ASC
                LIMIT 5
            """)
            
            results = self.db.execute(query, {
                "embedding": str(embedding),
                "company": f"%{company_name}%"
            }).fetchall()
            
            duplicates = []
            for r in results:
                if r.distance < (1 - threshold):
                    job = self.db.query(Job).filter(Job.id == r.id).first()
                    if job:
                        duplicates.append(job)
            
            return duplicates
            
        except Exception as e:
            logger.debug(f"pgvector search failed or not available: {e}. Falling back to text search.")
            
            # Fallback: Fuzzy text match
            fuzzy_matches = self.db.query(Job).filter(
                Job.company_name.ilike(f"%{company_name}%"),
                Job.job_title.ilike(f"%{job_title[:10]}%")
            ).all()
            
            return fuzzy_matches

    def recommend_best_source(self, jobs: List[Job]) -> Job:
        """Rank sources: Company Site > LinkedIn > Indeed > Others"""
        
        source_rank = {
            "company_site": 1,
            "linkedin": 2,
            "indeed": 3,
            "ziprecruiter": 4
        }
        
        sorted_jobs = sorted(
            jobs, 
            key=lambda j: source_rank.get(j.source.lower() if j.source else "", 99)
        )
        
        return sorted_jobs[0]
