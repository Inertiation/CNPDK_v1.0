# -*- coding: utf-8 -*-
"""
CNPDK Portable Installer and Environment Checker v1.0
======================================================

建议放置位置
------------
CNPDK/tools/CNPDK_install_check.py

路径策略
--------
脚本以自身位置为基准定位PDK根目录，不写死盘符、用户名或安装路径。
安装时会把目标CNPDK.lyt中的Layer Properties引用改成相对路径：

    CNPDK.lyp

默认行为仅检查，不修改或复制任何文件。

命令行示例
----------
只检查当前PDK：
    python CNPDK_install_check.py --check

安装到指定KLayout tech目录：
    python CNPDK_install_check.py --install --target "C:\\Users\\me\\KLayout\\tech"

覆盖已有CNPDK安装：
    python CNPDK_install_check.py --install --target "..." --force

仅把当前CNPDK.lyt改成可移植相对路径：
    python CNPDK_install_check.py --repair-lyt

报告默认写入：
    CNPDK/tools/reports/CNPDK_environment_report.txt
"""

from __future__ import print_function

import argparse
import datetime
import os
import platform
import py_compile
import re
import shutil
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path


PDK_NAME = "CNPDK"
SCRIPT_VERSION = "1.0"
MIN_KLAYOUT_VERSION = (0, 28, 0)

REQUIRED_DIRS = ("drc", "lvs", "pymacros", "tools")
REQUIRED_ROOT_FILES = ("CNPDK.lyt", "CNPDK.lyp")
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

EXPECTED_LAYERS = {
    (21, 0): "N-Well",
    (22, 0): "Active",
    (30, 0): "Poly",
    (31, 0): "P+ Implant",
    (32, 0): "N+ Implant",
    (33, 0): "Contact",
    (34, 0): "Metal1",
    (35, 0): "Via1",
    (36, 0): "Metal2",
    (38, 0): "Via2",
    (42, 0): "Metal3",
    (49, 0): "Silicide Block",
    (75, 0): "FuseTop",
    (110, 5): "Resistor Mark",
    (117, 5): "Capacitor Mark",
    (22, 10): "Active Label",
    (30, 10): "Poly Label",
    (34, 10): "Metal1 Label",
    (36, 10): "Metal2 Label",
    (42, 10): "Metal3 Label",
}

TEXT_EXTENSIONS = {
    ".py", ".lyt", ".lyp", ".lym", ".lydrc", ".lylvs",
    ".txt", ".md", ".json", ".xml", ".cir", ".spice",
}


class Results(object):
    def __init__(self):
        self.passed = []
        self.warnings = []
        self.errors = []
        self.info = []

    def ok(self, message):
        self.passed.append(message)

    def warn(self, message):
        self.warnings.append(message)

    def error(self, message):
        self.errors.append(message)

    def note(self, message):
        self.info.append(message)

    @property
    def status(self):
        if self.errors:
            return "FAIL"
        if self.warnings:
            return "PASS WITH WARNINGS"
        return "PASS"


def script_path():
    try:
        return Path(__file__).resolve()
    except NameError:
        return Path.cwd() / "CNPDK_install_check.py"


def find_pdk_root(start=None):
    """从脚本目录向上寻找同时包含CNPDK.lyt和CNPDK.lyp的目录。"""
    current = Path(start or script_path().parent).resolve()
    for candidate in (current,) + tuple(current.parents):
        if all((candidate / name).is_file() for name in REQUIRED_ROOT_FILES):
            return candidate
    raise RuntimeError(
        "无法定位CNPDK根目录。请把本脚本放入CNPDK/tools目录，"
        "并确认CNPDK.lyt与CNPDK.lyp存在。"
    )


def is_absolute_reference(text):
    value = (text or "").strip()
    if not value:
        return False
    return (
        bool(re.match(r"^[A-Za-z]:[\\/]", value))
        or value.startswith("/")
        or value.startswith("\\\\")
        or value.startswith("~")
    )


def relative_display(path, root):
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def parse_version(text):
    numbers = re.findall(r"\d+", text or "")
    if not numbers:
        return None
    values = [int(value) for value in numbers[:3]]
    while len(values) < 3:
        values.append(0)
    return tuple(values)


def detect_klayout_runtime():
    """返回(runtime_name, version_text, pya_module)。"""
    try:
        import pya
        version = ""
        try:
            version = str(pya.Application.instance().version())
        except Exception:
            version = "unknown"
        return "KLayout embedded Python", version, pya
    except Exception:
        pass

    commands = (["klayout", "-v"], ["klayout_app", "-v"])
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
                check=False,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                return command[0], completed.stdout.strip(), None
        except Exception:
            continue
    return None, None, None


def check_klayout(results):
    runtime, version_text, pya_module = detect_klayout_runtime()
    if runtime is None:
        results.warn(
            "当前Python环境未找到KLayout；文件检查仍可完成。"
            "如需验证Library注册，请在KLayout中运行本脚本。"
        )
        return

    results.ok("检测到{}：{}".format(runtime, version_text))
    version = parse_version(version_text)
    if version and version < MIN_KLAYOUT_VERSION:
        results.warn(
            "KLayout版本{}低于建议版本{}。".format(
                ".".join(map(str, version)),
                ".".join(map(str, MIN_KLAYOUT_VERSION)),
            )
        )

    if pya_module is not None:
        try:
            library = pya_module.Library.library_by_name(PDK_NAME)
            if library is None:
                results.warn(
                    "KLayout当前会话尚未注册CNPDK Library；"
                    "请运行pymacros/library.py或设置其Run on start-up。"
                )
            else:
                results.ok("KLayout当前会话已注册CNPDK Library。")
        except Exception as error:
            results.warn("无法检查CNPDK Library注册状态：{}".format(error))


def check_structure(root, results):
    for dirname in REQUIRED_DIRS:
        path = root / dirname
        if path.is_dir():
            results.ok("目录存在：{}".format(dirname))
        else:
            results.error("缺少目录：{}".format(dirname))

    for filename in REQUIRED_ROOT_FILES:
        path = root / filename
        if path.is_file():
            results.ok("根文件存在：{}".format(filename))
        else:
            results.error("缺少根文件：{}".format(filename))

    pcell_dir = root / "pymacros"
    for filename in REQUIRED_PCELL_FILES:
        path = pcell_dir / filename
        if path.is_file():
            results.ok("PCell文件存在：pymacros/{}".format(filename))
        else:
            results.error("缺少PCell文件：pymacros/{}".format(filename))

    drc_files = sorted((root / "drc").glob("*.lydrc"))
    lvs_files = sorted((root / "lvs").glob("*.lylvs"))
    if drc_files:
        results.ok("找到DRC规则文件{}个。".format(len(drc_files)))
    else:
        results.error("drc目录中没有找到*.lydrc文件。")
    if lvs_files:
        results.ok("找到LVS规则文件{}个。".format(len(lvs_files)))
    else:
        results.error("lvs目录中没有找到*.lylvs文件。")


def xml_text(root_element, name):
    element = root_element.find(name)
    return "" if element is None or element.text is None else element.text.strip()


def check_technology_file(root, results):
    tech_path = root / "CNPDK.lyt"
    if not tech_path.is_file():
        return
    try:
        tree = ET.parse(str(tech_path))
        technology = tree.getroot()
    except Exception as error:
        results.error("CNPDK.lyt不是有效XML：{}".format(error))
        return

    name = xml_text(technology, "name")
    dbu = xml_text(technology, "dbu")
    layer_file = xml_text(technology, "layer-properties_file")
    base_path = xml_text(technology, "base-path")
    original_base = xml_text(technology, "original-base-path")

    if name == PDK_NAME:
        results.ok("Technology名称正确：CNPDK")
    else:
        results.error("Technology名称应为CNPDK，当前为：{}".format(name))

    try:
        if abs(float(dbu) - 0.001) < 1e-12:
            results.ok("Technology DBU正确：0.001um")
        else:
            results.warn("Technology DBU不是预期的0.001um：{}".format(dbu))
    except Exception:
        results.error("CNPDK.lyt中的DBU无效：{}".format(dbu))

    if not layer_file:
        results.error("CNPDK.lyt没有设置layer-properties_file。")
    elif is_absolute_reference(layer_file):
        results.error(
            "CNPDK.lyt仍使用绝对Layer Properties路径：{}".format(
                layer_file
            )
        )
    else:
        resolved = (root / layer_file).resolve()
        if resolved.is_file():
            results.ok(
                "Layer Properties使用有效相对路径：{}".format(layer_file)
            )
        else:
            results.error(
                "Layer Properties相对路径无法解析：{} -> {}".format(
                    layer_file, resolved
                )
            )

    if is_absolute_reference(base_path):
        results.warn("base-path使用绝对路径：{}".format(base_path))
    if is_absolute_reference(original_base):
        results.warn(
            "original-base-path保留了旧电脑路径：{}".format(original_base)
        )


def repair_technology_file(root, results):
    """把CNPDK.lyt改为相对于Technology目录的可移植引用。"""
    tech_path = root / "CNPDK.lyt"
    tree = ET.parse(str(tech_path))
    technology = tree.getroot()

    def set_text(name, value):
        element = technology.find(name)
        if element is None:
            element = ET.SubElement(technology, name)
        element.text = value

    set_text("base-path", ".")
    set_text("original-base-path", "")
    set_text("layer-properties_file", "CNPDK.lyp")
    tree.write(str(tech_path), encoding="utf-8", xml_declaration=True)
    results.ok("已把CNPDK.lyt修复为相对路径引用。")


def extract_lyp_layers(lyp_path):
    text = lyp_path.read_text(encoding="utf-8", errors="replace")
    layers = set()
    for layer, datatype in re.findall(r"\s(\d+)/(\d+)@(?:\d+)", text):
        layers.add((int(layer), int(datatype)))
    return layers


def check_layers(root, results):
    path = root / "CNPDK.lyp"
    if not path.is_file():
        return
    try:
        actual = extract_lyp_layers(path)
    except Exception as error:
        results.error("无法读取CNPDK.lyp：{}".format(error))
        return

    missing = [
        "{}/{} ({})".format(layer, datatype, name)
        for (layer, datatype), name in sorted(EXPECTED_LAYERS.items())
        if (layer, datatype) not in actual
    ]
    if missing:
        results.error("CNPDK.lyp缺少关键图层：" + "；".join(missing))
    else:
        results.ok(
            "CNPDK.lyp包含全部{}个关键图层。".format(
                len(EXPECTED_LAYERS)
            )
        )


def check_python_sources(root, results):
    pcell_dir = root / "pymacros"
    checked = 0
    for filename in REQUIRED_PCELL_FILES:
        path = pcell_dir / filename
        if not path.is_file():
            continue
        try:
            source = path.read_text(encoding="utf-8-sig")
            compile(source, str(path), "exec")
            checked += 1
        except Exception as error:
            results.error(
                "Python语法错误 {}：{}".format(
                    relative_display(path, root), error
                )
            )
    if checked:
        results.ok("PCell Python语法检查通过：{}个文件。".format(checked))


def iter_text_files(root):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or "reports" in path.parts:
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def check_absolute_paths(root, results):
    windows_pattern = re.compile(
        r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/][^\\r\\n<>\"]+"
    )
    unix_pattern = re.compile(
        r"(?<![A-Za-z0-9_])/(?:home|Users|opt|usr|var|tmp)/[^\\s<>\"]+"
    )
    findings = []
    self_name = script_path().name

    for path in iter_text_files(root):
        if path.name == self_name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            matches = windows_pattern.findall(line) + unix_pattern.findall(line)
            for match in matches:
                findings.append(
                    "{}:{} -> {}".format(
                        relative_display(path, root),
                        line_number,
                        match.strip(),
                    )
                )

    if findings:
        results.warn(
            "发现可能影响移植的绝对路径{}处：\n    {}".format(
                len(findings), "\n    ".join(findings[:20])
            )
        )
        if len(findings) > 20:
            results.warn("其余绝对路径未在摘要中展开。")
    else:
        results.ok("未在PDK文本文件中发现绝对路径。")


def default_tech_target():
    home = Path.home()
    candidates = []
    if os.name == "nt":
        candidates.append(home / "KLayout" / "tech")
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "KLayout" / "tech")
    else:
        candidates.append(home / ".klayout" / "tech")
        candidates.append(home / "KLayout" / "tech")

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def install_pdk(source_root, tech_target, force, results):
    tech_target = Path(tech_target).expanduser().resolve()
    destination = tech_target / PDK_NAME

    if destination.exists() and not force:
        raise RuntimeError(
            "目标已存在：{}\n"
            "为保护现有PDK，安装已停止。确认覆盖时请增加--force。"
            .format(destination)
        )

    tech_target.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(str(destination))

    def ignore(directory, names):
        ignored = {
            name for name in names
            if name in ("__pycache__", "reports")
            or name.endswith((".pyc", ".pyo"))
        }
        return ignored

    shutil.copytree(str(source_root), str(destination), ignore=ignore)
    repair_technology_file(destination, results)
    results.ok("CNPDK已安装到：{}".format(destination))
    results.note(
        "请重启KLayout，使tech目录和启动宏重新加载。"
    )
    return destination


def run_checks(root):
    results = Results()
    results.note("PDK根目录：{}".format(root))
    results.note("操作系统：{} {}".format(platform.system(), platform.release()))
    results.note("Python：{}".format(sys.version.replace("\n", " ")))
    check_structure(root, results)
    check_technology_file(root, results)
    check_layers(root, results)
    check_python_sources(root, results)
    check_absolute_paths(root, results)
    check_klayout(results)
    return results


def format_report(root, results):
    lines = [
        "CNPDK Installation and Environment Report",
        "=" * 58,
        "Generated : {}".format(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ),
        "Checker   : v{}".format(SCRIPT_VERSION),
        "PDK Root  : {}".format(root),
        "Status    : {}".format(results.status),
        "",
    ]

    sections = (
        ("INFORMATION", results.info),
        ("PASS", results.passed),
        ("WARNING", results.warnings),
        ("ERROR", results.errors),
    )
    for title, items in sections:
        lines.append("[{}] {}".format(title, len(items)))
        if items:
            for index, item in enumerate(items, 1):
                lines.append("{}. {}".format(index, item))
        else:
            lines.append("(none)")
        lines.append("")

    lines.extend([
        "Summary",
        "-" * 58,
        "Passed   : {}".format(len(results.passed)),
        "Warnings : {}".format(len(results.warnings)),
        "Errors   : {}".format(len(results.errors)),
        "Result   : {}".format(results.status),
        "",
    ])
    return "\n".join(lines)


def write_report(root, report_text):
    report_dir = root / "tools" / "reports"
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "CNPDK_environment_report.txt"
        report_path.write_text(report_text, encoding="utf-8")
        return report_path
    except Exception:
        fallback = Path.cwd() / "CNPDK_environment_report.txt"
        fallback.write_text(report_text, encoding="utf-8")
        return fallback


def show_klayout_message(report_path, results):
    try:
        import pya
        message = (
            "CNPDK检查完成\n\n"
            "结果：{}\n"
            "通过：{}\n警告：{}\n错误：{}\n\n"
            "报告：{}"
        ).format(
            results.status,
            len(results.passed),
            len(results.warnings),
            len(results.errors),
            report_path,
        )
        if results.errors:
            pya.MessageBox.critical(
                "CNPDK环境检查", message, pya.MessageBox.Ok
            )
        else:
            pya.MessageBox.info(
                "CNPDK环境检查", message, pya.MessageBox.Ok
            )
    except Exception:
        pass


def build_parser():
    parser = argparse.ArgumentParser(
        description="CNPDK可移植安装与环境检查工具"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="检查当前CNPDK（默认行为）",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="把当前CNPDK复制到KLayout tech目录后检查",
    )
    parser.add_argument(
        "--target",
        help="KLayout tech目录；默认自动检测用户目录",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允许覆盖目标tech/CNPDK目录",
    )
    parser.add_argument(
        "--repair-lyt",
        action="store_true",
        help="把当前CNPDK.lyt改成相对路径引用",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args, _unknown = parser.parse_known_args(argv)

    try:
        root = find_pdk_root()
        operation_results = Results()

        if args.install:
            target = Path(args.target) if args.target else default_tech_target()
            root = install_pdk(root, target, args.force, operation_results)
        elif args.repair_lyt:
            repair_technology_file(root, operation_results)

        results = run_checks(root)
        results.passed[0:0] = operation_results.passed
        results.warnings[0:0] = operation_results.warnings
        results.errors[0:0] = operation_results.errors
        results.info[0:0] = operation_results.info

        report_text = format_report(root, results)
        report_path = write_report(root, report_text)
        print(report_text)
        print("Report:", report_path)
        show_klayout_message(report_path, results)
        return 2 if results.errors else 0

    except Exception as error:
        message = "CNPDK安装/检查失败：{}\n{}".format(
            error, traceback.format_exc()
        )
        print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    exit_code = main()
    # KLayout宏环境中抛出SystemExit可能显示成脚本异常；命令行环境
    # 才返回进程退出码。
    try:
        import pya
        _inside_klayout = pya.Application.instance() is not None
    except Exception:
        _inside_klayout = False
    if not _inside_klayout:
        sys.exit(exit_code)