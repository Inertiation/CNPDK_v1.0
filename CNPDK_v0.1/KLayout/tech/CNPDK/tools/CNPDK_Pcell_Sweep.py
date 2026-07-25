# -*- coding: utf-8 -*-
"""
CNPDK PCell Parameter Sweep and QA Gallery Generator v1.0
==========================================================

用途
----
在KLayout当前Layout中，直接调用已经注册的CNPDK Library，批量生成
一张PCell参数扫描与展示版图，用于：

1. 验证PCell在不同参数下能否稳定生成；
2. 生成统一的DRC回归测试输入；
3. 展示CNPDK器件种类与参数化能力；
4. 为后续版本对比提供固定的Golden Test Layout。

路径策略
--------
本脚本不导入nmos.py、pmos.py等文件，也不包含任何绝对路径。
它只通过以下接口调用已注册PCell：

    pya.Library.library_by_name("CNPDK")

推荐将脚本放在：

    CNPDK/tools/CNPDK_PCell_Parameter_Sweep.py

运行条件
--------
1. 已经在KLayout中打开一个Layout；
2. CNPDK Library已经注册；
3. 当前Layout中不存在非空的CNPDK_PCELL_SWEEP测试Cell。

输出
----
顶层Cell：
    CNPDK_PCELL_SWEEP

分组Cell：
    CNPDK_QA_NMOS
    CNPDK_QA_PMOS
    CNPDK_QA_RESISTOR
    CNPDK_QA_MIM
    CNPDK_QA_VIA
    CNPDK_QA_CONTACT
    CNPDK_QA_GUARDRING

QA文字层：
    200/0

说明：200/0仅作为非制造测试说明层，不应写入正式流片数据。
"""

import pya


# ======================================================================
# 1. Library、PCell与版图配置
# ======================================================================

LIBRARY_NAME = "CNPDK"
TOP_CELL_NAME = "CNPDK_PCELL_SWEEP"

PCELL_NMOS = "NMOS"
PCELL_PMOS = "PMOS"
PCELL_RESISTOR = "电阻P_PO_SAB"
PCELL_MIM = "电容MIM"
PCELL_VIA = "金属通孔"
PCELL_CONTACT = "接触孔"
PCELL_GUARDRING = "GuardRing"

QA_TEXT_LAYER = pya.LayerInfo(200, 0)

INSTANCES_PER_ROW = 5
INSTANCE_SPACING_UM = 5.0
GROUP_SPACING_UM = 15.0
INSTANCE_LABEL_GAP_UM = 1.0
INSTANCE_LABEL_HEIGHT_UM = 3.0
GROUP_LABEL_GAP_UM = 3.0


# ======================================================================
# 2. 推荐扫描参数
# ======================================================================

MOS_CASES = [
    {
        "w": 1.0,
        "l": 0.28,
        "nf": 1,
        "gate_contact_position": 0,
        "add_labels": True,
    },
    {
        "w": 2.0,
        "l": 0.28,
        "nf": 2,
        "gate_contact_position": 1,
        "add_labels": True,
    },
    {
        "w": 4.0,
        "l": 0.28,
        "nf": 4,
        "gate_contact_position": 2,
        "add_labels": True,
    },
    {
        "w": 2.0,
        "l": 0.50,
        "nf": 1,
        "gate_contact_position": 1,
        "add_labels": True,
    },
    {
        "w": 2.0,
        "l": 1.00,
        "nf": 2,
        "gate_contact_position": 1,
        "add_labels": True,
    },
    {
        "w": 2.0,
        "l": 2.00,
        "nf": 4,
        "gate_contact_position": 2,
        "add_labels": True,
    },
    {
        "w": 8.0,
        "l": 1.00,
        "nf": 4,
        "gate_contact_position": 1,
        "add_labels": True,
    },
]

RESISTOR_CASES = [
    {"length": 5.0, "width": 1.0, "sheet_resistance": 311.0},
    {"length": 10.0, "width": 1.0, "sheet_resistance": 311.0},
    {"length": 20.0, "width": 1.0, "sheet_resistance": 311.0},
    {"length": 10.0, "width": 2.0, "sheet_resistance": 311.0},
    {"length": 20.0, "width": 2.0, "sheet_resistance": 311.0},
]

MIM_CASES = [
    {"length": 5.0, "width": 5.0, "cap_density": 0.002},
    {"length": 10.0, "width": 5.0, "cap_density": 0.002},
    {"length": 10.0, "width": 10.0, "cap_density": 0.002},
    {"length": 20.0, "width": 10.0, "cap_density": 0.002},
    {"length": 20.0, "width": 20.0, "cap_density": 0.002},
]

ARRAY_CASES = [
    (1, 1),
    (1, 4),
    (4, 1),
    (2, 2),
    (4, 4),
]

GUARDRING_CASES = [
    (3.0, 3.0),
    (5.0, 5.0),
    (10.0, 5.0),
    (5.0, 10.0),
    (10.0, 10.0),
]


# ======================================================================
# 3. 消息、坐标与PCell调用
# ======================================================================

def show_info(message):
    pya.MessageBox.info(
        "CNPDK PCell参数扫描",
        message,
        pya.MessageBox.Ok,
    )


def show_error(message):
    pya.MessageBox.critical(
        "CNPDK PCell参数扫描错误",
        message,
        pya.MessageBox.Ok,
    )


def um_to_dbu(layout, value_um):
    return int(round(float(value_um) / layout.dbu))


def create_pcell_variant(layout, library, pcell_name, parameters):
    declaration = library.layout().pcell_declaration(pcell_name)
    if declaration is None:
        raise RuntimeError(
            "CNPDK Library中没有找到PCell：{}".format(pcell_name)
        )

    cell_index = layout.add_pcell_variant(
        library,
        declaration.id(),
        parameters,
    )
    cell = layout.cell(cell_index)
    if cell is None:
        raise RuntimeError(
            "无法创建PCell Variant：{} {}".format(
                pcell_name, parameters
            )
        )
    return cell


def insert_instance(parent_cell, child_cell, x_dbu, y_dbu):
    transform = pya.Trans(int(x_dbu), int(y_dbu))
    parent_cell.insert(
        pya.CellInstArray(child_cell.cell_index(), transform)
    )
    return transform


def insert_text(cell, layer_index, text, x_dbu, y_dbu):
    label = pya.Text(
        str(text),
        pya.Trans(int(x_dbu), int(y_dbu)),
    )
    cell.shapes(layer_index).insert(label)


def gate_name(value):
    return {
        0: "None",
        1: "Top",
        2: "Bottom",
    }.get(int(value), str(value))


def ring_name(value):
    return "N+ NWell" if int(value) == 0 else "P+ PSub"


# ======================================================================
# 4. 扫描条目构建
# ======================================================================

def build_mos_entries(device_name):
    pcell_name = PCELL_NMOS if device_name == "NMOS" else PCELL_PMOS
    entries = []
    for index, parameters in enumerate(MOS_CASES, 1):
        label = (
            "{0}_{1:02d}  W={2:g}  L={3:g}  NF={4}  Gate={5}"
        ).format(
            device_name,
            index,
            parameters["w"],
            parameters["l"],
            parameters["nf"],
            gate_name(parameters["gate_contact_position"]),
        )
        entries.append({
            "pcell": pcell_name,
            "parameters": dict(parameters),
            "label": label,
        })
    return entries


def build_resistor_entries():
    entries = []
    for index, parameters in enumerate(RESISTOR_CASES, 1):
        resistance = (
            parameters["sheet_resistance"]
            * parameters["length"]
            / parameters["width"]
        )
        label = (
            "RES_{0:02d}  L={1:g}  W={2:g}  Rs={3:g}  R~{4:g}ohm"
        ).format(
            index,
            parameters["length"],
            parameters["width"],
            parameters["sheet_resistance"],
            resistance,
        )
        entries.append({
            "pcell": PCELL_RESISTOR,
            "parameters": dict(parameters),
            "label": label,
        })
    return entries


def build_mim_entries():
    entries = []
    for index, parameters in enumerate(MIM_CASES, 1):
        capacitance = (
            parameters["cap_density"]
            * parameters["length"]
            * parameters["width"]
        )
        label = (
            "MIM_{0:02d}  L={1:g}  W={2:g}  Cd={3:g}  C~{4:g}pF"
        ).format(
            index,
            parameters["length"],
            parameters["width"],
            parameters["cap_density"],
            capacitance,
        )
        entries.append({
            "pcell": PCELL_MIM,
            "parameters": dict(parameters),
            "label": label,
        })
    return entries


def build_via_entries():
    entries = []
    for via_type in (1, 2):
        for rows, columns in ARRAY_CASES:
            parameters = {
                "via_type": via_type,
                "cut": 0.26,
                "spacing": 0.26,
                "rows": rows,
                "columns": columns,
                "bottom_enclosure": 0.06,
                "top_enclosure": 0.06,
            }
            label = "VIA{0}  Rows={1}  Cols={2}".format(
                via_type, rows, columns
            )
            entries.append({
                "pcell": PCELL_VIA,
                "parameters": parameters,
                "label": label,
            })
    return entries


def build_contact_entries():
    entries = []
    for contact_type in (0, 1):
        type_name = "Active-M1" if contact_type == 0 else "Poly-M1"
        for rows, columns in ARRAY_CASES:
            parameters = {
                "contact_type": contact_type,
                "cut": 0.22,
                "spacing": 0.25,
                "rows": rows,
                "columns": columns,
                "bottom_enclosure": 0.07,
                "metal1_enclosure": 0.06,
            }
            label = "CONTACT {0}  Rows={1}  Cols={2}".format(
                type_name, rows, columns
            )
            entries.append({
                "pcell": PCELL_CONTACT,
                "parameters": parameters,
                "label": label,
            })
    return entries


def build_guardring_entries():
    entries = []
    for ring_type in (0, 1):
        for inner_width, inner_height in GUARDRING_CASES:
            parameters = {
                "ring_type": ring_type,
                "inner_width": inner_width,
                "inner_height": inner_height,
            }
            label = "GR {0}  IW={1:g}  IH={2:g}".format(
                ring_name(ring_type),
                inner_width,
                inner_height,
            )
            entries.append({
                "pcell": PCELL_GUARDRING,
                "parameters": parameters,
                "label": label,
            })
    return entries


def build_groups():
    return [
        ("NMOS PARAMETER SWEEP", "CNPDK_QA_NMOS", build_mos_entries("NMOS")),
        ("PMOS PARAMETER SWEEP", "CNPDK_QA_PMOS", build_mos_entries("PMOS")),
        (
            "P+ POLY SAB RESISTOR PARAMETER SWEEP",
            "CNPDK_QA_RESISTOR",
            build_resistor_entries(),
        ),
        ("MIM CAPACITOR PARAMETER SWEEP", "CNPDK_QA_MIM", build_mim_entries()),
        ("VIA ARRAY PARAMETER SWEEP", "CNPDK_QA_VIA", build_via_entries()),
        (
            "CONTACT ARRAY PARAMETER SWEEP",
            "CNPDK_QA_CONTACT",
            build_contact_entries(),
        ),
        (
            "GUARDRING PARAMETER SWEEP",
            "CNPDK_QA_GUARDRING",
            build_guardring_entries(),
        ),
    ]


# ======================================================================
# 5. 动态网格排布
# ======================================================================

def require_empty_named_cell(layout, name):
    existing = layout.cell(name)
    if existing is not None:
        if not existing.is_empty():
            raise RuntimeError(
                "Layout中已存在非空测试Cell：{}\n\n"
                "为避免覆盖旧的回归版图，本次生成已经停止。"
                "请新建Layout，或手动删除旧测试Cell后重试。"
                .format(name)
            )
        return existing
    return layout.create_cell(name)


def place_group(
    layout,
    library,
    group_cell,
    group_title,
    entries,
    qa_layer_index,
):
    spacing = um_to_dbu(layout, INSTANCE_SPACING_UM)
    label_gap = um_to_dbu(layout, INSTANCE_LABEL_GAP_UM)
    label_height = um_to_dbu(layout, INSTANCE_LABEL_HEIGHT_UM)
    group_label_gap = um_to_dbu(layout, GROUP_LABEL_GAP_UM)

    x_cursor = 0
    y_cursor = 0
    row_height = 0
    row_width = 0
    maximum_width = 0
    placed_count = 0

    for index, entry in enumerate(entries):
        if index > 0 and index % INSTANCES_PER_ROW == 0:
            maximum_width = max(maximum_width, row_width)
            y_cursor += row_height + spacing
            x_cursor = 0
            row_height = 0
            row_width = 0

        pcell = create_pcell_variant(
            layout,
            library,
            entry["pcell"],
            entry["parameters"],
        )
        box = pcell.bbox()
        transform = pya.Trans(
            x_cursor - box.left,
            y_cursor - box.bottom,
        )
        group_cell.insert(
            pya.CellInstArray(pcell.cell_index(), transform)
        )

        world_right = x_cursor + box.width()
        world_top = y_cursor + box.height()
        insert_text(
            group_cell,
            qa_layer_index,
            entry["label"],
            x_cursor,
            world_top + label_gap,
        )

        allocated_height = box.height() + label_gap + label_height
        row_height = max(row_height, allocated_height)
        x_cursor = world_right + spacing
        row_width = max(row_width, world_right)
        placed_count += 1

    maximum_width = max(maximum_width, row_width)
    total_height = y_cursor + row_height

    insert_text(
        group_cell,
        qa_layer_index,
        group_title,
        0,
        total_height + group_label_gap,
    )

    return {
        "count": placed_count,
        "width": maximum_width,
        "height": total_height + group_label_gap + label_height,
    }


def place_groups_in_top(layout, top_cell, group_results, qa_layer_index):
    group_spacing = um_to_dbu(layout, GROUP_SPACING_UM)
    y_cursor = 0
    total_count = 0

    insert_text(
        top_cell,
        qa_layer_index,
        "CNPDK PCELL PARAMETER SWEEP / QA GALLERY",
        0,
        0,
    )
    y_cursor += um_to_dbu(layout, 5.0)

    for group_cell, result in group_results:
        insert_instance(top_cell, group_cell, 0, y_cursor)
        y_cursor += result["height"] + group_spacing
        total_count += result["count"]

    return total_count


# ======================================================================
# 6. KLayout上下文与主程序
# ======================================================================

def current_context():
    main_window = pya.Application.instance().main_window()
    view = main_window.current_view()
    if view is None:
        raise RuntimeError(
            "当前没有打开Layout。请先新建或打开一个Layout后运行。"
        )

    cell_view = view.active_cellview()
    if cell_view is None or not cell_view.is_valid():
        raise RuntimeError("当前没有有效的CellView。")

    layout = cell_view.layout()
    if layout is None:
        raise RuntimeError("无法取得当前Layout。")
    return main_window, view, cell_view, layout


def activate_top_cell(view, cell_view, top_cell):
    try:
        cell_view.cell = top_cell
        return
    except Exception:
        pass
    try:
        view.select_cell(top_cell.cell_index(), 0)
    except Exception:
        pass


def main():
    try:
        _main_window, view, cell_view, layout = current_context()

        library = pya.Library.library_by_name(LIBRARY_NAME)
        if library is None:
            raise RuntimeError(
                "没有找到已注册的CNPDK Library。\n\n"
                "请先运行CNPDK/pymacros/library.py，"
                "或将其设置为Run on start-up。"
            )

        top_cell = require_empty_named_cell(layout, TOP_CELL_NAME)
        qa_layer_index = layout.layer(QA_TEXT_LAYER)

        group_results = []
        for group_title, group_name, entries in build_groups():
            group_cell = require_empty_named_cell(layout, group_name)
            result = place_group(
                layout,
                library,
                group_cell,
                group_title,
                entries,
                qa_layer_index,
            )
            group_results.append((group_cell, result))

        total_count = place_groups_in_top(
            layout,
            top_cell,
            group_results,
            qa_layer_index,
        )

        activate_top_cell(view, cell_view, top_cell)
        view.add_missing_layers()
        view.zoom_fit()

        show_info(
            "PCell参数扫描版图生成完成。\n\n"
            "顶层Cell：{}\n"
            "分组数量：{}\n"
            "测试实例：{}\n"
            "每行实例：{}\n"
            "器件间距：{}um\n"
            "说明层：200/0（非制造层）\n\n"
            "请保存Layout后运行整合DRC。\n"
            "正式流片数据应排除200/0说明层。"
            .format(
                TOP_CELL_NAME,
                len(group_results),
                total_count,
                INSTANCES_PER_ROW,
                INSTANCE_SPACING_UM,
            )
        )

    except Exception as error:
        show_error(str(error))


main()