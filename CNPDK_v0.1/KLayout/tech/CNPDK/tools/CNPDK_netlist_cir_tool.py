# -*- coding: utf-8 -*-

import pya
import os
import re


# ============================================================
# CNPDK通用Virtuoso CDL转换宏
# ============================================================

# Virtuoso默认输出文件名称
INPUT_FILE_CANDIDATES = [
    "netlist",
    "netlist.cdl",
    "netlist.sp",
    "netlist.spi",
    "netlist.cir"
]

# 已知电阻模型及其方块电阻，单位：ohm/square
RESISTOR_SHEET_RESISTANCE = {
    "CNPDK_RPPOLY": 311.0
}


# ============================================================
# 消息窗口
# ============================================================

def show_info(message):

    pya.MessageBox.info(
        "CNPDK通用网表转换",
        message,
        pya.MessageBox.Ok
    )


def show_error(message):

    pya.MessageBox.critical(
        "CNPDK网表转换错误",
        message,
        pya.MessageBox.Ok
    )


# ============================================================
# 当前GDS目录
# ============================================================

def get_layout_directory():

    main_window = pya.Application.instance().main_window()
    layout_view = main_window.current_view()

    if layout_view is None:
        raise RuntimeError("当前没有打开任何版图。")

    cell_view = layout_view.active_cellview()
    layout_filename = cell_view.filename()

    if not layout_filename:
        raise RuntimeError(
            "当前版图尚未保存。\n"
            "请先保存GDS，再运行转换宏。"
        )

    return os.path.dirname(
        os.path.abspath(layout_filename)
    )


# ============================================================
# 查找Virtuoso网表
# ============================================================

def find_input_netlist(layout_directory):

    for file_name in INPUT_FILE_CANDIDATES:

        file_path = os.path.join(
            layout_directory,
            file_name
        )

        if os.path.isfile(file_path):
            return file_path

    raise RuntimeError(
        "在当前GDS目录中没有找到Virtuoso网表。\n\n"
        "请将Virtuoso导出的文件命名为netlist，"
        "并放在GDS文件所在目录。"
    )


# ============================================================
# 合并SPICE续行
# ============================================================

def join_continuation_lines(text):

    source_lines = text.splitlines()
    result_lines = []

    for line in source_lines:

        stripped = line.lstrip()

        if stripped.startswith("+") and result_lines:

            continuation = stripped[1:].strip()

            result_lines[-1] = (
                result_lines[-1].rstrip()
                + " "
                + continuation
            )

        else:
            result_lines.append(line)

    return result_lines


# ============================================================
# 自动识别顶层Cell
# ============================================================

def detect_top_cell(lines):

    # 优先读取Virtuoso头部
    header_pattern = re.compile(
        r"^\s*\*\s*Top\s+Cell\s+Name\s*:\s*(\S+)",
        re.IGNORECASE
    )

    for line in lines:

        match = header_pattern.match(line)

        if match:
            return match.group(1)

    # 如果没有头部，则采用最后出现的SUBCKT
    subckt_pattern = re.compile(
        r"^\s*\.subckt\s+(\S+)",
        re.IGNORECASE
    )

    subckt_names = []

    for line in lines:

        match = subckt_pattern.match(line)

        if match:
            subckt_names.append(match.group(1))

    if not subckt_names:
        raise RuntimeError(
            "网表中没有找到任何.SUBCKT定义。"
        )

    return subckt_names[-1]


# ============================================================
# 提取全部SUBCKT
# ============================================================

def extract_all_subckts(lines):

    subckt_pattern = re.compile(
        r"^\s*\.subckt\s+(\S+)",
        re.IGNORECASE
    )

    ends_pattern = re.compile(
        r"^\s*\.ends(?:\s+\S+)?",
        re.IGNORECASE
    )

    output_lines = []
    inside_subckt = False
    current_subckt = None
    subckt_count = 0

    for line in lines:

        subckt_match = subckt_pattern.match(line)

        if subckt_match:

            inside_subckt = True
            current_subckt = subckt_match.group(1)
            subckt_count += 1

            output_lines.append(line)
            continue

        if inside_subckt:

            if ends_pattern.match(line):

                output_lines.append(
                    ".ENDS {}".format(current_subckt)
                )

                output_lines.append("")

                inside_subckt = False
                current_subckt = None

            else:
                output_lines.append(line)

    if inside_subckt and current_subckt:

        output_lines.append(
            ".ENDS {}".format(current_subckt)
        )

    if subckt_count == 0:

        raise RuntimeError(
            "没有提取到任何SUBCKT电路。"
        )

    return output_lines, subckt_count


# ============================================================
# SPICE数值转换
# ============================================================

def spice_value_to_float(value_text):

    value_text = value_text.strip()

    match = re.match(
        r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)"
        r"(?:[eE][+-]?\d+)?)"
        r"([A-Za-z]+)?$",
        value_text
    )

    if not match:

        raise ValueError(
            "无法识别SPICE数值：{}".format(value_text)
        )

    number = float(match.group(1))
    suffix = (match.group(2) or "").upper()

    multipliers = {
        "":    1.0,
        "T":   1e12,
        "G":   1e9,
        "MEG": 1e6,
        "K":   1e3,
        "M":   1e-3,
        "U":   1e-6,
        "N":   1e-9,
        "P":   1e-12,
        "F":   1e-15
    }

    if suffix not in multipliers:

        raise ValueError(
            "不支持的SPICE单位：{}".format(suffix)
        )

    return number * multipliers[suffix]


# ============================================================
# 清理Cadence CDL语法
# ============================================================

def normalize_cadence_syntax(line):

    # $[CNPDK_RPPOLY] → CNPDK_RPPOLY
    line = re.sub(
        r"\$\[([^\]]+)\]",
        r"\1",
        line
    )

    # $W=1u → W=1u
    # $L=10u → L=10u
    line = re.sub(
        r"(?<!\w)\$([A-Za-z_][A-Za-z0-9_]*)\s*=",
        r"\1=",
        line
    )

    return line


# ============================================================
# 从器件行读取参数
# ============================================================

def find_parameter(tokens, parameter_name):

    pattern = re.compile(
        r"^" + re.escape(parameter_name) + r"=(.+)$",
        re.IGNORECASE
    )

    for token in tokens:

        match = pattern.match(token)

        if match:
            return match.group(1)

    return None


# ============================================================
# 自动为电阻插入阻值
# ============================================================

def normalize_resistor_line(line):

    stripped = line.strip()

    # 忽略注释和非电阻行
    if not stripped or stripped.startswith("*"):
        return line

    if not re.match(r"^[Rr]\S+\s+", stripped):
        return line

    tokens = stripped.split()

    # 至少需要：名称、节点1、节点2、模型
    if len(tokens) < 4:
        return line

    model_index = None
    model_name = None

    for index, token in enumerate(tokens[3:], start=3):

        upper_token = token.upper()

        if upper_token in RESISTOR_SHEET_RESISTANCE:
            model_index = index
            model_name = upper_token
            break

    if model_index is None:
        return line

    width_text = find_parameter(tokens, "W")
    length_text = find_parameter(tokens, "L")

    if width_text is None or length_text is None:
        return line

    width = spice_value_to_float(width_text)
    length = spice_value_to_float(length_text)

    if width <= 0:
        raise RuntimeError(
            "电阻宽度W必须大于0：\n{}".format(line)
        )

    sheet_resistance = (
        RESISTOR_SHEET_RESISTANCE[model_name]
    )

    resistance = sheet_resistance * length / width

    # 检查模型名前面是否已经存在阻值
    token_before_model = (
        tokens[model_index - 1]
        if model_index > 3
        else None
    )

    already_has_value = False

    if token_before_model is not None:

        try:
            spice_value_to_float(token_before_model)
            already_has_value = True
        except ValueError:
            already_has_value = False

    if not already_has_value:

        resistance_text = "{:.12g}".format(resistance)

        tokens.insert(
            model_index,
            resistance_text
        )

    return " ".join(tokens)


# ============================================================
# 转换全部器件行
# ============================================================

def normalize_netlist_lines(lines):

    normalized_lines = []

    for line in lines:

        line = normalize_cadence_syntax(line)
        line = normalize_resistor_line(line)

        normalized_lines.append(line)

    return normalized_lines


# ============================================================
# 统计器件
# ============================================================

def count_devices(lines):

    mos_count = 0
    resistor_count = 0
    capacitor_count = 0

    for line in lines:

        stripped = line.strip()

        if not stripped or stripped.startswith("*"):
            continue

        if re.match(r"^[Mm]\S+\s+", stripped):
            mos_count += 1

        elif re.match(r"^[Rr]\S+\s+", stripped):
            resistor_count += 1

        elif re.match(r"^[Cc]\S+\s+", stripped):
            capacitor_count += 1

    return mos_count, resistor_count, capacitor_count


# ============================================================
# 主程序
# ============================================================

def main():

    try:

        layout_directory = get_layout_directory()

        input_file_path = find_input_netlist(
            layout_directory
        )

        with open(
            input_file_path,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as input_file:

            netlist_text = input_file.read()

        logical_lines = join_continuation_lines(
            netlist_text
        )

        top_cell_name = detect_top_cell(
            logical_lines
        )

        subckt_lines, subckt_count = extract_all_subckts(
            logical_lines
        )

        normalized_lines = normalize_netlist_lines(
            subckt_lines
        )

        mos_count, resistor_count, capacitor_count = (
            count_devices(normalized_lines)
        )

        output_file_name = (
            top_cell_name + "_reference.cir"
        )

        output_file_path = os.path.join(
            layout_directory,
            output_file_name
        )

        output_lines = [
            "* ========================================================",
            "* CNPDK KLayout LVS Reference Netlist",
            "* Automatically converted from Virtuoso CDL",
            "* Top Cell: {}".format(top_cell_name),
            "* Source: {}".format(
                os.path.basename(input_file_path)
            ),
            "* ========================================================",
            ""
        ]

        output_lines.extend(normalized_lines)

        with open(
            output_file_path,
            "w",
            encoding="utf-8",
            newline="\n"
        ) as output_file:

            output_file.write(
                "\n".join(output_lines)
            )

        show_info(
            "转换完成。\n\n"
            "顶层Cell：{}\n"
            "SUBCKT数量：{}\n"
            "MOS数量：{}\n"
            "电阻数量：{}\n"
            "电容数量：{}\n\n"
            "输出文件：\n{}".format(
                top_cell_name,
                subckt_count,
                mos_count,
                resistor_count,
                capacitor_count,
                output_file_path
            )
        )

    except Exception as error:
        show_error(str(error))


main()