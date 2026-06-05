from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from utils.document_store import (
    delete_document,
    iter_documents,
    rename_document,
    resolve_document,
    update_text_document,
)


router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentUpdate(BaseModel):
    new_name: Optional[str] = None
    content: Optional[str] = None


@router.get("")
async def list_documents(
    q: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """List uploaded resumes, tailored resumes, and cover letters."""
    query = (q or "").strip().lower()
    docs = []
    for doc in iter_documents():
        if category and category != "all" and doc["category"] != category:
            continue
        haystack = " ".join(
            str(doc.get(key, ""))
            for key in ("name", "company", "job_title", "doc_type", "category")
        ).lower()
        if query and query not in haystack:
            continue
        docs.append(doc)

    docs.sort(key=lambda item: item.get("modified_at") or "", reverse=True)
    counts = {
        "all": len(docs),
        "uploaded_resumes": sum(1 for d in docs if d["category"] == "uploaded_resumes"),
        "tailored_resumes": sum(1 for d in docs if d["category"] == "tailored_resumes"),
        "cover_letters": sum(1 for d in docs if d["category"] == "cover_letters"),
    }
    return {"success": True, "documents": docs, "total": len(docs), "counts": counts}


@router.get("/view/{category}/{filename}")
async def view_document(category: str, filename: str):
    """Preview text-like documents in the browser."""
    try:
        path = resolve_document(category, filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if path.suffix.lower() not in {".txt", ".json", ".md", ".csv"}:
        raise HTTPException(status_code=415, detail="Preview is only available for text files")

    text = path.read_text(encoding="utf-8", errors="replace")
    return PlainTextResponse(text)


@router.get("/download/{category}/{filename}")
async def download_document(category: str, filename: str):
    """Download a document from an allowed document folder."""
    try:
        path = resolve_document(category, filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return FileResponse(path=str(path), filename=Path(path).name)


@router.patch("/{category}/{filename}")
async def update_document(category: str, filename: str, body: DocumentUpdate) -> Dict[str, Any]:
    """Rename a document and/or update text-file content."""
    try:
        doc = None
        current_name = filename
        if body.new_name:
            doc = rename_document(category, current_name, body.new_name)
            current_name = doc["name"]
        if body.content is not None:
            doc = update_text_document(category, current_name, body.content)
        if doc is None:
            doc = {"success": True}
        return {"success": True, "document": doc}
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{category}/{filename}")
async def remove_document(category: str, filename: str) -> Dict[str, Any]:
    """Delete a document from an allowed document folder."""
    try:
        delete_document(category, filename)
        return {"success": True, "deleted": filename}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
