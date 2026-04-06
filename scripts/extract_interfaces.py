#!/usr/bin/env python3
"""Extract API interfaces from a DOCX API document.

Output JSON records contain:
- path: API path like /api/v1/overview/realtime
- number: section number like 2.1.1
- title: section title like 获取系统实时概览
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Iterable, List, Tuple
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


def iter_paragraph_texts(docx_path: Path) -> Iterable[str]:
    """Yield paragraph texts from word/document.xml in document order."""
    with zipfile.ZipFile(docx_path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    for para in root.findall(".//w:body//w:p", NS):
        runs = para.findall(".//w:t", NS)
        if not runs:
            continue
        text = "".join((node.text or "") for node in runs).strip()
        if text:
            yield text


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


def extract_interfaces(docx_path: Path) -> List[dict]:
    current_number = ""
    current_title = ""

    seen_paths = set()
    interfaces: List[dict] = []

    for line in iter_paragraph_texts(docx_path):
        num_match = NUM_HEADING_RE.match(line)
        if num_match:
            current_number = num_match.group(1)
            current_title = clean_heading_text(num_match.group(2))
            continue

        cn_match = CN_HEADING_RE.match(line)
        if cn_match:
            current_number = cn_match.group(1)
            current_title = clean_heading_text(cn_match.group(2))
            continue

        if not should_check_for_path(line):
            continue

        for raw in PATH_RE.findall(line):
            path = normalize_path(raw)
            if not path or path == "/api/v1":
                continue
            if path in seen_paths:
                continue

            seen_paths.add(path)
            interfaces.append(
                {
                    "path": path,
                    "number": current_number,
                    "title": current_title,
                }
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
