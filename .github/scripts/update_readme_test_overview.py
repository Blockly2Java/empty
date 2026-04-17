#!/usr/bin/env python3

import glob
import os
import sys
import xml.etree.ElementTree as ET


START_MARKER = "<!-- TEST_OVERVIEW_START -->"
END_MARKER = "<!-- TEST_OVERVIEW_END -->"


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


def build_table(solution_results, template_results):
    all_cases = sorted(set(solution_results.keys()) | set(template_results.keys()))

    lines = [
        "## Test Case Overview",
        "",
        "Auto-updated by CI from latest test runs.",
        "",
        "Legend: ✅ passed, ❌ failed/error, ⏭️ skipped, — not present.",
        "",
        "| Test Case | Solution | Template |",
        "| --- | --- | --- |",
    ]

    for case_id in all_cases:
        sol = solution_results.get(case_id, "—")
        tpl = template_results.get(case_id, "—")
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