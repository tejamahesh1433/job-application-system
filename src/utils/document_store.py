"""
Document storage helpers for uploaded and generated application files.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_RESUMES_DIR = PROJECT_ROOT / settings.resumes_dir
TAILORED_RESUMES_DIR = PROJECT_ROOT / settings.applications_dir / "tailored_resumes"
COVER_LETTERS_DIR = PROJECT_ROOT / settings.applications_dir / "cover_letters"

DOCUMENT_ROOTS = {
    "uploaded_resumes": UPLOAD_RESUMES_DIR,
    "tailored_resumes": TAILORED_RESUMES_DIR,
    "cover_letters": COVER_LETTERS_DIR,
}


def safe_name(value: str, fallback: str = "document") -> str:
    text = (value or fallback).strip()
    text = re.sub(r"[^A-Za-z0-9._ -]+", "", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("._-")
    return text[:80] or fallback


def company_filename(
    company_name: str,
    doc_type: str,
    job_title: str = "",
    extension: str = "txt",
) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    company = safe_name(company_name, "Unknown_Company")
    title = safe_name(job_title, "Role")
    kind = safe_name(doc_type, "document")
    return f"{company}__{kind}__{title}__{stamp}.{extension.lstrip('.')}"


def write_text_document(
    category: str,
    company_name: str,
    doc_type: str,
    content: str,
    job_title: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    extension: str = "txt",
) -> Dict[str, Any]:
    target_dir = DOCUMENT_ROOTS[category]
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = company_filename(company_name, doc_type, job_title, extension)
    path = target_dir / filename

    if extension.lower().lstrip(".") == "json":
        payload = {
            "metadata": metadata or {},
            "content": content,
            "created_at": datetime.utcnow().isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        header = [
            f"Company: {company_name or 'Unknown Company'}",
            f"Role: {job_title or 'Unknown Role'}",
            f"Document: {doc_type}",
            f"Created: {datetime.utcnow().isoformat()} UTC",
            "",
        ]
        path.write_text("\n".join(header) + content.strip() + "\n", encoding="utf-8")

    return describe_file(path, category)


def describe_file(path: Path, category: str) -> Dict[str, Any]:
    stat = path.stat()
    name = path.name
    parts = name.split("__")
    company = parts[0].replace("_", " ") if len(parts) >= 3 else ""
    doc_type = parts[1].replace("_", " ") if len(parts) >= 3 else category.replace("_", " ")
    title = parts[2].replace("_", " ") if len(parts) >= 3 else ""
    return {
        "id": f"{category}:{name}",
        "category": category,
        "name": name,
        "company": company,
        "doc_type": doc_type,
        "job_title": title,
        "extension": path.suffix.lower().lstrip("."),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "download_url": f"/api/documents/download/{category}/{name}",
        "view_url": f"/api/documents/view/{category}/{name}",
    }


def iter_documents() -> Iterable[Dict[str, Any]]:
    for category, root in DOCUMENT_ROOTS.items():
        root.mkdir(parents=True, exist_ok=True)
        for path in root.iterdir():
            if not path.is_file() or path.name.startswith("."):
                continue
            yield describe_file(path, category)


def resolve_document(category: str, filename: str) -> Path:
    if category not in DOCUMENT_ROOTS:
        raise FileNotFoundError("Unknown document category")
    root = DOCUMENT_ROOTS[category].resolve()
    path = (root / filename).resolve()
    if not str(path).lower().startswith(str(root).lower()):
        raise FileNotFoundError("Invalid document path")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("Document not found")
    return path


def rename_document(category: str, filename: str, new_stem: str) -> Dict[str, Any]:
    path = resolve_document(category, filename)
    clean_stem = safe_name(new_stem, path.stem)
    target = path.with_name(f"{clean_stem}{path.suffix}")
    if target.exists() and target != path:
        raise FileExistsError("A file with that name already exists")
    path.rename(target)
    return describe_file(target, category)


def delete_document(category: str, filename: str) -> None:
    path = resolve_document(category, filename)
    path.unlink()


def update_text_document(category: str, filename: str, content: str) -> Dict[str, Any]:
    path = resolve_document(category, filename)
    if path.suffix.lower() not in {".txt", ".json", ".md", ".csv"}:
        raise ValueError("Only text files can be edited in the browser")
    path.write_text(content or "", encoding="utf-8")
    return describe_file(path, category)
