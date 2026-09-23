#!/usr/bin/env python3
"""Turn Heathrow's annual runway alternation programme PDF into the JSON table.

Heathrow publishes a new two-page programme each year (page 1 day-time, page 2
night-time). Run this against it to produce the file the integration reads:

    python3 scripts/build_alternation_table.py ~/Downloads/Heathrow_Runway_Alternation_Programme_2027.pdf

Needs ``pdftotext`` (poppler). The year comes from the PDF filename unless
``--year`` says otherwise, and the output lands beside the other tables unless
``--out`` says otherwise. The parsed schedule is checked for shape before it is
written: 52 contiguous Monday weeks per page, a day-time pair that swaps every
week, and a night-time alternative that is the primary runway's other end.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "heathrow_arrivals"

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
RWY = r"(?:09L|09R|27L|27R)"
# Each printed line carries two week columns: date, runway, runway - twice over.
ROW = re.compile(
    rf"(\d{{1,2}})\s+([A-Z][a-z]{{2}})\s+({RWY})\s+({RWY})\s+"
    rf"(\d{{1,2}})\s+([A-Z][a-z]{{2}})\s+({RWY})\s+({RWY})"
)
# The night alternative is the primary runway approached from the other end.
OPPOSITE = {"27R": "09L", "09L": "27R", "27L": "09R", "09R": "27L"}


def page_text(pdf: Path, number: int) -> str:
    return subprocess.run(
        ["pdftotext", "-layout", "-f", str(number), "-l", str(number), str(pdf), "-"],
        capture_output=True, text=True, check=True).stdout


def parse_page(text: str, year: int) -> list[tuple[date, str, str]]:
    weeks: list[tuple[date, str, str]] = []
    for match in ROW.finditer(text):
        d1, mon1, a1, b1, d2, mon2, a2, b2 = match.groups()
        weeks.append((date(year, MONTHS[mon1], int(d1)), a1, b1))
        weeks.append((date(year, MONTHS[mon2], int(d2)), a2, b2))
    weeks.sort(key=lambda week: week[0])
    return weeks


def check(day, night) -> list[str]:
    problems = []
    for label, table in (("day", day), ("night", night)):
        if len(table) != 52:
            problems.append(f"{label}: expected 52 weeks, parsed {len(table)}")
        for i, (week, _, _) in enumerate(table):
            if week.weekday() != 0:
                problems.append(f"{label}: week commencing {week} is not a Monday")
            if i and week - table[i - 1][0] != timedelta(days=7):
                problems.append(f"{label}: gap between {table[i - 1][0]} and {week}")
    for week, morning, afternoon in day:
        if {morning, afternoon} != {"27L", "27R"}:
            problems.append(f"day {week}: unexpected pair {morning}/{afternoon}")
    for i in range(1, len(day)):
        if day[i][1] == day[i - 1][1]:
            problems.append(f"day {day[i][0]}: morning runway did not alternate")
    for week, primary, alternative in night:
        if OPPOSITE[primary] != alternative:
            problems.append(f"night {week}: {alternative} is not the other end of {primary}")
    if len({primary for _, primary, _ in night[:4]}) != 4:
        problems.append("night: the first four weeks are not a full four-week cycle")
    return problems


def render(year: int, day, night) -> str:
    def block(name, table, last):
        lines = [f'  "{name}": {{']
        for i, (week, first, second) in enumerate(table):
            comma = "" if i == len(table) - 1 else ","
            lines.append(f'    "{week}": ["{first}", "{second}"]{comma}')
        lines.append("  }" + ("" if last else ","))
        return lines

    lines = [
        "{",
        f'  "year": {year},',
        f'  "source": "Heathrow Runway Alternation Programme {year} (heathrow.com)",',
        '  "_day": "week commencing (Monday) -> [06:00-15:00 runway, '
        '15:00-last departure runway], westerly operations only",',
        '  "_night": "week commencing (Monday) -> [primary runway, '
        'same strip from the other end]",',
    ]
    lines += block("day", day, last=False)
    lines += block("night", night, last=True)
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="the published programme PDF")
    parser.add_argument("--year", type=int, help="defaults to the year in the PDF filename")
    parser.add_argument("--out", type=Path, help="defaults to the integration's data directory")
    args = parser.parse_args()

    year = args.year
    if year is None:
        found = re.search(r"(20\d{2})", args.pdf.name)
        if not found:
            parser.error("no year in the filename - pass --year")
        year = int(found.group(1))

    day = parse_page(page_text(args.pdf, 1), year)
    night = parse_page(page_text(args.pdf, 2), year)

    problems = check(day, night)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1

    out = args.out or COMPONENT / f"runway_alternation_{year}.json"
    text = render(year, day, night)
    json.loads(text)  # the emitted file must parse
    out.write_text(text)
    print(f"{len(day)} day weeks, {len(night)} night weeks -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
