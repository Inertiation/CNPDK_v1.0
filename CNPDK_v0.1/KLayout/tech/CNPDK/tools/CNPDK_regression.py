# -*- coding: utf-8 -*-
"""
CNPDK Automated Regression Runner v1.0
=======================================

建议位置
--------
    CNPDK/tools/CNPDK_regression.py

目标
----
对准备发布的CNPDK安装包执行可重复的一键回归：

1. 检查目录、核心文件、Python语法和绝对路径残留；
2. 在独立KLayout批处理进程中重新加载CNPDK Library；
3. 创建固定的PCell参数测试矩阵并写出GDS；
4. 对参数测试GDS运行整合DRC，统计真实marker数量；
5. 自动发现tests/lvs下的Golden LVS用例并逐项比较；
6. 输出JSON和TXT两份机器/人工可读报告。

它不替代DRC和LVS，而是自动、重复地调用二者，防止PDK修改造成
已有功能退化。

推荐目录
--------
CNPDK/
├─ CNPDK.lyt
├─ CNPDK.lyp
├─ pymacros/
│  ├─ library.py
│  ├─ via_array.py
│  ├─ contact_array.py
│  ├─ nmos.py
│  ├─ pmos.py
│  ├─ guardring.py
│  ├─ rpposab.py
│  └─ mim.py
├─ drc/
│  └─ *.lydrc
├─ lvs/
│  └─ *.lylvs
├─ tests/
│  └─ lvs/
│     ├─ inverter/
│     │  ├─ inverter.gds
│     │  └─ inverter_reference.cir
│     └─ rc_load/
│        ├─ rc_load.gds
│        └─ rc_load_reference.cir
└─ tools/
   └─ CNPDK_regression.py

运行
----
放在CNPDK/tools后直接运行：

    python CNPDK_regression.py

指定KLayout：

    python CNPDK_regression.py --klayout "C:\\Program Files\\KLayout\\klayout.exe"

仅做静态和PCell测试，不跑DRC/LVS：

    python CNPDK_regression.py --skip-drc --skip-lvs

返回码
------
0：全部必测项目PASS；允许LVS测试目录不存在而显示SKIP
1：存在FAIL或ERROR
2：运行器自身配置错误
"""

from __future__ import print_function

import argparse
import datetime
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path


RUNNER_VERSION = "1.0"
PDK_NAME = "CNPDK"
LIBRARY_NAME = "CNPDK"
REPORT_DIR_RELATIVE = Path("tests") / "regression_output"
DEFAULT_TIMEOUT_SECONDS = 300

REQUIRED_ROOT_FILES = ("CNPDK.lyt", "CNPDK.lyp")
REQUIRED_DIRS = ("pymacros", "drc", "lvs", "tools")
REQUIRED_PCELL_FILES = (
    "library.py",
    "via_array.py",
    "contact_array.py",
    "nmos.py",
    "pmos.py",
    "guardring.py",
    "rpposab.py",
    "mim.py",
)

# 优先采用这些发布文件名；找不到时再自动选目录中的第一个相应deck。
DRC_DECK_CANDIDATES = (
    "CNPDK_complete_DRC.lydrc",
    "CNIC_PDK_DRC.lydrc",
    "CNPDK_DRC.lydrc",
)
LVS_DECK_CANDIDATES = (
    "CNPDK_complete_LVS.lylvs",
    "CNIC_PDK_LVS.lylvs",
    "CNPDK_LVS.lylvs",
)

TEXT_SUFFIXES = {
    ".py", ".lyt", ".lyp", ".lydrc", ".lylvs",
    ".txt", ".md", ".json", ".cir", ".spice",
}


# =====================================================================
# 1. 报告数据结构
# =====================================================================


class RegressionReport(object):
    def __init__(self, root):
        self.started_at = datetime.datetime.now().isoformat(timespec="seconds")
        self.finished_at = None
        self.pdk_root = str(root)
        self.runner_version = RUNNER_VERSION
        self.results = []
        self.metadata = {}

    def add(self, category, name, status, message, details=None, duration=None):
        item = {
            "category": str(category),
            "name": str(name),
            "status": str(status).upper(),
            "message": str(message),
        }
        if details is not None:
            item["details"] = details
        if duration is not None:
            item["duration_seconds"] = round(float(duration), 3)
        self.results.append(item)
        return item

    def finish(self):
        self.finished_at = datetime.datetime.now().isoformat(timespec="seconds")

    @property
    def counts(self):
        values = {}
        for item in self.results:
            status = item["status"]
            values[status] = values.get(status, 0) + 1
        return values

    @property
    def overall_status(self):
        statuses = {item["status"] for item in self.results}
        if "ERROR" in statuses or "FAIL" in statuses:
            return "FAIL"
        if "WARN" in statuses:
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def as_dict(self):
        return {
            "schema": "CNPDK_REGRESSION_REPORT_V1",
            "pdk": PDK_NAME,
            "runner_version": self.runner_version,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "pdk_root": self.pdk_root,
            "overall_status": self.overall_status,
            "counts": self.counts,
            "metadata": self.metadata,
            "results": self.results,
        }


# =====================================================================
# 2. 路径与进程辅助
# =====================================================================


def now_seconds():
    return datetime.datetime.now().timestamp()


def elapsed_since(start):
    return now_seconds() - start


def script_file():
    return Path(__file__).resolve()


def find_pdk_root(explicit=None):
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not root.is_dir():
            raise RuntimeError("指定的PDK根目录不存在：{}".format(root))
        return root

    current = script_file().parent
    for candidate in (current,) + tuple(current.parents):
        if all((candidate / name).is_file() for name in REQUIRED_ROOT_FILES):
            return candidate

    raise RuntimeError(
        "无法定位CNPDK根目录。请把脚本放在CNPDK/tools目录，"
        "或通过--pdk-root明确指定。"
    )


def discover_klayout(explicit=None):
    candidates = []
    if explicit:
        candidates.append(explicit)

    environment_value = os.environ.get("KLAYOUT_EXE")
    if environment_value:
        candidates.append(environment_value)

    for command in ("klayout", "klayout_app", "klayout.exe"):
        found = shutil.which(command)
        if found:
            candidates.append(found)

    if os.name == "nt":
        program_files = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        for base in program_files:
            if not base:
                continue
            candidates.extend([
                str(Path(base) / "KLayout" / "klayout.exe"),
                str(Path(base) / "KLayout" / "klayout_app.exe"),
            ])

    checked = []
    for value in candidates:
        path = Path(value).expanduser()
        checked.append(str(path))
        if path.is_file():
            return path.resolve(), checked
        found = shutil.which(str(value))
        if found:
            return Path(found).resolve(), checked

    return None, checked


def run_process(command, cwd, timeout):
    start = now_seconds()
    completed = subprocess.run(
        [str(value) for value in command],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "output": completed.stdout,
        "duration": elapsed_since(start),
        "command": [str(value) for value in command],
    }


def path_for_deck(path):
    """KLayout Ruby/Python字符串统一使用正斜杠。"""
    return str(Path(path).resolve()).replace("\\", "/")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_text(path):
    return path.read_text(encoding="utf-8-sig", errors="replace")


def shorten_output(text, maximum=12000):
    text = text or ""
    if len(text) <= maximum:
        return text
    return text[-maximum:]


# =====================================================================
# 3. 静态包检查
# =====================================================================


def static_package_checks(root, report):
    for filename in REQUIRED_ROOT_FILES:
        path = root / filename
        if path.is_file():
            report.add("STATIC", filename, "PASS", "核心文件存在")
        else:
            report.add("STATIC", filename, "FAIL", "缺少核心文件")

    for dirname in REQUIRED_DIRS:
        path = root / dirname
        if path.is_dir():
            report.add("STATIC", dirname + "/", "PASS", "目录存在")
        else:
            report.add("STATIC", dirname + "/", "FAIL", "目录不存在")

    pcell_dir = root / "pymacros"
    for filename in REQUIRED_PCELL_FILES:
        path = pcell_dir / filename
        if not path.is_file():
            report.add("PYTHON", filename, "FAIL", "缺少PCell文件")
            continue
        try:
            py_compile.compile(str(path), doraise=True)
            report.add("PYTHON", filename, "PASS", "Python语法检查通过")
        except Exception as error:
            report.add("PYTHON", filename, "FAIL", "Python语法错误", str(error))

    absolute_hits = []
    drive_pattern = re.compile(r"(?i)(?<![A-Za-z0-9_])[A-Z]:[\\/]")
    unix_pattern = re.compile(
        r"(?<![A-Za-z0-9_])/(?:home|Users|workspace|opt|mnt)/"
    )
    ignored_dirs = {
        "__pycache__", "regression_output", ".git",
    }

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in ignored_dirs for part in path.parts):
            continue
        try:
            text = read_text(path)
        except Exception:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") and "example" in stripped.lower():
                continue
            if drive_pattern.search(line) or unix_pattern.search(line):
                absolute_hits.append({
                    "file": str(path.relative_to(root)),
                    "line": line_number,
                    "text": stripped[:240],
                })

    if absolute_hits:
        report.add(
            "PORTABILITY",
            "absolute_path_scan",
            "WARN",
            "发现可能的绝对路径，请在发布前确认",
            absolute_hits[:50],
        )
    else:
        report.add(
            "PORTABILITY",
            "absolute_path_scan",
            "PASS",
            "未发现明显的用户/盘符绝对路径",
        )


# =====================================================================
# 4. PCell独立进程回归
# =====================================================================


def pcell_worker_source(root, result_path, gds_path):
    pcell_dir = root / "pymacros"

    cases = [
        ("NMOS", {"w": 1.0, "l": 0.28, "nf": 1,
                  "gate_contact_position": 0, "add_labels": True}),
        ("NMOS", {"w": 2.0, "l": 0.28, "nf": 2,
                  "gate_contact_position": 1, "add_labels": True}),
        ("NMOS", {"w": 4.0, "l": 0.28, "nf": 4,
                  "gate_contact_position": 2, "add_labels": True}),
        ("NMOS", {"w": 8.0, "l": 1.00, "nf": 4,
                  "gate_contact_position": 1, "add_labels": True}),
        ("PMOS", {"w": 1.0, "l": 0.28, "nf": 1,
                  "gate_contact_position": 0, "add_labels": True}),
        ("PMOS", {"w": 2.0, "l": 0.28, "nf": 2,
                  "gate_contact_position": 1, "add_labels": True}),
        ("PMOS", {"w": 4.0, "l": 0.28, "nf": 4,
                  "gate_contact_position": 2, "add_labels": True}),
        ("PMOS", {"w": 8.0, "l": 1.00, "nf": 4,
                  "gate_contact_position": 1, "add_labels": True}),
        ("电阻P_PO_SAB",
         {"length": 5.0, "width": 1.0, "sheet_resistance": 311.0}),
        ("电阻P_PO_SAB",
         {"length": 20.0, "width": 2.0, "sheet_resistance": 311.0}),
        ("电容MIM",
         {"length": 5.0, "width": 5.0, "cap_density": 0.002}),
        ("电容MIM",
         {"length": 20.0, "width": 20.0, "cap_density": 0.002}),
        ("金属通孔",
         {"via_type": 1, "cut": 0.26, "spacing": 0.26,
          "rows": 1, "columns": 1,
          "bottom_enclosure": 0.06, "top_enclosure": 0.06}),
        ("金属通孔",
         {"via_type": 2, "cut": 0.26, "spacing": 0.26,
          "rows": 4, "columns": 4,
          "bottom_enclosure": 0.06, "top_enclosure": 0.06}),
        ("接触孔",
         {"contact_type": 0, "cut": 0.22, "spacing": 0.25,
          "rows": 1, "columns": 1,
          "bottom_enclosure": 0.07, "metal1_enclosure": 0.06}),
        ("接触孔",
         {"contact_type": 1, "cut": 0.22, "spacing": 0.25,
          "rows": 4, "columns": 4,
          "bottom_enclosure": 0.07, "metal1_enclosure": 0.06}),
        ("GuardRing",
         {"ring_type": 0, "inner_width": 5.0, "inner_height": 5.0}),
        ("GuardRing",
         {"ring_type": 1, "inner_width": 10.0, "inner_height": 5.0}),
    ]

    # repr产生合法Python字面量；路径统一正斜杠，避免Windows反斜杠转义。
    return r'''# -*- coding: utf-8 -*-
import json
import runpy
import sys
import traceback
import pya

PCELL_DIR = {pcell_dir!r}
RESULT_PATH = {result_path!r}
GDS_PATH = {gds_path!r}
CASES = {cases!r}

results = []
payload = {{"status": "FAIL", "cases": results}}

try:
    if PCELL_DIR not in sys.path:
        sys.path.insert(0, PCELL_DIR)

    runpy.run_path(PCELL_DIR + "/library.py", run_name="__main__")
    library = pya.Library.library_by_name("CNPDK")
    if library is None:
        raise RuntimeError("CNPDK Library registration failed")

    layout = pya.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("CNPDK_REGRESSION_PCELL")

    x_cursor = 0
    y_cursor = 0
    row_height = 0
    per_row = 4
    spacing = int(round(20.0 / layout.dbu))

    for index, (pcell_name, parameters) in enumerate(CASES):
        case = {{
            "index": index + 1,
            "pcell": pcell_name,
            "parameters": parameters,
        }}
        try:
            declaration = library.layout().pcell_declaration(pcell_name)
            if declaration is None:
                raise RuntimeError("PCell declaration not found")

            cell_index = layout.add_pcell_variant(
                library, declaration.id(), parameters
            )
            cell = layout.cell(cell_index)
            if cell is None or cell.is_empty():
                raise RuntimeError("PCell generated an empty cell")

            bbox = cell.bbox()
            if bbox.empty() or bbox.width() <= 0 or bbox.height() <= 0:
                raise RuntimeError("PCell bounding box is empty")

            if index > 0 and index % per_row == 0:
                x_cursor = 0
                y_cursor += row_height + spacing
                row_height = 0

            transform = pya.Trans(
                x_cursor - bbox.left,
                y_cursor - bbox.bottom,
            )
            top.insert(pya.CellInstArray(cell_index, transform))
            x_cursor += bbox.width() + spacing
            row_height = max(row_height, bbox.height())

            case["status"] = "PASS"
            case["bbox_dbu"] = [
                bbox.left, bbox.bottom, bbox.right, bbox.top
            ]
        except Exception as error:
            case["status"] = "FAIL"
            case["error"] = str(error)
        results.append(case)

    layout.write(GDS_PATH)
    payload["status"] = (
        "PASS"
        if results and all(item["status"] == "PASS" for item in results)
        else "FAIL"
    )
    payload["gds_path"] = GDS_PATH
    payload["case_count"] = len(results)

except Exception as error:
    payload["status"] = "ERROR"
    payload["error"] = str(error)
    payload["traceback"] = traceback.format_exc()

with open(RESULT_PATH, "w", encoding="utf-8") as stream:
    json.dump(payload, stream, ensure_ascii=False, indent=2)

if payload["status"] != "PASS":
    raise RuntimeError("CNPDK PCell regression failed")
'''.format(
        pcell_dir=path_for_deck(pcell_dir),
        result_path=path_for_deck(result_path),
        gds_path=path_for_deck(gds_path),
        cases=cases,
    )


def run_pcell_regression(root, klayout, output_dir, report, timeout):
    worker = output_dir / "_pcell_regression_worker.py"
    result_path = output_dir / "pcell_results.json"
    gds_path = output_dir / "CNPDK_regression_pcell.gds"
    write_text(worker, pcell_worker_source(root, result_path, gds_path))

    process = run_process(
        [klayout, "-b", "-r", worker],
        cwd=root,
        timeout=timeout,
    )

    if result_path.is_file():
        try:
            payload = json.loads(read_text(result_path))
        except Exception as error:
            report.add(
                "PCELL", "parameter_matrix", "ERROR",
                "PCell结果JSON无法读取",
                {"error": str(error), "log": shorten_output(process["output"])},
                process["duration"],
            )
            return None
    else:
        report.add(
            "PCELL", "parameter_matrix", "ERROR",
            "KLayout没有生成PCell结果文件",
            {
                "returncode": process["returncode"],
                "log": shorten_output(process["output"]),
            },
            process["duration"],
        )
        return None

    status = payload.get("status", "ERROR")
    message = "固定PCell矩阵通过，共{}个实例".format(
        payload.get("case_count", 0)
    )
    if status != "PASS":
        message = "PCell矩阵存在失败项"

    report.add(
        "PCELL", "parameter_matrix", status, message,
        {
            "cases": payload.get("cases", []),
            "returncode": process["returncode"],
            "gds": str(gds_path.relative_to(root)),
            "log": shorten_output(process["output"]),
        },
        process["duration"],
    )
    return gds_path if status == "PASS" and gds_path.is_file() else None


# =====================================================================
# 5. DRC回归
# =====================================================================


def discover_deck(directory, candidates, suffix):
    for name in candidates:
        path = directory / name
        if path.is_file():
            return path
    matches = sorted(directory.glob("*" + suffix))
    return matches[0] if matches else None


def make_drc_deck(original, gds_path, report_path, generated_path):
    text = read_text(original)

    # 删除已有显式source，避免两次设置source；当前CNPDK总DRC通常没有source。
    text = re.sub(
        r"(?m)^\s*source\s*\([^\n]*\)\s*$",
        "",
        text,
        count=1,
    )

    report_pattern = re.compile(
        r'report\s*\(\s*"([^"]*)"\s*\)',
        re.MULTILINE,
    )
    replacement = 'report("\\1", "{}")'.format(path_for_deck(report_path))
    text, count = report_pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(
            "DRC deck中没有找到单参数report(\"...\")，无法注入报告路径。"
        )

    prefix = 'source("{}")\n\n'.format(path_for_deck(gds_path))
    write_text(generated_path, prefix + text)


def count_lyrdb_markers(path):
    if not path.is_file():
        raise RuntimeError("DRC报告文件不存在")

    try:
        root = ET.parse(str(path)).getroot()
        return sum(1 for element in root.iter() if element.tag.endswith("item"))
    except Exception:
        text = read_text(path)
        return len(re.findall(r"<item(?:\s|>)", text))


def run_drc_regression(root, klayout, gds_path, output_dir, report, timeout):
    drc_dir = root / "drc"
    deck = discover_deck(drc_dir, DRC_DECK_CANDIDATES, ".lydrc")
    if deck is None:
        report.add("DRC", "pcell_matrix", "FAIL", "没有找到整合DRC deck")
        return

    generated_deck = output_dir / "_regression_drc.lydrc"
    marker_db = output_dir / "CNPDK_regression_DRC.lyrdb"

    try:
        make_drc_deck(deck, gds_path, marker_db, generated_deck)
    except Exception as error:
        report.add("DRC", "pcell_matrix", "ERROR", str(error))
        return

    process = run_process(
        [klayout, "-b", "-r", generated_deck],
        cwd=root,
        timeout=timeout,
    )

    if process["returncode"] != 0:
        report.add(
            "DRC", "pcell_matrix", "ERROR",
            "KLayout DRC进程执行失败",
            {
                "deck": str(deck.relative_to(root)),
                "returncode": process["returncode"],
                "log": shorten_output(process["output"]),
            },
            process["duration"],
        )
        return

    try:
        marker_count = count_lyrdb_markers(marker_db)
    except Exception as error:
        report.add(
            "DRC", "pcell_matrix", "ERROR",
            "无法统计DRC marker：{}".format(error),
            {"log": shorten_output(process["output"])},
            process["duration"],
        )
        return

    status = "PASS" if marker_count == 0 else "FAIL"
    report.add(
        "DRC", "pcell_matrix", status,
        "DRC marker数量：{}".format(marker_count),
        {
            "deck": str(deck.relative_to(root)),
            "marker_database": str(marker_db.relative_to(root)),
            "marker_count": marker_count,
            "log": shorten_output(process["output"]),
        },
        process["duration"],
    )


# =====================================================================
# 6. LVS Golden测试
# =====================================================================


def find_lvs_cases(root):
    base = root / "tests" / "lvs"
    if not base.is_dir():
        return []

    cases = []
    for gds in sorted(base.rglob("*.gds")):
        preferred = gds.with_name(gds.stem + "_reference.cir")
        references = []
        if preferred.is_file():
            references = [preferred]
        else:
            references = sorted(gds.parent.glob("*_reference.cir"))
        if references:
            cases.append({
                "name": str(gds.relative_to(base).with_suffix("")),
                "gds": gds,
                "reference": references[0],
            })
    return cases


def make_lvs_deck(original, gds_path, status_path, generated_path):
    text = read_text(original)

    # 当前整合LVS通过source.path查找同目录reference，因此将source设置为
    # 本测试GDS即可，不修改top名称。
    prefix = 'source("{}")\n\n'.format(path_for_deck(gds_path))

    # 原规则中已有：lvs_success = compare
    # 在同一Ruby/DSL作用域中把布尔值写出，避免仅凭进程返回码猜测LVS。
    suffix = r'''

# CNPDK regression status hook
File.open("{status}", "w") do |stream|
  stream.write(lvs_success ? "PASS" : "FAIL")
end
'''.format(status=path_for_deck(status_path))

    if "lvs_success = compare" not in text:
        raise RuntimeError(
            "LVS deck缺少'lvs_success = compare'，无法自动取得比较结果。"
        )

    write_text(generated_path, prefix + text + suffix)


def run_one_lvs_case(root, klayout, deck, case, output_dir, report, timeout):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", case["name"])
    generated_deck = output_dir / ("_lvs_{}.lylvs".format(safe_name))
    status_file = output_dir / ("lvs_{}.status".format(safe_name))

    # 整合LVS会从GDS目录查找reference。若用例文件名不满足首选命名，
    # 仍会选择该目录最新的*_reference.cir。每个用例应放在独立子目录。
    try:
        make_lvs_deck(deck, case["gds"], status_file, generated_deck)
    except Exception as error:
        report.add("LVS", case["name"], "ERROR", str(error))
        return

    process = run_process(
        [klayout, "-b", "-r", generated_deck],
        cwd=case["gds"].parent,
        timeout=timeout,
    )

    if process["returncode"] != 0:
        report.add(
            "LVS", case["name"], "ERROR",
            "KLayout LVS进程执行失败",
            {
                "gds": str(case["gds"].relative_to(root)),
                "reference": str(case["reference"].relative_to(root)),
                "returncode": process["returncode"],
                "log": shorten_output(process["output"]),
            },
            process["duration"],
        )
        return

    if not status_file.is_file():
        report.add(
            "LVS", case["name"], "ERROR",
            "LVS没有写出PASS/FAIL状态",
            {"log": shorten_output(process["output"])},
            process["duration"],
        )
        return

    status = read_text(status_file).strip().upper()
    if status not in ("PASS", "FAIL"):
        status = "ERROR"

    report.add(
        "LVS", case["name"], status,
        "版图与参考网表{}".format("匹配" if status == "PASS" else "不匹配"),
        {
            "gds": str(case["gds"].relative_to(root)),
            "reference": str(case["reference"].relative_to(root)),
            "deck": str(deck.relative_to(root)),
            "log": shorten_output(process["output"]),
        },
        process["duration"],
    )


def run_lvs_regression(root, klayout, output_dir, report, timeout):
    lvs_dir = root / "lvs"
    deck = discover_deck(lvs_dir, LVS_DECK_CANDIDATES, ".lylvs")
    if deck is None:
        report.add("LVS", "golden_cases", "FAIL", "没有找到整合LVS deck")
        return

    cases = find_lvs_cases(root)
    if not cases:
        report.add(
            "LVS", "golden_cases", "SKIP",
            "tests/lvs中没有发现GDS + *_reference.cir用例；"
            "这不会阻止首次运行，但发布前建议加入反相器和RC负载用例。",
        )
        return

    report.metadata["lvs_case_count"] = len(cases)
    for case in cases:
        run_one_lvs_case(
            root, klayout, deck, case, output_dir, report, timeout
        )


# =====================================================================
# 7. 报告输出
# =====================================================================


def write_reports(report, output_dir):
    report.finish()
    json_path = output_dir / "CNPDK_regression_report.json"
    txt_path = output_dir / "CNPDK_regression_report.txt"

    write_text(
        json_path,
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2),
    )

    lines = [
        "CNPDK AUTOMATED REGRESSION REPORT",
        "=" * 72,
        "Overall Status : {}".format(report.overall_status),
        "Started        : {}".format(report.started_at),
        "Finished       : {}".format(report.finished_at),
        "PDK Root       : {}".format(report.pdk_root),
        "Counts         : {}".format(
            ", ".join(
                "{}={}".format(key, value)
                for key, value in sorted(report.counts.items())
            )
        ),
        "",
    ]

    for item in report.results:
        lines.append(
            "[{status:<5}] {category:<12} {name}".format(**item)
        )
        lines.append("        " + item["message"])
        if "duration_seconds" in item:
            lines.append(
                "        Duration: {} s".format(item["duration_seconds"])
            )
    lines.extend([
        "",
        "JSON report: {}".format(json_path),
    ])
    write_text(txt_path, "\n".join(lines) + "\n")
    return json_path, txt_path


def print_summary(report, json_path, txt_path):
    print("")
    print("=" * 72)
    print("CNPDK REGRESSION: {}".format(report.overall_status))
    print("=" * 72)
    for status, count in sorted(report.counts.items()):
        print("{:<20} {}".format(status, count))
    print("JSON: {}".format(json_path))
    print("TXT : {}".format(txt_path))


# =====================================================================
# 8. 主程序
# =====================================================================


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="CNPDK automated regression runner"
    )
    parser.add_argument(
        "--pdk-root",
        help="CNPDK根目录；默认根据脚本位置向上自动查找",
    )
    parser.add_argument(
        "--klayout",
        help="klayout.exe/klayout_app.exe路径；也可设置KLAYOUT_EXE",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="每个KLayout任务最大秒数，默认300",
    )
    parser.add_argument("--skip-pcell", action="store_true")
    parser.add_argument("--skip-drc", action="store_true")
    parser.add_argument("--skip-lvs", action="store_true")
    return parser.parse_args()


def main():
    try:
        args = parse_arguments()
        root = find_pdk_root(args.pdk_root)
    except Exception as error:
        print("CNPDK regression configuration error: {}".format(error))
        return 2

    output_dir = root / REPORT_DIR_RELATIVE
    output_dir.mkdir(parents=True, exist_ok=True)
    report = RegressionReport(root)

    static_package_checks(root, report)

    klayout, checked = discover_klayout(args.klayout)
    report.metadata["klayout_candidates_checked"] = checked

    needs_klayout = not (
        args.skip_pcell and args.skip_drc and args.skip_lvs
    )
    if klayout is None and needs_klayout:
        report.add(
            "ENVIRONMENT", "klayout", "FAIL",
            "没有找到KLayout可执行文件。请使用--klayout或设置KLAYOUT_EXE。",
            checked,
        )
        json_path, txt_path = write_reports(report, output_dir)
        print_summary(report, json_path, txt_path)
        return 1

    if klayout is not None:
        report.metadata["klayout_executable"] = str(klayout)
        version_process = run_process(
            [klayout, "-v"], cwd=root, timeout=min(args.timeout, 20)
        )
        report.add(
            "ENVIRONMENT", "klayout", "PASS",
            shorten_output(version_process["output"], 1000).strip()
            or "检测到KLayout",
            {"executable": str(klayout)},
            version_process["duration"],
        )

    pcell_gds = None
    if args.skip_pcell:
        report.add("PCELL", "parameter_matrix", "SKIP", "用户跳过PCell回归")
    elif klayout is not None:
        pcell_gds = run_pcell_regression(
            root, klayout, output_dir, report, args.timeout
        )

    if args.skip_drc:
        report.add("DRC", "pcell_matrix", "SKIP", "用户跳过DRC回归")
    elif pcell_gds is None:
        report.add(
            "DRC", "pcell_matrix", "SKIP",
            "PCell测试GDS未成功生成，因此未运行DRC",
        )
    else:
        run_drc_regression(
            root, klayout, pcell_gds, output_dir, report, args.timeout
        )

    if args.skip_lvs:
        report.add("LVS", "golden_cases", "SKIP", "用户跳过LVS回归")
    elif klayout is not None:
        run_lvs_regression(
            root, klayout, output_dir, report, args.timeout
        )

    json_path, txt_path = write_reports(report, output_dir)
    print_summary(report, json_path, txt_path)
    return 0 if report.overall_status != "FAIL" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("CNPDK regression interrupted by user")
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        sys.exit(2)