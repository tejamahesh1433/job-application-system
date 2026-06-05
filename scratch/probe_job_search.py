import asyncio
import sys

sys.path.insert(0, "src")

from routers.jobs import search_jobs_api
from utils.database import SessionLocal


async def main():
    db = SessionLocal()
    try:
        result = await search_jobs_api(
            keyword="DevOps Engineer",
            location="Anywhere in USA",
            work_type="all",
            job_type="contract",
            source="",
            db=db,
        )
        print("success:", result.get("success"))
        print("total:", result.get("total"))
        print("sources:", result.get("sources"))
        print("message:", result.get("message"))
        for job in result.get("jobs", [])[:5]:
            print("|".join([
                job.get("title", ""),
                job.get("company", ""),
                job.get("job_type", ""),
                job.get("source", ""),
                job.get("url", "")[:60],
            ]))
    finally:
        db.close()


asyncio.run(main())
