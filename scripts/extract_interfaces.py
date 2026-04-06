#!/usr/bin/env python3
"""Extract API interfaces from a DOCX API document.

Output JSON records contain:
- path: API path like /api/v1/overview/realtime
- number: section number like 2.1.1
- title: section title like 获取系统实时概览
- response_example: response example text under 响应示例/相应示例
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

# Numbered headings in this document look like: "3.1.6 预警汇总"
NUM_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)+)\s+(.+?)\s*$")
# Some top-level sections look like: "二、系统概览接口"
CN_HEADING_RE = re.compile(r"^([一二三四五六七八九十]+)、\s*(.+?)\s*$")
# Capture API-like paths. Excludes protocol prefixes and only keeps path segment.
PATH_RE = re.compile(r"(?<!\w)(/api/[A-Za-z0-9._~!$&'()*+,;=:@%{}\-/]+)")

HTTP_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD")


def clean_heading_text(text: str) -> str:
    """Normalize heading text by collapsing noisy whitespace from DOCX runs."""
    text = (
        text.replace("\u00a0", " ")
        .replace("\u2002", " ")
        .replace("\u2003", " ")
        .replace("\u3000", " ")
    )
    text = re.sub(r"\s+", " ", text).strip()
    # Remove spaces between adjacent Chinese characters.
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract interfaces from DOCX into JSON")
    parser.add_argument(
        "--docx",
        default="doc/中检数据治理平台-可视化系统接口文档-20260312v2.docx",
        help="Path to source .docx file",
    )
    parser.add_argument(
        "--output",
        default="doc/interfaces.json",
        help="Output JSON path",
    )
    return parser.parse_args()


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def read_document_body(docx_path: Path) -> ET.Element:
    with zipfile.ZipFile(docx_path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    body = root.find(".//w:body", NS)
    if body is None:
        raise ValueError("Invalid DOCX: missing word body")
    return body


def get_paragraph_text(para: ET.Element) -> str:
    runs = para.findall(".//w:t", NS)
    if not runs:
        return ""
    text = "".join((node.text or "") for node in runs).strip()
    return clean_heading_text(text)


def get_table_rows(table: ET.Element) -> List[List[str]]:
    rows: List[List[str]] = []
    for tr in table.findall("./w:tr", NS):
        row: List[str] = []
        for tc in tr.findall("./w:tc", NS):
            text_nodes = tc.findall(".//w:t", NS)
            text = clean_heading_text("".join((node.text or "") for node in text_nodes))
            row.append(text)
        if any(cell for cell in row):
            rows.append(row)
    return rows


def normalize_path(path: str) -> str:
    path = path.strip().rstrip("，。；;:：)）]\"'")
    if path.endswith("/") and path != "/":
        path = path[:-1]
    return path


def should_check_for_path(line: str) -> bool:
    if "接口地址" in line:
        return True
    if any(method in line for method in HTTP_METHODS) and "/api/" in line:
        return True
    if "/api/" in line:
        return True
    return False


def parse_description(line: str) -> Optional[str]:
    match = re.search(r"接口描述\s*[:：]\s*(.+)", line)
    if not match:
        return None
    text = clean_heading_text(match.group(1))
    return text or None


def detect_name_column(header: List[str]) -> int:
    candidates = ("参数名", "参数", "参数名称", "字段名", "字段", "名称")
    for idx, cell in enumerate(header):
        if any(key in cell for key in candidates):
            return idx
    return 0


def normalize_parameter_name(value: str) -> str:
    text = clean_heading_text(value).lstrip("•-* ")
    if not text:
        return ""

    for sep in ("（", "(", " ", "，", ",", "：", ":"):
        if sep in text:
            text = text.split(sep, 1)[0]
    return text.strip()


def extract_parameter_names(rows: List[List[str]]) -> List[str]:
    if not rows:
        return []

    start_idx = 0
    name_col = 0

    first_row = rows[0]
    if any("参数" in cell or "字段" in cell or "名称" in cell for cell in first_row):
        name_col = detect_name_column(first_row)
        start_idx = 1

    params: List[str] = []
    seen = set()
    for row in rows[start_idx:]:
        if name_col >= len(row):
            continue
        raw = row[name_col]
        name = normalize_parameter_name(raw)
        if not name:
            continue
        if name in {"参数", "参数名", "参数名称", "字段", "字段名", "名称"}:
            continue
        if name in seen:
            continue
        seen.add(name)
        params.append(name)
    return params


def is_response_example_heading(line: str) -> bool:
    """Check whether a paragraph marks response example section."""
    return "响应示例" in line or "相应示例" in line


def is_response_example_boundary(line: str) -> bool:
    """Detect boundaries that end response-example capture."""
    if not line:
        return False

    if is_response_example_heading(line):
        return True

    if "请求参数" in line or "路径参数" in line or "响应数据结构定义" in line:
        return True

    if NUM_HEADING_RE.match(line) or CN_HEADING_RE.match(line):
        return True

    if "接口地址" in line:
        return True

    if any(method in line for method in HTTP_METHODS) and "/api/" in line:
        return True

    return False


def format_table_as_text(rows: List[List[str]]) -> str:
    """Format table rows into plain text for response example storage."""
    if not rows:
        return ""

    lines = []
    for row in rows:
        cells = [cell for cell in row if cell]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines).strip()


def save_response_example(
    path_to_record: Dict[str, dict],
    interface_path: Optional[str],
    chunks: List[str],
) -> None:
    """Persist accumulated response-example chunks to target record."""
    if not interface_path or not chunks:
        return

    record = path_to_record.get(interface_path)
    if not record:
        return

    content = "\n".join(
        chunk.strip() for chunk in chunks if chunk and chunk.strip()
    ).strip()
    if not content:
        return

    existing = record.get("response_example", "")
    if existing:
        record["response_example"] = f"{existing}\n{content}"
    else:
        record["response_example"] = content


def extract_interfaces(docx_path: Path) -> List[dict]:
    current_number = ""
    current_title = ""
    current_module = ""
    current_interface_path: Optional[str] = None
    pending_request_params_path: Optional[str] = None
    pending_response_example_path: Optional[str] = None
    pending_response_example_chunks: List[str] = []

    seen_paths = set()
    path_to_record: Dict[str, dict] = {}
    interfaces: List[dict] = []

    body = read_document_body(docx_path)

    for child in list(body):
        tag = local_name(child.tag)

        if tag == "p":
            line = get_paragraph_text(child)
            if not line:
                continue

            if pending_response_example_path and is_response_example_boundary(line):
                save_response_example(
                    path_to_record,
                    pending_response_example_path,
                    pending_response_example_chunks,
                )
                pending_response_example_path = None
                pending_response_example_chunks = []

            num_match = NUM_HEADING_RE.match(line)
            if num_match:
                current_number = num_match.group(1)
                current_title = clean_heading_text(num_match.group(2))
                level = current_number.count(".") + 1
                if level == 2 and ("模块" in current_title or "接口" in current_title):
                    current_module = current_title
                pending_request_params_path = None
                pending_response_example_path = None
                pending_response_example_chunks = []
                continue

            cn_match = CN_HEADING_RE.match(line)
            if cn_match:
                current_number = cn_match.group(1)
                current_title = clean_heading_text(cn_match.group(2))
                if "接口" in current_title or "模块" in current_title:
                    current_module = current_title
                pending_request_params_path = None
                pending_response_example_path = None
                pending_response_example_chunks = []
                continue

            if "请求参数" in line:
                pending_request_params_path = current_interface_path
                pending_response_example_path = None
                pending_response_example_chunks = []
                continue

            if "路径参数" in line:
                pending_request_params_path = None
                pending_response_example_path = None
                pending_response_example_chunks = []
                continue

            if is_response_example_heading(line):
                pending_request_params_path = None
                pending_response_example_path = current_interface_path
                pending_response_example_chunks = []
                continue

            if "响应数据结构定义" in line:
                pending_request_params_path = None
                pending_response_example_path = None
                pending_response_example_chunks = []
                continue

            if pending_response_example_path:
                pending_response_example_chunks.append(line)
                continue

            description = parse_description(line)
            if description and current_interface_path:
                record = path_to_record.get(current_interface_path)
                if record and not record.get("description"):
                    record["description"] = description
                continue

            if not should_check_for_path(line):
                continue

            for raw in PATH_RE.findall(line):
                path = normalize_path(raw)
                if not path or path == "/api/v1":
                    continue

                current_interface_path = path
                pending_request_params_path = None
                pending_response_example_path = None
                pending_response_example_chunks = []

                if path in seen_paths:
                    continue

                seen_paths.add(path)
                record = {
                    "path": path,
                    "number": current_number,
                    "title": current_title,
                    "description": "",
                    "parameter": [],
                    "module": current_module,
                    "response_example": "",
                }
                interfaces.append(record)
                path_to_record[path] = record

        elif tag == "tbl":
            if pending_response_example_path:
                rows = get_table_rows(child)
                table_text = format_table_as_text(rows)
                if table_text:
                    pending_response_example_chunks.append(table_text)
                continue

            if not pending_request_params_path:
                continue

            record = path_to_record.get(pending_request_params_path)
            pending_request_params_path = None
            if not record:
                continue

            rows = get_table_rows(child)
            params = extract_parameter_names(rows)
            if not params:
                continue

            existing = set(record["parameter"])
            for param in params:
                if param not in existing:
                    record["parameter"].append(param)
                    existing.add(param)

    if pending_response_example_path:
        save_response_example(
            path_to_record,
            pending_response_example_path,
            pending_response_example_chunks,
        )

    return interfaces


def main() -> None:
    args = parse_args()
    docx_path = Path(args.docx)
    output_path = Path(args.output)

    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX not found: {docx_path}")

    records = extract_interfaces(docx_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Extracted {len(records)} interfaces -> {output_path}")


if __name__ == "__main__":
    main()
