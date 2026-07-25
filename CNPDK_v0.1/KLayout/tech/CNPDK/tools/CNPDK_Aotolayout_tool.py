# -*- coding: utf-8 -*-
"""
CNPDK Netlist-Driven AutoLayout Generator v1.0
================================================

用途
----
在KLayout当前已经保存的空白Layout/Cell中，读取同目录下由
v_netlist_k_cir.py生成的“*_reference.cir”，调用CNPDK PCell完成
基础器件放置，并使用M2横向、M3纵向的曼哈顿方式完成网络连接。
v1.0在紧凑放置、局部最短逃逸和MIM避让基础上，把宽电源轨
正式纳入M3轨道障碍物，作为CNPDK自动布局布线工具的最终版本。

第一版支持
----------
* CNPDK_NMOS
* CNPDK_PMOS
* CNPDK_RPPOLY
* CNPDK_MIMCAP
* 单个平坦.SUBCKT
* 每个MOS独立Guardring
* VDD左侧M3、VSS右侧M3、IN上侧M3、OUT下侧M3
* 电阻自动选择0/90度方向，电阻/电容紧凑放在MOS右下侧
* MOS/Guardring、电阻、MIM硬Keep-Out
* MIM PLUS/MINUS局部专用逃逸，不再建立远端双M3主干

重要限制
--------
* 本程序是第一版启发式布局器，不是通用模拟版图综合工具。
* 本程序不会自动运行DRC或LVS。
* 它使用与当前CNPDK DRC一致的合法基础尺寸，但复杂或拥塞电路
  仍应由使用者在生成后检查，并在最终交付前手动运行DRC/LVS。
* 不支持层次化子电路实例、未知器件模型和受控源。
* 为防止破坏已有工作，当前Cell非空时程序会停止。

安装
----
建议通过KLayout的Macro Development把本文件导入为Python
“General Layout macro (*.lym)”，设置“Show in menu”，不要设置
“Run on start-up”。
"""

import math
import os
import re
from collections import defaultdict

import pya


# ======================================================================
# 1. CNPDK接口与规则数据库（单位均为um，图形坐标运行时转换为DBU）
# ======================================================================

LIBRARY_NAME = "CNPDK"

PCELL_NMOS = "NMOS"
PCELL_PMOS = "PMOS"
PCELL_RESISTOR = "电阻P_PO_SAB"
PCELL_MIM = "电容MIM"
PCELL_GUARDRING = "GuardRing"

MODEL_NMOS = "CNPDK_NMOS"
MODEL_PMOS = "CNPDK_PMOS"
MODEL_RESISTOR = "CNPDK_RPPOLY"
MODEL_MIM = "CNPDK_MIMCAP"

SUPPORTED_MODELS = {
    MODEL_NMOS,
    MODEL_PMOS,
    MODEL_RESISTOR,
    MODEL_MIM,
}

# GDS Layer/Datatype
L_POLY_LABEL = pya.LayerInfo(30, 10)
L_METAL1 = pya.LayerInfo(34, 0)
L_METAL1_LABEL = pya.LayerInfo(34, 10)
L_VIA1 = pya.LayerInfo(35, 0)
L_METAL2 = pya.LayerInfo(36, 0)
L_METAL2_LABEL = pya.LayerInfo(36, 10)
L_VIA2 = pya.LayerInfo(38, 0)
L_METAL3 = pya.LayerInfo(42, 0)
L_METAL3_LABEL = pya.LayerInfo(42, 10)

# 用户确认的布局约束
DEVICE_MIN_SPACE = 0.50
GUARDRING_CLEARANCE = 0.50
SIGNAL_WIDTH = 0.38
POWER_RAIL_WIDTH = 1.00
OUTER_MARGIN = 1.00

# 器件硬Keep-Out。除本器件自身端口逃逸外，其他网络不得进入。
MOS_KEEP_OUT = 0.50
RES_KEEP_OUT = 0.50
# DRC 15.5要求MIM底板边缘到无关M2边缘至少1.20um。
# 普通0.38um M2按中心线布线，因此取1.40um中心线Keep-Out。
MIM_KEEP_OUT = 1.40

# 当前整合DRC中的互连规则
M1_MIN_SPACE = 0.23
M2_MIN_SPACE = 0.28
M3_MIN_SPACE = 0.28
VIA_SIZE = 0.26
VIA_SPACE = 0.26
VIA_ENCLOSURE = 0.06

# 1.0um电源轨与0.38um信号M3的中心距离至少为：
# 0.50 + 0.28 + 0.19 = 0.97um。
M3_POWER_SIGNAL_CENTER_SPACE = (
    0.5 * POWER_RAIL_WIDTH
    + M3_MIN_SPACE
    + 0.5 * SIGNAL_WIDTH
)

# 0.38 + 0.28 = 0.66um，取0.70um形成规则且整齐的轨道
ROUTING_PITCH = 0.70
ROUTING_CHANNEL_MARGIN = 0.70

# MOS区与无源器件区之间预留一条Keep-Out之外的布线走廊。
PASSIVE_REGION_GAP = 2.80

# 电阻、电容教学默认参数
DEFAULT_SHEET_RESISTANCE = 311.0
DEFAULT_CAP_DENSITY = 0.002  # pF/um^2
MIM_MIN_SIDE = 5.0
MIM_MAX_SIDE = 100.0


# ======================================================================
# 2. UI消息
# ======================================================================

def show_info(message):
    pya.MessageBox.info(
        "CNPDK自动布局 v1.0",
        message,
        pya.MessageBox.Ok
    )


def show_error(message):
    pya.MessageBox.critical(
        "CNPDK自动布局错误",
        message,
        pya.MessageBox.Ok
    )


# ======================================================================
# 3. 通用数值、坐标和图形函数
# ======================================================================

def spice_value_to_float(value_text):
    """把SPICE数值转换为SI浮点数。"""
    text = value_text.strip().strip("{}")
    match = re.match(
        r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
        r"([A-Za-z]+)?$",
        text
    )
    if not match:
        raise ValueError("无法识别SPICE数值：{}".format(value_text))

    number = float(match.group(1))
    suffix = (match.group(2) or "").upper()
    multipliers = {
        "": 1.0,
        "T": 1e12,
        "G": 1e9,
        "MEG": 1e6,
        "K": 1e3,
        "M": 1e-3,
        "U": 1e-6,
        "N": 1e-9,
        "P": 1e-12,
        "F": 1e-15,
    }
    if suffix not in multipliers:
        raise ValueError("不支持的SPICE单位：{}".format(suffix))
    return number * multipliers[suffix]


def parameter_value(tokens, name, default=None):
    pattern = re.compile(
        r"^" + re.escape(name) + r"=(.+)$",
        re.IGNORECASE
    )
    for token in tokens:
        # Virtuoso auCdl可能把参数写成$W=、$L=。
        match = pattern.match(token.lstrip("$"))
        if match:
            return match.group(1)
    return default


def um_parameter(tokens, name, default_um):
    value = parameter_value(tokens, name)
    if value is None:
        return float(default_um)
    return spice_value_to_float(value) * 1.0e6


def snap_um(value_um):
    return round(float(value_um) / ROUTING_PITCH) * ROUTING_PITCH


class Geometry(object):
    """在当前Layout中创建符合基础互连规则的矩形与通孔。"""

    def __init__(self, layout, top_cell):
        self.layout = layout
        self.top_cell = top_cell
        self.dbu = layout.dbu

        self.m1 = layout.layer(L_METAL1)
        self.via1 = layout.layer(L_VIA1)
        self.m2 = layout.layer(L_METAL2)
        self.m2_label = layout.layer(L_METAL2_LABEL)
        self.via2 = layout.layer(L_VIA2)
        self.m3 = layout.layer(L_METAL3)
        self.m3_label = layout.layer(L_METAL3_LABEL)

    def u(self, value_um):
        return int(round(float(value_um) / self.dbu))

    def um(self, value_dbu):
        return float(value_dbu) * self.dbu

    def point(self, x_um, y_um):
        return pya.Point(self.u(x_um), self.u(y_um))

    def box(self, x1_um, y1_um, x2_um, y2_um):
        x1, x2 = sorted((self.u(x1_um), self.u(x2_um)))
        y1, y2 = sorted((self.u(y1_um), self.u(y2_um)))
        return pya.Box(x1, y1, x2, y2)

    def insert_box(self, layer_index, x1, y1, x2, y2):
        box = self.box(x1, y1, x2, y2)
        self.top_cell.shapes(layer_index).insert(box)
        return box

    def pad(self, layer_index, x, y, size=SIGNAL_WIDTH):
        half = 0.5 * size
        return self.insert_box(
            layer_index,
            x - half, y - half,
            x + half, y + half
        )

    def horizontal(self, layer_index, y, x1, x2, width=SIGNAL_WIDTH):
        half = 0.5 * width
        if abs(x2 - x1) < 1.0e-12:
            return self.pad(layer_index, x1, y, width)
        return self.insert_box(
            layer_index,
            min(x1, x2) - half, y - half,
            max(x1, x2) + half, y + half
        )

    def vertical(self, layer_index, x, y1, y2, width=SIGNAL_WIDTH):
        half = 0.5 * width
        if abs(y2 - y1) < 1.0e-12:
            return self.pad(layer_index, x, y1, width)
        return self.insert_box(
            layer_index,
            x - half, min(y1, y2) - half,
            x + half, max(y1, y2) + half
        )

    def add_via1(self, x, y):
        """M1-Via1-M2，0.26um cut和0.06um包围。"""
        landing = VIA_SIZE + 2.0 * VIA_ENCLOSURE
        self.pad(self.m1, x, y, landing)
        self.pad(self.via1, x, y, VIA_SIZE)
        self.pad(self.m2, x, y, landing)

    def add_via2(self, x, y):
        """M2-Via2-M3，0.26um cut和0.06um包围。"""
        landing = VIA_SIZE + 2.0 * VIA_ENCLOSURE
        self.pad(self.m2, x, y, landing)
        self.pad(self.via2, x, y, VIA_SIZE)
        self.pad(self.m3, x, y, landing)

    def add_m2_label(self, text, x, y):
        label = pya.Text(
            str(text),
            pya.Trans(self.u(x), self.u(y))
        )
        self.top_cell.shapes(self.m2_label).insert(label)

    def add_m3_label(self, text, x, y):
        label = pya.Text(
            str(text),
            pya.Trans(self.u(x), self.u(y))
        )
        self.top_cell.shapes(self.m3_label).insert(label)


# ======================================================================
# 4. 参考网表搜索与解析
# ======================================================================

def join_continuation_lines(text):
    result = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("+") and result:
            result[-1] = result[-1].rstrip() + " " + stripped[1:].strip()
        else:
            result.append(line)
    return result


def find_reference_netlist(layout_filename):
    directory = os.path.dirname(os.path.abspath(layout_filename))
    gds_base = os.path.splitext(os.path.basename(layout_filename))[0]

    candidates = []
    for name in os.listdir(directory):
        if name.lower().endswith("_reference.cir"):
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                candidates.append(path)

    if not candidates:
        raise RuntimeError(
            "当前GDS目录中没有找到“*_reference.cir”。\n\n"
            "请先把Virtuoso网表放到GDS目录，运行转换宏，再运行自动布局。"
        )

    # 优先选择和GDS同名的参考网表，否则选择最新文件
    exact_names = {
        (gds_base + "_reference.cir").lower(),
        (gds_base + ".cir").lower(),
    }
    exact = [
        path for path in candidates
        if os.path.basename(path).lower() in exact_names
    ]
    if exact:
        return max(exact, key=os.path.getmtime)
    return max(candidates, key=os.path.getmtime)


def read_subckts(lines):
    subckts = []
    current = None

    for raw_line in lines:
        line = raw_line.strip()
        start = re.match(
            r"^\.subckt\s+(\S+)(.*)$",
            line,
            re.IGNORECASE
        )
        if start:
            current = {
                "name": start.group(1),
                "pins": start.group(2).split(),
                "lines": [],
            }
            subckts.append(current)
            continue

        if re.match(r"^\.ends(?:\s+\S+)?", line, re.IGNORECASE):
            current = None
            continue

        if current is not None:
            current["lines"].append(raw_line)

    if not subckts:
        raise RuntimeError("参考网表中没有找到.SUBCKT。")
    return subckts


def detect_top_name(lines, subckts):
    header = re.compile(
        r"^\s*\*\s*Top\s+Cell\s*:\s*(\S+)",
        re.IGNORECASE
    )
    for line in lines:
        match = header.match(line)
        if match:
            return match.group(1)
    return subckts[-1]["name"]


def locate_model(tokens):
    for token in tokens:
        cleaned = token.strip().replace("$", "").strip("[]").upper()
        if cleaned in SUPPORTED_MODELS:
            return cleaned
    return None


def parse_device_line(line):
    stripped = line.strip()
    if not stripped or stripped.startswith("*") or stripped.startswith("."):
        return None

    tokens = stripped.split()
    name = tokens[0]
    prefix = name[0].upper()
    model = locate_model(tokens)

    if prefix in ("M", "R", "C") and model is None:
        raise RuntimeError(
            "遇到不支持或无法识别的器件模型：\n{}".format(line)
        )

    if prefix == "M":
        if len(tokens) < 6:
            raise RuntimeError("MOS器件行格式不完整：\n{}".format(line))
        return {
            "name": name,
            "kind": "NMOS" if model == MODEL_NMOS else "PMOS",
            "model": model,
            "nets": {
                "D": tokens[1],
                "G": tokens[2],
                "S": tokens[3],
                "B": tokens[4],
            },
            "w": um_parameter(tokens, "W", 1.0),
            "l": um_parameter(tokens, "L", 0.28),
            "nf": max(1, int(float(parameter_value(tokens, "NF", "1")))),
        }

    if prefix == "R":
        if len(tokens) < 4:
            raise RuntimeError("电阻器件行格式不完整：\n{}".format(line))
        return {
            "name": name,
            "kind": "RES",
            "model": model,
            "nets": {
                "P": tokens[1],
                "N": tokens[2],
            },
            "width": um_parameter(tokens, "W", 1.0),
            "length": um_parameter(tokens, "L", 10.0),
        }

    if prefix == "C":
        if len(tokens) < 4:
            raise RuntimeError("电容器件行格式不完整：\n{}".format(line))

        model_index = None
        for index, token in enumerate(tokens):
            cleaned = token.strip().replace("$", "").strip("[]").upper()
            if cleaned == model:
                model_index = index
                break

        capacitance_si = None
        for token in tokens[3:model_index]:
            try:
                capacitance_si = spice_value_to_float(token)
                break
            except ValueError:
                pass

        if capacitance_si is None:
            raise RuntimeError("MIM电容行中没有找到电容值：\n{}".format(line))

        capacitance_pf = capacitance_si * 1.0e12
        side = math.sqrt(max(capacitance_pf, 0.0) / DEFAULT_CAP_DENSITY)
        side = min(max(side, MIM_MIN_SIDE), MIM_MAX_SIDE)

        return {
            "name": name,
            "kind": "MIM",
            "model": model,
            "nets": {
                "PLUS": tokens[1],
                "MINUS": tokens[2],
            },
            "capacitance_pf": capacitance_pf,
            "length": side,
            "width": side,
        }

    # 第一版不允许静默忽略实际器件或子电路实例
    if prefix == "X":
        raise RuntimeError(
            "第一版暂不支持层次化子电路实例：\n{}".format(line)
        )
    return None


def parse_reference_netlist(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        lines = join_continuation_lines(handle.read())

    subckts = read_subckts(lines)
    top_name = detect_top_name(lines, subckts)
    selected = None

    for subckt in subckts:
        if subckt["name"].lower() == top_name.lower():
            selected = subckt
            break
    if selected is None:
        selected = subckts[-1]
        top_name = selected["name"]

    devices = []
    for line in selected["lines"]:
        device = parse_device_line(line)
        if device is not None:
            devices.append(device)

    if not devices:
        raise RuntimeError("顶层.SUBCKT中没有找到受支持的器件。")

    pin_directions = {}
    for raw_line in selected["lines"]:
        line = raw_line.strip()
        if not re.match(r"^\*?\.PININFO\b", line, re.IGNORECASE):
            continue
        fields = re.sub(
            r"^\*?\.PININFO\s*",
            "",
            line,
            flags=re.IGNORECASE
        ).split()
        for field in fields:
            if ":" in field:
                pin, direction = field.rsplit(":", 1)
                pin_directions[pin] = direction.upper()

    return {
        "name": top_name,
        "pins": selected["pins"],
        "pin_directions": pin_directions,
        "devices": devices,
    }


# ======================================================================
# 5. PCell创建、端口提取与放置
# ======================================================================

def library_and_pcell(layout, pcell_name, parameters):
    library = pya.Library.library_by_name(LIBRARY_NAME)
    if library is None:
        raise RuntimeError(
            "没有找到CNPDK Library。\n"
            "请确认library.py已运行或已设置Run on start-up。"
        )

    declaration = library.layout().pcell_declaration(pcell_name)
    if declaration is None:
        raise RuntimeError("CNPDK中没有找到PCell：{}".format(pcell_name))

    cell_index = layout.add_pcell_variant(
        library,
        declaration.id(),
        parameters
    )
    return layout.cell(cell_index)


def bbox_center(box):
    return pya.Point(
        (box.left + box.right) // 2,
        (box.bottom + box.top) // 2
    )


def transformed_box(box, transform):
    return box.transformed(transform)


def transformed_point(point, transform):
    return transform * point


def expanded_box(box, margin_dbu):
    return pya.Box(
        box.left - margin_dbu,
        box.bottom - margin_dbu,
        box.right + margin_dbu,
        box.top + margin_dbu
    )


def text_position(shape):
    text = shape.text
    return text.trans.disp


def shape_boxes(cell, layer_index):
    boxes = []
    for shape in cell.shapes(layer_index).each():
        if shape.is_box() or shape.is_polygon() or shape.is_path():
            boxes.append(shape.bbox())
    return boxes


def label_points(cell, layer_index):
    result = []
    for shape in cell.shapes(layer_index).each():
        if shape.is_text():
            result.append((shape.text.string, text_position(shape)))
    return result


def squared_distance_to_box(point, box):
    if point.x < box.left:
        dx = box.left - point.x
    elif point.x > box.right:
        dx = point.x - box.right
    else:
        dx = 0

    if point.y < box.bottom:
        dy = box.bottom - point.y
    elif point.y > box.top:
        dy = point.y - box.top
    else:
        dy = 0
    return dx * dx + dy * dy


def nearest_box_center(point, boxes):
    if not boxes:
        return point
    nearest = min(
        boxes,
        key=lambda box: squared_distance_to_box(point, box)
    )
    return bbox_center(nearest)


def extract_mos_local_ports(layout, cell):
    """从PCell标签定位D/G/S，并把G投影到最近的M1 landing。"""
    m1_index = layout.layer(L_METAL1)
    m1_label_index = layout.layer(L_METAL1_LABEL)
    poly_label_index = layout.layer(L_POLY_LABEL)

    metal_boxes = shape_boxes(cell, m1_index)
    labels = (
        label_points(cell, m1_label_index)
        + label_points(cell, poly_label_index)
    )

    ports = defaultdict(list)
    for name, point in labels:
        upper = name.upper()
        if upper.startswith("D"):
            terminal = "D"
        elif upper.startswith("S"):
            terminal = "S"
        elif upper.startswith("G"):
            terminal = "G"
        else:
            continue
        ports[terminal].append(nearest_box_center(point, metal_boxes))

    for terminal in ("D", "G", "S"):
        if not ports[terminal]:
            raise RuntimeError(
                "{}缺少可识别的{}端口。"
                "自动布局实例化MOS时必须启用add_labels。".format(
                    cell.name, terminal
                )
            )
    return ports


def extract_resistor_local_ports(layout, cell):
    m1_index = layout.layer(L_METAL1)
    boxes = sorted(shape_boxes(cell, m1_index), key=lambda box: box.left)
    if len(boxes) < 2:
        raise RuntimeError("{}没有找到两个M1电阻端口。".format(cell.name))
    return {
        "P": [bbox_center(boxes[0])],
        "N": [bbox_center(boxes[-1])],
    }


def extract_mim_local_ports(layout, cell):
    m2_index = layout.layer(L_METAL2)
    m3_index = layout.layer(L_METAL3)
    m2_boxes = shape_boxes(cell, m2_index)
    m3_boxes = shape_boxes(cell, m3_index)
    if not m2_boxes or not m3_boxes:
        raise RuntimeError("{}缺少M2或M3电容端口。".format(cell.name))

    bottom = max(m2_boxes, key=lambda box: box.area())
    top = max(m3_boxes, key=lambda box: box.area())

    # MINUS从M2底板右侧引出；PLUS从已有M3 landing上边缘引出。
    # PLUS不得在CapMk内部新增普通Via2。
    minus = pya.Point(bottom.right, (bottom.bottom + bottom.top) // 2)
    plus = pya.Point((top.left + top.right) // 2, top.top)
    return {
        "PLUS": [plus],
        "MINUS": [minus],
    }


def create_device_cells(layout, circuit):
    records = []
    for device in circuit["devices"]:
        kind = device["kind"]

        if kind == "NMOS":
            cell = library_and_pcell(
                layout,
                PCELL_NMOS,
                {
                    "w": device["w"],
                    "l": device["l"],
                    "nf": device["nf"],
                    "gate_contact_position": 1,  # Top
                    "add_labels": True,
                }
            )
            ports = extract_mos_local_ports(layout, cell)

        elif kind == "PMOS":
            cell = library_and_pcell(
                layout,
                PCELL_PMOS,
                {
                    "w": device["w"],
                    "l": device["l"],
                    "nf": device["nf"],
                    "gate_contact_position": 2,  # Bottom
                    "add_labels": True,
                }
            )
            ports = extract_mos_local_ports(layout, cell)

        elif kind == "RES":
            cell = library_and_pcell(
                layout,
                PCELL_RESISTOR,
                {
                    "length": device["length"],
                    "width": device["width"],
                    "sheet_resistance": DEFAULT_SHEET_RESISTANCE,
                }
            )
            ports = extract_resistor_local_ports(layout, cell)

        elif kind == "MIM":
            cell = library_and_pcell(
                layout,
                PCELL_MIM,
                {
                    "length": device["length"],
                    "width": device["width"],
                    "cap_density": DEFAULT_CAP_DENSITY,
                }
            )
            ports = extract_mim_local_ports(layout, cell)

        else:
            raise RuntimeError("不支持的器件类型：{}".format(kind))

        records.append({
            "device": device,
            "cell": cell,
            "local_ports": ports,
            "transform": None,
            "world_ports": defaultdict(list),
            "bbox": None,
            "keepout": None,
            "guard": None,
        })
    return records


def place_instance(top_cell, cell, transform):
    instance = pya.CellInstArray(cell.cell_index(), transform)
    top_cell.insert(instance)
    return instance


def make_guard(layout, mos_cell, ring_type):
    box = mos_cell.bbox()
    dbu = layout.dbu
    inner_width = box.width() * dbu + 2.0 * GUARDRING_CLEARANCE
    inner_height = box.height() * dbu + 2.0 * GUARDRING_CLEARANCE

    guard_cell = library_and_pcell(
        layout,
        PCELL_GUARDRING,
        {
            "ring_type": ring_type,
            "inner_width": inner_width,
            "inner_height": inner_height,
        }
    )
    return guard_cell, inner_width, inner_height


def row_dimensions(items):
    if not items:
        return 0, 0
    total_width = sum(item["guard_cell"].bbox().width() for item in items)
    total_width += max(0, len(items) - 1) * items[0]["space_dbu"]
    max_height = max(item["guard_cell"].bbox().height() for item in items)
    return total_width, max_height


def place_mos_rows(layout, top_cell, records, channel_height_um):
    dbu = layout.dbu
    space_dbu = int(round(DEVICE_MIN_SPACE / dbu))

    p_items = []
    n_items = []

    for record in records:
        kind = record["device"]["kind"]
        if kind not in ("PMOS", "NMOS"):
            continue

        ring_type = 0 if kind == "PMOS" else 1
        guard_cell, inner_w, inner_h = make_guard(
            layout, record["cell"], ring_type
        )
        item = {
            "record": record,
            "guard_cell": guard_cell,
            "inner_width": inner_w,
            "inner_height": inner_h,
            "space_dbu": space_dbu,
        }
        if kind == "PMOS":
            p_items.append(item)
        else:
            n_items.append(item)

    p_width, p_height = row_dimensions(p_items)
    n_width, n_height = row_dimensions(n_items)
    group_width = max(p_width, n_width, int(round(2.0 / dbu)))

    channel_dbu = int(round(channel_height_um / dbu))
    n_center_y = -(channel_dbu + n_height) // 2
    p_center_y = +(channel_dbu + p_height) // 2

    for items, row_width, center_y, kind in (
        (p_items, p_width, p_center_y, "PMOS"),
        (n_items, n_width, n_center_y, "NMOS"),
    ):
        cursor_x = -row_width // 2

        for item in items:
            record = item["record"]
            guard_cell = item["guard_cell"]
            guard_bbox = guard_cell.bbox()

            guard_center_x = (
                cursor_x
                - guard_bbox.left
                + guard_bbox.width() // 2
            )
            guard_center_y = center_y
            guard_trans = pya.Trans(guard_center_x, guard_center_y)
            place_instance(top_cell, guard_cell, guard_trans)

            device_box = record["cell"].bbox()
            device_center = bbox_center(device_box)
            device_trans = pya.Trans(
                guard_center_x - device_center.x,
                guard_center_y - device_center.y
            )
            place_instance(top_cell, record["cell"], device_trans)

            record["transform"] = device_trans
            record["bbox"] = transformed_box(device_box, device_trans)
            world_guard_box = transformed_box(guard_bbox, guard_trans)
            record["keepout"] = expanded_box(
                world_guard_box,
                int(round(MOS_KEEP_OUT / dbu))
            )

            for terminal, local_points in record["local_ports"].items():
                for point in local_points:
                    record["world_ports"][terminal].append(
                        transformed_point(point, device_trans)
                    )

            # PMOS Guardring朝左侧VDD轨引出，NMOS朝右侧VSS轨引出。
            ring_centerline_offset = (
                0.5 * item["inner_width"] + 0.5 * 0.52
            )
            if kind == "PMOS":
                body_local = pya.Point(
                    -int(round(ring_centerline_offset / dbu)),
                    0
                )
            else:
                body_local = pya.Point(
                    int(round(ring_centerline_offset / dbu)),
                    0
                )

            record["guard"] = {
                "cell": guard_cell,
                "transform": guard_trans,
                "port": transformed_point(body_local, guard_trans),
                "net": record["device"]["nets"]["B"],
            }

            cursor_x += guard_bbox.width() + space_dbu

    return group_width


def place_passives(layout, top_cell, records, channel_height_um):
    passive = [
        record for record in records
        if record["device"]["kind"] in ("RES", "MIM")
    ]
    if not passive:
        return

    current = top_cell.bbox()
    # 相邻无源器件之间同时容纳两侧Keep-Out和一条逃逸走廊。
    passive_space_um = (
        DEVICE_MIN_SPACE + RES_KEEP_OUT + MIM_KEEP_OUT
    )
    space = int(round(passive_space_um / layout.dbu))

    # 无源器件置于MOS右下侧并横向排布。它们低于中央信号通道，
    # 但可与NMOS在Y方向部分并排，从而减少纯衬底空白并改善宽高比。
    # 长条电阻自动选择较窄的竖直方向；MIM保持PCell原始方向。
    oriented = []
    for record in passive:
        box = record["cell"].bbox()
        if (
            record["device"]["kind"] == "RES"
            and box.width() > box.height()
        ):
            rotation = pya.Trans.R90
        else:
            rotation = pya.Trans.R0
        rotated_box = box.transformed(pya.Trans(rotation, 0, 0))
        oriented.append((record, rotation, rotated_box))

    channel_bottom_um = -0.5 * channel_height_um
    y_top_um = (
        channel_bottom_um
        - MIM_KEEP_OUT
        - 0.5 * ROUTING_PITCH
    )
    y_top = int(round(y_top_um / layout.dbu))
    cursor_x = (
        current.right
        + int(round(PASSIVE_REGION_GAP / layout.dbu))
    )

    for record, rotation, rotated_box in oriented:
        trans = pya.Trans(
            rotation,
            cursor_x - rotated_box.left,
            y_top - rotated_box.top
        )
        place_instance(top_cell, record["cell"], trans)
        record["transform"] = trans
        record["bbox"] = transformed_box(record["cell"].bbox(), trans)
        margin_um = (
            MIM_KEEP_OUT
            if record["device"]["kind"] == "MIM"
            else RES_KEEP_OUT
        )
        record["keepout"] = expanded_box(
            record["bbox"],
            int(round(margin_um / layout.dbu))
        )
        cursor_x += rotated_box.width() + space

        for terminal, local_points in record["local_ports"].items():
            for point in local_points:
                record["world_ports"][terminal].append(
                    transformed_point(point, trans)
                )


# ======================================================================
# 6. 网络收集与M2/M3曼哈顿布线
# ======================================================================

def is_vdd_net(name):
    upper = name.upper()
    return (
        upper in ("VDD", "AVDD", "DVDD", "VCC", "VPWR")
        or upper.endswith("VDD")
    )


def is_vss_net(name):
    upper = name.upper()
    return (
        upper in ("VSS", "AVSS", "DVSS", "GND", "VGND", "VNB")
        or upper.endswith("VSS")
        or upper.endswith("GND")
    )


def collect_net_accesses(records):
    accesses = defaultdict(list)

    for record in records:
        device = record["device"]
        kind = device["kind"]

        if kind in ("NMOS", "PMOS"):
            for terminal in ("D", "G", "S"):
                net = device["nets"][terminal]
                for point in record["world_ports"][terminal]:
                    accesses[net].append({
                        "point": point,
                        "layer": "M1",
                        "owner": device["name"],
                        "terminal": terminal,
                        "record": record,
                        "strategy": "MOS",
                    })

            guard = record["guard"]
            accesses[guard["net"]].append({
                "point": guard["port"],
                "layer": "M1",
                "owner": device["name"] + "_GUARDRING",
                "terminal": "B",
                "record": record,
                "strategy": "GUARD",
            })

        elif kind == "RES":
            for terminal in ("P", "N"):
                net = device["nets"][terminal]
                for point in record["world_ports"][terminal]:
                    accesses[net].append({
                        "point": point,
                        "layer": "M1",
                        "owner": device["name"],
                        "terminal": terminal,
                        "record": record,
                        "strategy": "RES",
                    })

        elif kind == "MIM":
            for terminal, layer in (("PLUS", "M3"), ("MINUS", "M2")):
                net = device["nets"][terminal]
                for point in record["world_ports"][terminal]:
                    accesses[net].append({
                        "point": point,
                        "layer": layer,
                        "owner": device["name"],
                        "terminal": terminal,
                        "record": record,
                        "strategy": (
                            "MIM_PLUS"
                            if terminal == "PLUS"
                            else "MIM_MINUS"
                        ),
                    })

    return accesses


def unique_track_x(preferred_x, used_tracks, direction=1):
    candidate = snap_um(preferred_x)
    step = ROUTING_PITCH if direction >= 0 else -ROUTING_PITCH
    while any(abs(candidate - used) < ROUTING_PITCH - 1.0e-9
              for used in used_tracks):
        candidate += step
    used_tracks.append(candidate)
    return candidate


def reserve_outward_track(preferred_x, used_tracks, direction):
    """向版图外侧寻找不与已有M3轨重合的轨道。"""
    candidate = snap_um(preferred_x)
    step = ROUTING_PITCH if direction >= 0 else -ROUTING_PITCH
    while any(abs(candidate - used) < ROUTING_PITCH - 1.0e-9
              for used in used_tracks):
        candidate += step
    used_tracks.append(candidate)
    return candidate


def keepout_um(geometry, access):
    box = access["record"]["keepout"]
    return {
        "left": geometry.um(box.left),
        "right": geometry.um(box.right),
        "bottom": geometry.um(box.bottom),
        "top": geometry.um(box.top),
    }


def access_to_m3_escape(geometry, access, used_tracks):
    """在器件自己的Keep-Out内完成最短逃逸，并在区外返回M3轨道点。

    返回(track_x, start_y)。之后只能沿M3竖向走到公共M2通道。
    """
    point = access["point"]
    x = geometry.um(point.x)
    y = geometry.um(point.y)
    strategy = access["strategy"]
    bounds = keepout_um(geometry, access)

    if strategy in ("MOS", "GUARD"):
        track_x = unique_track_x(x, used_tracks)
        geometry.add_via1(x, y)
        geometry.horizontal(geometry.m2, y, x, track_x)
        geometry.add_via2(track_x, y)
        return track_x, y

    if strategy == "RES":
        track_x = access["record"]["escape_track_x_by_terminal"][
            access["terminal"]
        ]
        geometry.add_via1(x, y)
        geometry.horizontal(geometry.m2, y, x, track_x)
        geometry.add_via2(track_x, y)
        return track_x, y

    if strategy == "MIM_MINUS":
        # 底板自身的连续M2属于mim_bottom；在1.20um Keep-Out外换层。
        track_x = access["record"]["escape_track_x_by_terminal"][
            access["terminal"]
        ]
        geometry.horizontal(geometry.m2, y, x, track_x)
        geometry.add_via2(track_x, y)
        return track_x, y

    if strategy == "MIM_PLUS":
        # 上极板PCell已经包含专用Via2阵列和M3 landing。
        # 从现有M3边缘直接向上引出，严禁在CapMk内新增普通Via2。
        escape_y = snap_um(bounds["top"] + 0.5 * ROUTING_PITCH)
        geometry.vertical(geometry.m3, x, y, escape_y)
        geometry.add_via2(x, escape_y)
        track_x = access["record"]["escape_track_x_by_terminal"][
            access["terminal"]
        ]
        geometry.horizontal(geometry.m2, escape_y, x, track_x)
        geometry.add_via2(track_x, escape_y)
        return track_x, escape_y

    raise RuntimeError("未知端口逃逸策略：{}".format(strategy))


def choose_pin_sides(pins, directions):
    sides = {}
    remaining_index = 0

    for pin in pins:
        upper = pin.upper()
        direction = directions.get(pin, "")
        if is_vdd_net(pin):
            sides[pin] = "LEFT"
        elif is_vss_net(pin):
            sides[pin] = "RIGHT"
        elif upper == "IN" or direction == "I":
            sides[pin] = "TOP"
        elif upper == "OUT" or direction == "O":
            sides[pin] = "BOTTOM"
        else:
            sides[pin] = "TOP" if remaining_index % 2 == 0 else "BOTTOM"
            remaining_index += 1
    return sides


def route_access_to_power(
    geometry,
    access,
    rail_x,
    is_vdd,
    used_tracks,
    vdd_corridor_y,
    vss_corridor_y
):
    """端口先接入M3，再从全局安全走廊连接左右电源轨。"""
    track_x, start_y = access_to_m3_escape(
        geometry,
        access,
        used_tracks
    )
    escape_y = vdd_corridor_y if is_vdd else vss_corridor_y

    geometry.vertical(geometry.m3, track_x, start_y, escape_y)
    geometry.add_via2(track_x, escape_y)
    geometry.horizontal(geometry.m2, escape_y, track_x, rail_x)
    geometry.add_via2(rail_x, escape_y)


def signal_track_positions(signal_nets):
    positions = {}
    if not signal_nets:
        return positions
    start_y = -0.5 * (len(signal_nets) - 1) * ROUTING_PITCH
    for index, net in enumerate(signal_nets):
        positions[net] = start_y + index * ROUTING_PITCH
    return positions


def route_layout(layout, top_cell, circuit, records):
    geometry = Geometry(layout, top_cell)

    content_box = top_cell.bbox()
    content_left = geometry.um(content_box.left)
    content_right = geometry.um(content_box.right)
    content_bottom = geometry.um(content_box.bottom)
    content_top = geometry.um(content_box.top)

    all_keepouts = [
        record["keepout"] for record in records
        if record["keepout"] is not None
    ]
    keepout_left = min(
        [geometry.um(box.left) for box in all_keepouts] or [content_left]
    )
    keepout_right = max(
        [geometry.um(box.right) for box in all_keepouts] or [content_right]
    )
    keepout_bottom = min(
        [geometry.um(box.bottom) for box in all_keepouts] or [content_bottom]
    )
    keepout_top = max(
        [geometry.um(box.top) for box in all_keepouts] or [content_top]
    )
    vdd_corridor_y = snap_um(
        keepout_top + 0.5 * ROUTING_PITCH
    )
    vss_corridor_y = snap_um(
        keepout_bottom - 0.5 * ROUTING_PITCH
    )
    bottom_boundary = min(
        content_bottom - OUTER_MARGIN,
        vss_corridor_y - OUTER_MARGIN
    )
    top_boundary = max(
        content_top + OUTER_MARGIN,
        vdd_corridor_y + OUTER_MARGIN
    )

    # 为无源端子选择最近的左/右逃逸轨。如果端口位于MOS横向投影
    # 内，则把M3轨推到MOS Keep-Out外，避免竖线穿越MOS。
    mos_left = min(
        [
            geometry.um(record["keepout"].left)
            for record in records
            if record["device"]["kind"] in ("NMOS", "PMOS")
        ] or [content_left]
    )
    mos_right = max(
        [
            geometry.um(record["keepout"].right)
            for record in records
            if record["device"]["kind"] in ("NMOS", "PMOS")
        ] or [content_right]
    )
    reserved_passive_tracks = []
    for record in records:
        if record["device"]["kind"] not in ("RES", "MIM"):
            continue
        own_left = geometry.um(record["keepout"].left)
        own_right = geometry.um(record["keepout"].right)
        if record["device"]["kind"] == "RES":
            terminals = ("P", "N")
        else:
            terminals = ("PLUS", "MINUS")

        left_track = reserve_outward_track(
            min(own_left, mos_left) - 0.5 * ROUTING_PITCH,
            reserved_passive_tracks,
            -1
        )
        right_track = reserve_outward_track(
            max(own_right, mos_right) + 0.5 * ROUTING_PITCH,
            reserved_passive_tracks,
            +1
        )
        record["escape_track_x_by_terminal"] = {
            terminals[0]: left_track,
            terminals[1]: right_track,
        }

    # 电源轨放在最外侧信号轨之外两个routing pitch，既保持紧凑，
    # 也保证1.0um宽电源轨与0.38um信号轨满足M3间距。
    left_anchor = min([keepout_left] + reserved_passive_tracks)
    right_anchor = max([keepout_right] + reserved_passive_tracks)
    vdd_x = snap_um(left_anchor - 2.0 * ROUTING_PITCH)
    vss_x = snap_um(right_anchor + 2.0 * ROUTING_PITCH)

    geometry.vertical(
        geometry.m3,
        vdd_x,
        bottom_boundary,
        top_boundary,
        POWER_RAIL_WIDTH
    )
    geometry.vertical(
        geometry.m3,
        vss_x,
        bottom_boundary,
        top_boundary,
        POWER_RAIL_WIDTH
    )

    accesses = collect_net_accesses(records)

    pin_sides = choose_pin_sides(
        circuit["pins"],
        circuit.get("pin_directions", {})
    )
    pin_set = set(circuit["pins"])

    # 非电源网络采用位于MOS两行之间的独立M2横向轨道
    signal_nets = [
        net for net in accesses.keys()
        if not is_vdd_net(net) and not is_vss_net(net)
    ]
    for pin in circuit["pins"]:
        if (
            not is_vdd_net(pin)
            and not is_vss_net(pin)
            and pin not in signal_nets
        ):
            signal_nets.append(pin)

    signal_nets.sort(
        key=lambda net: (
            0 if net.upper() == "IN" else
            1 if net.upper() == "OUT" else
            2,
            net.upper()
        )
    )

    track_y_by_net = signal_track_positions(signal_nets)

    used_vertical_tracks = list(reserved_passive_tracks)

    # 普通信号轨之间用0.70um中心距即可，但1.0um宽电源轨需要
    # 0.97um中心距。加入三个虚拟障碍点，使相邻0.70um轨被拒绝，
    # 下一条可用轨自然落在1.40um处。
    rail_guard_offset = (
        M3_POWER_SIGNAL_CENTER_SPACE - ROUTING_PITCH + 0.01
    )
    for rail_x in (vdd_x, vss_x):
        used_vertical_tracks.extend([
            rail_x - rail_guard_offset,
            rail_x,
            rail_x + rail_guard_offset,
        ])
    top_pin_count = 0
    bottom_pin_count = 0

    # 电源网络：先逃离器件Keep-Out，再以M2横线连接左右M3轨。
    for net, net_accesses in accesses.items():
        if not (is_vdd_net(net) or is_vss_net(net)):
            continue

        rail_x = vdd_x if is_vdd_net(net) else vss_x
        for access in net_accesses:
            route_access_to_power(
                geometry,
                access,
                rail_x,
                is_vdd_net(net),
                used_vertical_tracks,
                vdd_corridor_y,
                vss_corridor_y
            )

    # 普通信号网络：每个网络一条M2横线，每个端口一条M3竖线
    for net in signal_nets:
        track_y = track_y_by_net[net]
        net_tracks = []

        for access in accesses.get(net, []):
            track_x, point_y = access_to_m3_escape(
                geometry,
                access,
                used_vertical_tracks
            )
            geometry.vertical(geometry.m3, track_x, point_y, track_y)
            geometry.add_via2(track_x, track_y)
            net_tracks.append(track_x)

        # 普通顶层端口在上/下边界使用M3；与中央M2轨通过Via2连接。
        pin_x = None
        side = None
        if net in pin_set:
            side = pin_sides.get(net, "TOP")
            exterior_offset = 2.0 * ROUTING_PITCH
            if side == "TOP":
                preferred = (
                    vdd_x + exterior_offset
                    + top_pin_count * ROUTING_PITCH
                )
                top_pin_count += 1
            else:
                preferred = (
                    vss_x - exterior_offset
                    - bottom_pin_count * ROUTING_PITCH
                )
                bottom_pin_count += 1
            pin_x = unique_track_x(
                preferred,
                used_vertical_tracks,
                +1 if side == "TOP" else -1
            )
            net_tracks.append(pin_x)

        if not net_tracks:
            continue

        geometry.horizontal(
            geometry.m2,
            track_y,
            min(net_tracks),
            max(net_tracks),
            SIGNAL_WIDTH
        )

        if net in pin_set:
            pin_y = top_boundary if side == "TOP" else bottom_boundary
            geometry.add_via2(pin_x, track_y)
            geometry.vertical(geometry.m3, pin_x, track_y, pin_y)
            geometry.pad(geometry.m3, pin_x, pin_y, SIGNAL_WIDTH)
            geometry.add_m3_label(net, pin_x, pin_y)

    # 电源端口标签
    for pin in circuit["pins"]:
        if is_vdd_net(pin):
            geometry.add_m3_label(pin, vdd_x, top_boundary)
        elif is_vss_net(pin):
            geometry.add_m3_label(pin, vss_x, top_boundary)

    return {
        "left": vdd_x - 0.5 * POWER_RAIL_WIDTH - OUTER_MARGIN,
        "right": vss_x + 0.5 * POWER_RAIL_WIDTH + OUTER_MARGIN,
        "top": top_boundary + OUTER_MARGIN,
        "bottom": bottom_boundary - OUTER_MARGIN,
        "signal_nets": len(signal_nets),
    }


# ======================================================================
# 7. 主程序
# ======================================================================

def current_layout_context():
    main_window = pya.Application.instance().main_window()
    view = main_window.current_view()
    if view is None:
        raise RuntimeError("当前没有打开Layout。")

    cell_view = view.active_cellview()
    if cell_view is None or not cell_view.is_valid():
        raise RuntimeError("当前没有有效的CellView。")

    filename = cell_view.filename()
    if not filename:
        raise RuntimeError(
            "当前Layout尚未保存。\n"
            "请先保存为GDS，再运行网表转换宏和自动布局宏。"
        )

    layout = cell_view.layout()
    cell = cell_view.cell
    if layout is None or cell is None:
        raise RuntimeError("无法取得当前Layout或Cell。")

    # 只允许在完全空白Cell中运行
    if not cell.is_empty():
        raise RuntimeError(
            "当前Cell不是空白Cell。\n\n"
            "为了避免覆盖已有版图，自动布局已经停止。\n"
            "请新建并保存一个空白Layout后重新运行。"
        )

    return main_window, view, cell_view, layout, cell, filename


def main():
    try:
        (
            main_window,
            view,
            cell_view,
            layout,
            top_cell,
            layout_filename,
        ) = current_layout_context()

        reference_path = find_reference_netlist(layout_filename)
        circuit = parse_reference_netlist(reference_path)

        # 先根据非电源网络数量预留中央M2信号轨道
        all_nets = set()
        for device in circuit["devices"]:
            all_nets.update(device["nets"].values())
        signal_net_count = len([
            net for net in all_nets
            if not is_vdd_net(net) and not is_vss_net(net)
        ])
        channel_height = max(
            2.0,
            signal_net_count * ROUTING_PITCH
            + 2.0 * ROUTING_CHANNEL_MARGIN
        )

        records = create_device_cells(layout, circuit)
        place_mos_rows(
            layout,
            top_cell,
            records,
            channel_height
        )
        place_passives(
            layout,
            top_cell,
            records,
            channel_height
        )
        route_result = route_layout(
            layout,
            top_cell,
            circuit,
            records
        )

        view.add_missing_layers()
        view.zoom_fit()

        counts = defaultdict(int)
        for record in records:
            counts[record["device"]["kind"]] += 1

        show_info(
            "CNPDK自动布局布线最终版生成完成。\n\n"
            "参考网表：{}\n"
            "顶层电路：{}\n"
            "NMOS：{}\n"
            "PMOS：{}\n"
            "电阻：{}\n"
            "MIM电容：{}\n"
            "普通信号网络：{}\n\n"
            "布线约定：VDD左侧、VSS右侧，普通端口位于上/下边界；\n"
            "M2横向、M3纵向；M3标签使用42/10；\n"
            "已启用电阻自动旋转、局部逃逸、MIM 1.20um M2避让，\n"
            "并将VDD/VSS宽电源轨纳入M3间距规划。\n\n"
            "生成结果尚未自动保存。\n"
            "请先检查版图，再按Ctrl+S保存；最终仍建议手动运行DRC/LVS。"
            .format(
                os.path.basename(reference_path),
                circuit["name"],
                counts["NMOS"],
                counts["PMOS"],
                counts["RES"],
                counts["MIM"],
                route_result["signal_nets"],
            )
        )

    except Exception as error:
        show_error(str(error))


main()