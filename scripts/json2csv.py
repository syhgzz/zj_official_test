#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Convert a list inside a JSON file to CSV and Excel.

Example:
    python json2csv.py responses/3.2.7_api_v1_udmds_alerts_summary.json data.alerts

Sort by time from oldest to newest:
    python json2csv.py responses/xxx.json data.alerts --sort-by-time

Keep original timestamp values:
    python json2csv.py responses/xxx.json data.alerts --no-convert-time

By default, output files are created next to the input JSON file with the same
base name, for example:
    responses/3.2.7_api_v1_udmds_alerts_summary.csv
    responses/3.2.7_api_v1_udmds_alerts_summary.xlsx
"""
import argparse
import csv
import json
import zipfile
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


TIME_FIELD_NAMES = {"time", "timestamp", "detectionTime", "startTime", "endTime"}


def get_value_by_path(data: Any, field_path: str) -> Any:
    """Read a nested value by dot path, for example: data.alerts."""
    current = data
    for part in field_path.split("."):
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(f"Path segment '{part}' not found in '{field_path}'")
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise KeyError(
                    f"Path segment '{part}' is not a valid list index in '{field_path}'"
                ) from exc
        else:
            raise KeyError(
                f"Cannot read segment '{part}' from non-container value in '{field_path}'"
            )
    return current


def flatten_record(record: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dictionaries so they can be written as CSV columns."""
    flattened: Dict[str, Any] = {}
    for key, value in record.items():
        column = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(flatten_record(value, column))
        elif isinstance(value, list):
            flattened[column] = json.dumps(value, ensure_ascii=False)
        else:
            flattened[column] = value
    return flattened


def looks_like_timestamp(value: Any) -> bool:
    """Return True for common second or millisecond Unix timestamp numbers."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    return 1_000_000_000 <= value <= 99_999_999_999_999


def timestamp_to_text(value: Any) -> str:
    """Convert Unix timestamp in seconds or milliseconds to readable local time."""
    timestamp = value / 1000 if value >= 10_000_000_000 else value
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def is_time_field(fieldname: str) -> bool:
    """Match fields named time or ending with .time after flattening nested JSON."""
    last_part = fieldname.rsplit(".", 1)[-1]
    return last_part in TIME_FIELD_NAMES


def convert_time_fields(rows: Sequence[Dict[str, Any]]) -> None:
    """Convert timestamp-like time fields to readable time text in-place."""
    for row in rows:
        for fieldname, value in list(row.items()):
            if is_time_field(fieldname) and looks_like_timestamp(value):
                row[fieldname] = timestamp_to_text(value)


def get_sort_timestamp(row: Dict[str, Any]) -> Tuple[int, float]:
    """Get the first timestamp-like time value for optional ascending sorting."""
    for fieldname, value in row.items():
        if is_time_field(fieldname) and looks_like_timestamp(value):
            timestamp = value / 1000 if value >= 10_000_000_000 else value
            return 0, timestamp
    return 1, 0


def collect_fieldnames(rows: Iterable[Dict[str, Any]]) -> List[str]:
    """Collect output fieldnames in first-seen order."""
    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    return fieldnames


def load_rows(
    json_file: Path,
    list_field: str,
    convert_time: bool = True,
    sort_by_time: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Load and flatten rows from the selected JSON list field."""
    with json_file.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    records = get_value_by_path(payload, list_field)
    if not isinstance(records, list):
        raise TypeError(f"Field '{list_field}' must be a list, got {type(records).__name__}")

    rows = [
        flatten_record(record) if isinstance(record, dict) else {"value": record}
        for record in records
    ]

    # Optional: sort records by timestamp from oldest to newest before conversion.
    if sort_by_time:
        rows.sort(key=get_sort_timestamp)

    # Optional: turn timestamp fields such as time/detectionTime into readable text.
    if convert_time:
        convert_time_fields(rows)

    return rows, collect_fieldnames(rows)


def write_csv(output_path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> Path:
    """Write rows to CSV. JSON numbers are written as numeric-looking values."""
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def column_name(index: int) -> str:
    """Convert a 1-based column index to an Excel column name."""
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def xlsx_cell(value: Any, row_index: int, column_index: int) -> str:
    """Build one XLSX cell, preserving JSON numbers as Excel numeric cells."""
    cell_ref = f"{column_name(column_index)}{row_index}"
    if value is None:
        return f'<c r="{cell_ref}"/>'
    if isinstance(value, bool):
        return f'<c r="{cell_ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{cell_ref}"><v>{value}</v></c>'

    text = escape(str(value))
    return f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def build_sheet_xml(rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> str:
    """Build worksheet XML for a minimal XLSX file."""
    sheet_rows = []
    header_cells = [
        xlsx_cell(fieldname, 1, column_index)
        for column_index, fieldname in enumerate(fieldnames, start=1)
    ]
    sheet_rows.append(f'<row r="1">{"".join(header_cells)}</row>')

    for row_index, row in enumerate(rows, start=2):
        cells = [
            xlsx_cell(row.get(fieldname), row_index, column_index)
            for column_index, fieldname in enumerate(fieldnames, start=1)
        ]
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        '</worksheet>'
    )


def write_excel(output_path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> Path:
    """Write rows to a minimal Excel .xlsx file using only the standard library."""
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="data" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", build_sheet_xml(rows, fieldnames))

    return output_path


def json_list_to_csv(
    json_file: Path,
    list_field: str,
    output_file: Optional[Path] = None,
    convert_time: bool = True,
    sort_by_time: bool = False,
) -> Path:
    """Convert the selected JSON list field to a CSV file."""
    rows, fieldnames = load_rows(json_file, list_field, convert_time, sort_by_time)
    output_path = output_file or json_file.with_suffix(".csv")
    return write_csv(output_path, rows, fieldnames)


def json_list_to_files(
    json_file: Path,
    list_field: str,
    csv_output: Optional[Path] = None,
    excel_output: Optional[Path] = None,
    convert_time: bool = True,
    sort_by_time: bool = False,
) -> Tuple[Path, Path]:
    """Convert the selected JSON list field to same-name CSV and XLSX files."""
    rows, fieldnames = load_rows(json_file, list_field, convert_time, sort_by_time)
    csv_path = csv_output or json_file.with_suffix(".csv")
    excel_path = excel_output or json_file.with_suffix(".xlsx")
    write_csv(csv_path, rows, fieldnames)
    write_excel(excel_path, rows, fieldnames)
    return csv_path, excel_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a nested JSON list field to same-name CSV and Excel files."
    )
    # Choose the JSON file here, for example: responses/xxx.json
    parser.add_argument("json_file", type=Path, help="Input JSON file path, for example xxx.json")
    parser.add_argument(
        "list_field",
        # Choose the nested list key path here, for example: data.alerts
        help="Dot path of the list field in JSON, for example data.alerts",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        help="Output CSV file path. Defaults to the input JSON path with .csv suffix.",
    )
    parser.add_argument(
        "--excel-output",
        type=Path,
        help="Output Excel file path. Defaults to the input JSON path with .xlsx suffix.",
    )
    parser.add_argument(
        "--sort-by-time",
        action="store_true",
        help="Sort rows by the first timestamp-like time field from oldest to newest.",
    )
    parser.add_argument(
        "--no-convert-time",
        action="store_true",
        help="Keep timestamp fields as raw numbers instead of readable local time text.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path, excel_path = json_list_to_files(
        args.json_file,
        args.list_field,
        csv_output=args.csv_output,
        excel_output=args.excel_output,
        convert_time=not args.no_convert_time,
        sort_by_time=args.sort_by_time,
    )
    print(f"CSV written to: {csv_path}")
    print(f"Excel written to: {excel_path}")


if __name__ == "__main__":
    main()
