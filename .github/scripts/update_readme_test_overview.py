#!/usr/bin/env python3

import glob
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET


START_MARKER = "<!-- TEST_OVERVIEW_START -->"
END_MARKER = "<!-- TEST_OVERVIEW_END -->"


STRUCTURAL_NAME_BY_INDEX = {
    1: "test.TestManager.structAttributes[Main]",
    2: "test.TestManager.structAttributes[Smiley]",
    3: "test.TestManager.structClass[Main]",
    4: "test.TestManager.structClass[Smiley]",
    5: "test.TestManager.structConstructors[Main]",
    6: "test.TestManager.structConstructors[Smiley]",
    7: "test.TestManager.structMethods[Main]",
    8: "test.TestManager.structMethods[Smiley]",
}


def normalize_solution_structural_names(case_results):
    priority = {"❌": 3, "⏭️": 2, "✅": 1}
    normalized = {}

    for case_id, status in case_results.items():
        mapped_case_id = case_id
        match = re.match(r"^test\.TestManager\.strukturTests\(String\)\[(\d+)\]$", case_id)
        if match:
            index = int(match.group(1))
            mapped_case_id = STRUCTURAL_NAME_BY_INDEX.get(index, case_id)

        prev = normalized.get(mapped_case_id)
        if prev is None or priority[status] > priority[prev]:
            normalized[mapped_case_id] = status

    return normalized


def testcase_id(testcase):
    classname = testcase.attrib.get("classname", "")
    name = testcase.attrib.get("name", "")
    return f"{classname}.{name}" if classname else name


def testcase_status(testcase):
    if testcase.find("failure") is not None or testcase.find("error") is not None:
        return "❌"
    if testcase.find("skipped") is not None:
        return "⏭️"
    return "✅"


def update_case_status(results, case_id, status, priority):
    prev = results.get(case_id)
    if prev is None or priority[status] > priority[prev]:
        results[case_id] = status


def split_results_by_scope(results):
    class_level = {}
    case_level = {}
    priority = {"❌": 3, "⏭️": 2, "✅": 1}

    for case_id, status in results.items():
        if case_id.endswith("."):
            class_name = case_id[:-1]
            if not class_name:
                continue
            prev = class_level.get(class_name)
            if prev is None or priority[status] > priority[prev]:
                class_level[class_name] = status
            continue
        case_level[case_id] = status

    return case_level, class_level


def propagate_class_level_to_cases(case_results, class_results, target_case_ids):
    priority = {"❌": 3, "⏭️": 2, "✅": 1}

    for case_id in target_case_ids:
        if "." not in case_id:
            continue
        class_name = case_id.rsplit(".", 1)[0]
        class_status = class_results.get(class_name)
        if class_status is None:
            continue

        prev = case_results.get(case_id)
        if prev is None or priority[class_status] > priority[prev]:
            case_results[case_id] = class_status

    return case_results


def parse_report_dir(report_dir):
    # Status precedence: failed/error > skipped > passed
    priority = {"❌": 3, "⏭️": 2, "✅": 1}
    results = {}

    for path in sorted(glob.glob(os.path.join(report_dir, "TEST-*.xml"))):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue

        for tc in root.findall(".//testcase"):
            case_id = testcase_id(tc)
            status = testcase_status(tc)
            update_case_status(results, case_id, status, priority)

    return results


def overview_timestamp_berlin():
    tz = ZoneInfo("Europe/Berlin")
    dt = datetime.now(tz)
    month_abbrev = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ][dt.month - 1]
    return f"Last Updated: {dt.day}. {month_abbrev} {dt.year} {dt:%H:%M:%S} [{dt:%Z}]"


def overview_commit_hash():
    return os.getenv("TEST_OVERVIEW_COMMIT") or os.getenv("GITHUB_SHA") or "unknown"


def build_table(solution_results, template_results):
    solution_cases, solution_class = split_results_by_scope(solution_results)
    template_cases, template_class = split_results_by_scope(template_results)

    solution_cases = normalize_solution_structural_names(solution_cases)

    base_cases = sorted(set(solution_cases.keys()) | set(template_cases.keys()))
    solution_cases = propagate_class_level_to_cases(solution_cases, solution_class, base_cases)
    template_cases = propagate_class_level_to_cases(template_cases, template_class, base_cases)

    all_cases = sorted(set(solution_cases.keys()) | set(template_cases.keys()))

    if not all_cases and (solution_class or template_class):
        all_classes = sorted(set(solution_class.keys()) | set(template_class.keys()))
        for class_name in all_classes:
            pseudo_case = f"{class_name}.*"
            if class_name in solution_class:
                solution_cases[pseudo_case] = solution_class[class_name]
            if class_name in template_class:
                template_cases[pseudo_case] = template_class[class_name]
        all_cases = sorted(set(solution_cases.keys()) | set(template_cases.keys()))

    lines = [
        "## Test Case Overview",
        "",
        "Auto-updated by CI from latest test runs.",
        "<!-- markdownlint-disable-next-line MD033 -->",
        f"> <sub>{overview_timestamp_berlin()}</sub>",
        "<!-- markdownlint-disable-next-line MD033 -->",
        f"> <sub>Commit: {overview_commit_hash()}</sub>",
        "",
        "Legend: ✅ passed, ❌ failed/error, ⏭️ skipped, — not present.",
        "",
        "| Test Case | Solution | Template |",
        "| --- | --- | --- |",
    ]

    for case_id in all_cases:
        sol = solution_cases.get(case_id, "—")
        tpl = template_cases.get(case_id, "—")
        lines.append(f"| {case_id} | {sol} | {tpl} |")

    if not all_cases:
        lines.append("| (no test results found) | — | — |")

    return "\n".join(lines)


def replace_marked_section(readme_text, new_section):
    block = f"{START_MARKER}\n{new_section}\n{END_MARKER}"
    if START_MARKER in readme_text and END_MARKER in readme_text:
        start = readme_text.index(START_MARKER)
        end = readme_text.index(END_MARKER) + len(END_MARKER)
        return readme_text[:start] + block + readme_text[end:]

    suffix = "" if readme_text.endswith("\n") else "\n"
    return f"{readme_text}{suffix}\n{block}\n"


def main():
    if len(sys.argv) != 4:
        print("Usage: update_readme_test_overview.py <readme_path> <solution_report_dir> <template_report_dir>")
        return 1

    readme_path, solution_dir, template_dir = sys.argv[1:4]

    solution_results = parse_report_dir(solution_dir)
    template_results = parse_report_dir(template_dir)
    new_section = build_table(solution_results, template_results)

    with open(readme_path, "r", encoding="utf-8") as f:
        current = f.read()

    updated = replace_marked_section(current, new_section)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())