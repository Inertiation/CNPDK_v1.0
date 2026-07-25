# -*- coding: utf-8 -*-

import math
import pya


class NMOSPCell(pya.PCellDeclarationHelper):
    """
    CNPDK基础3.3V NMOS PCell

    Gate Contact模式：
    - None：Gate保持独立，不生成互连
    - Top：上方生成Poly Bus、Contact阵列和Metal1
    - Bottom：下方生成Poly Bus、Contact阵列和Metal1
    """

    # ============================================================
    # 工艺固定参数，单位：μm
    # ============================================================

    CONTACT_SIZE = 0.22
    CONTACT_SPACE = 0.25

    ACTIVE_CONTACT_ENC = 0.07
    ACTIVE_CONTACT_TO_GATE = 0.15

    POLY_CONTACT_ENC = 0.07
    METAL1_CONTACT_ENC = 0.06

    MIN_CHANNEL_WIDTH = 0.22
    MIN_CHANNEL_LENGTH = 0.28

    ACTIVE_GATE_OVERHANG = 0.24
    POLY_EXTENSION = 0.22

    NPLUS_ENCLOSURE = 0.23

    # Gate Poly Contact到Active的距离
    POLY_CONTACT_TO_ACTIVE = 0.17

    def __init__(self):
        super(NMOSPCell, self).__init__()

        # ========================================================
        # 核心参数
        # ========================================================

        self.param(
            "w",
            self.TypeDouble,
            "宽度 / Width W (μm)",
            default=1.0
        )

        self.param(
            "l",
            self.TypeDouble,
            "长度 / Length L (μm)",
            default=0.28
        )

        self.param(
            "nf",
            self.TypeInt,
            "沟道数量 / Fingers",
            default=1
        )

        self.param(
            "total_width",
            self.TypeDouble,
            "总宽度 / Total Width (μm)",
            default=1.0,
            readonly=True
        )

        # ========================================================
        # Gate Contact参数
        # ========================================================

        gate_position_parameter = self.param(
            "gate_contact_position",
            self.TypeList,
            "栅极通孔引出 / gate contact position",
            default=0
        )

        gate_position_parameter.add_choice(
            "不生成 / None",
            0
        )

        gate_position_parameter.add_choice(
            "上方 / Top",
            1
        )

        gate_position_parameter.add_choice(
            "下方 / Bottom",
            2
        )

        # ========================================================
        # Label参数
        # ========================================================

        self.param(
            "add_labels",
            self.TypeBoolean,
            "生成端口标签 / Add Pin Labels",
            default=False
        )

    def display_text_impl(self):
        """
        KLayout层级窗口中的PCell名称。
        """

        return (
            "NMOS_W%.3f_L%.3f_Fingers%d"
            % (
                self.w,
                self.l,
                self.nf
            )
        )

    def coerce_parameters_impl(self):
        """
        检查并修正非法参数。
        """

        if self.w < self.MIN_CHANNEL_WIDTH:
            self.w = self.MIN_CHANNEL_WIDTH

        if self.l < self.MIN_CHANNEL_LENGTH:
            self.l = self.MIN_CHANNEL_LENGTH

        if self.nf < 1:
            self.nf = 1

        if self.gate_contact_position not in (0, 1, 2):
            self.gate_contact_position = 0

        # W至少需要容纳一行Contact
        minimum_contact_width = (
            self.CONTACT_SIZE
            + 2.0 * self.ACTIVE_CONTACT_ENC
        )

        if self.w < minimum_contact_width:
            self.w = minimum_contact_width

        self.total_width = (
            self.w * self.nf
        )

    def produce_impl(self):
        """
        生成NMOS版图。
        """

        dbu = self.layout.dbu

        def to_dbu(value_um):
            return int(round(value_um / dbu))

        # ========================================================
        # 图层
        # ========================================================

        active_index = self.layout.layer(
            pya.LayerInfo(
                22, 0,
                "有源区 / Active"
            )
        )

        poly_index = self.layout.layer(
            pya.LayerInfo(
                30, 0,
                "多晶硅 / Poly"
            )
        )

        poly_label_index = self.layout.layer(
            pya.LayerInfo(
                30, 10,
                "多晶硅标签 / Poly Label"
            )
        )

        nplus_index = self.layout.layer(
            pya.LayerInfo(
                32, 0,
                "N型注入 / N+ Implant"
            )
        )

        contact_index = self.layout.layer(
            pya.LayerInfo(
                33, 0,
                "接触孔 / Contact"
            )
        )

        metal1_index = self.layout.layer(
            pya.LayerInfo(
                34, 0,
                "第一层金属 / Metal 1"
            )
        )

        metal1_label_index = self.layout.layer(
            pya.LayerInfo(
                34, 10,
                "M1标签 / Metal 1 Label"
            )
        )

        # ========================================================
        # 参数转换
        # ========================================================

        w = to_dbu(self.w)
        l = to_dbu(self.l)

        contact_size = to_dbu(
            self.CONTACT_SIZE
        )

        contact_space = to_dbu(
            self.CONTACT_SPACE
        )

        active_contact_enc = to_dbu(
            self.ACTIVE_CONTACT_ENC
        )

        active_contact_to_gate = to_dbu(
            self.ACTIVE_CONTACT_TO_GATE
        )

        poly_contact_enc = to_dbu(
            self.POLY_CONTACT_ENC
        )

        metal1_contact_enc = to_dbu(
            self.METAL1_CONTACT_ENC
        )

        active_gate_overhang = to_dbu(
            self.ACTIVE_GATE_OVERHANG
        )

        poly_extension = to_dbu(
            self.POLY_EXTENSION
        )

        nplus_enclosure = to_dbu(
            self.NPLUS_ENCLOSURE
        )

        poly_contact_to_active = to_dbu(
            self.POLY_CONTACT_TO_ACTIVE
        )

        # ========================================================
        # Source/Drain扩散区宽度
        #
        # 0.15 + 0.22 + 0.15 = 0.52μm
        # ========================================================

        diffusion_width = max(
            contact_size
            + 2 * active_contact_to_gate,
            active_gate_overhang
        )

        # NMOS Active总长度
        device_width = (
            (self.nf + 1) * diffusion_width
            + self.nf * l
        )

        # ========================================================
        # 自动计算Source/Drain Contact行数
        # ========================================================

        available_contact_height = (
            w - 2 * active_contact_enc
        )

        contact_pitch = (
            contact_size + contact_space
        )

        contact_rows = int(
            math.floor(
                (
                    available_contact_height
                    + contact_space
                )
                / contact_pitch
            )
        )

        if contact_rows < 1:
            contact_rows = 1

        contact_array_height = (
            contact_rows * contact_size
            + (contact_rows - 1) * contact_space
        )

        contact_y_start = (
            w - contact_array_height
        ) // 2

        # ========================================================
        # Active
        # ========================================================

        active_box = pya.Box(
            0,
            0,
            device_width,
            w
        )

        self.cell.shapes(
            active_index
        ).insert(active_box)

        # ========================================================
        # NPLUS
        # ========================================================

        nplus_box = pya.Box(
            -nplus_enclosure,
            -nplus_enclosure,
            device_width + nplus_enclosure,
            w + nplus_enclosure
        )

        self.cell.shapes(
            nplus_index
        ).insert(nplus_box)

        # ========================================================
        # 独立Gate
        # ========================================================

        gate_centers = []

        for finger in range(self.nf):

            gate_x1 = (
                diffusion_width
                + finger * (
                    diffusion_width + l
                )
            )

            gate_x2 = gate_x1 + l

            gate_center_x = (
                gate_x1 + gate_x2
            ) // 2

            gate_centers.append(
                gate_center_x
            )

            poly_box = pya.Box(
                gate_x1,
                -poly_extension,
                gate_x2,
                w + poly_extension
            )

            self.cell.shapes(
                poly_index
            ).insert(poly_box)

        # ========================================================
        # Source/Drain Contact
        # ========================================================

        for diffusion_number in range(
            self.nf + 1
        ):

            diffusion_x1 = (
                diffusion_number * (
                    diffusion_width + l
                )
            )

            contact_x1 = (
                diffusion_x1
                + (
                    diffusion_width
                    - contact_size
                ) // 2
            )

            contact_x2 = (
                contact_x1 + contact_size
            )

            # 生成一列Source/Drain Contact
            for row in range(contact_rows):

                contact_y1 = (
                    contact_y_start
                    + row * contact_pitch
                )

                contact_y2 = (
                    contact_y1
                    + contact_size
                )

                contact_box = pya.Box(
                    contact_x1,
                    contact_y1,
                    contact_x2,
                    contact_y2
                )

                self.cell.shapes(
                    contact_index
                ).insert(contact_box)

            # Metal1覆盖Contact列
            metal1_box = pya.Box(
                contact_x1
                - metal1_contact_enc,
                contact_y_start
                - metal1_contact_enc,
                contact_x2
                + metal1_contact_enc,
                contact_y_start
                + contact_array_height
                + metal1_contact_enc
            )

            self.cell.shapes(
                metal1_index
            ).insert(metal1_box)

            # ----------------------------------------------------
            # 可选Source/Drain Label
            # ----------------------------------------------------

            if self.add_labels:

                if diffusion_number % 2 == 0:
                    terminal_type = "S"
                else:
                    terminal_type = "D"

                terminal_number = (
                    diffusion_number // 2 + 1
                )

                if self.nf == 1:
                    label_name = terminal_type
                else:
                    label_name = (
                        terminal_type
                        + str(terminal_number)
                    )

                label_x = (
                    contact_x1 + contact_x2
                ) // 2

                label_y = w // 2

                label = pya.Text(
                    label_name,
                    pya.Trans(
                        pya.Point(
                            label_x,
                            label_y
                        )
                    )
                )

                self.cell.shapes(
                    metal1_label_index
                ).insert(label)

        # ========================================================
        # Gate Contact及Gate互连
        #
        # None：
        #   不生成任何Gate互连。
        #
        # Top/Bottom：
        #   使用Poly Bus连接全部Gate；
        #   在Bus中自动生成Contact阵列；
        #   使用连续Metal1覆盖Contact阵列。
        # ========================================================

        if self.gate_contact_position != 0:

            # Gate Bus横跨第一根Gate到最后一根Gate
            gate_bus_center_x = (
                gate_centers[0]
                + gate_centers[-1]
            ) // 2

            gate_bus_width = (
                gate_centers[-1]
                - gate_centers[0]
                + l
            )

            # Bus至少需要容纳一个Contact及Poly包围
            minimum_gate_bus_width = (
                contact_size
                + 2 * poly_contact_enc
            )

            if gate_bus_width < minimum_gate_bus_width:
                gate_bus_width = minimum_gate_bus_width

            gate_bus_x1 = (
                gate_bus_center_x
                - gate_bus_width // 2
            )

            gate_bus_x2 = (
                gate_bus_x1
                + gate_bus_width
            )

            # ----------------------------------------------------
            # 根据Gate Bus长度计算Contact数量
            # ----------------------------------------------------

            available_gate_contact_width = (
                gate_bus_width
                - 2 * poly_contact_enc
            )

            gate_contact_columns = int(
                math.floor(
                    (
                        available_gate_contact_width
                        + contact_space
                    )
                    / contact_pitch
                )
            )

            if gate_contact_columns < 1:
                gate_contact_columns = 1

            gate_contact_array_width = (
                gate_contact_columns
                * contact_size
                + (
                    gate_contact_columns - 1
                )
                * contact_space
            )

            gate_contact_x_start = (
                gate_bus_center_x
                - gate_contact_array_width // 2
            )

            # ----------------------------------------------------
            # 上方Gate Contact
            # ----------------------------------------------------

            if self.gate_contact_position == 1:

                gate_contact_y1 = (
                    w + poly_contact_to_active
                )

                gate_contact_y2 = (
                    gate_contact_y1
                    + contact_size
                )

            # ----------------------------------------------------
            # 下方Gate Contact
            # ----------------------------------------------------

            else:

                gate_contact_y2 = (
                    -poly_contact_to_active
                )

                gate_contact_y1 = (
                    gate_contact_y2
                    - contact_size
                )

            # ----------------------------------------------------
            # 生成连接全部Gate的Poly Bus
            # ----------------------------------------------------

            gate_bus_y1 = (
                gate_contact_y1
                - poly_contact_enc
            )

            gate_bus_y2 = (
                gate_contact_y2
                + poly_contact_enc
            )

            poly_bus_box = pya.Box(
                gate_bus_x1,
                gate_bus_y1,
                gate_bus_x2,
                gate_bus_y2
            )

            self.cell.shapes(
                poly_index
            ).insert(poly_bus_box)

            # ----------------------------------------------------
            # 生成横向Gate Contact阵列
            # ----------------------------------------------------

            for column in range(
                gate_contact_columns
            ):

                gate_contact_x1 = (
                    gate_contact_x_start
                    + column * contact_pitch
                )

                gate_contact_x2 = (
                    gate_contact_x1
                    + contact_size
                )

                gate_contact_box = pya.Box(
                    gate_contact_x1,
                    gate_contact_y1,
                    gate_contact_x2,
                    gate_contact_y2
                )

                self.cell.shapes(
                    contact_index
                ).insert(gate_contact_box)

            # ----------------------------------------------------
            # Metal1覆盖并连接整排Gate Contact
            # ----------------------------------------------------

            gate_metal1_box = pya.Box(
                gate_contact_x_start
                - metal1_contact_enc,
                gate_contact_y1
                - metal1_contact_enc,
                gate_contact_x_start
                + gate_contact_array_width
                + metal1_contact_enc,
                gate_contact_y2
                + metal1_contact_enc
            )

            self.cell.shapes(
                metal1_index
            ).insert(gate_metal1_box)

        # ========================================================
        # 可选Gate Label
        # ========================================================

        if self.add_labels:

            # ----------------------------------------------------
            # Gate已经通过Bus互连
            # ----------------------------------------------------

            if self.gate_contact_position != 0:

                gate_label_name = "G"

                gate_label_x = (
                    gate_centers[0]
                    + gate_centers[-1]
                ) // 2

                if self.gate_contact_position == 1:

                    gate_label_y = (
                        w + poly_extension // 2
                    )

                else:

                    gate_label_y = (
                        -poly_extension // 2
                    )

                gate_label = pya.Text(
                    gate_label_name,
                    pya.Trans(
                        pya.Point(
                            gate_label_x,
                            gate_label_y
                        )
                    )
                )

                self.cell.shapes(
                    poly_label_index
                ).insert(gate_label)

            # ----------------------------------------------------
            # Gate没有互连，使用G1、G2等独立名称
            # ----------------------------------------------------

            else:

                for finger in range(self.nf):

                    gate_label_x = (
                        gate_centers[finger]
                    )

                    top_gate_label_y = (
                        w + poly_extension // 2
                    )

                    bottom_gate_label_y = (
                        -poly_extension // 2
                    )

                    if self.nf == 1:
                        gate_label_name = "G"
                    else:
                        gate_label_name = (
                            "G"
                            + str(finger + 1)
                        )

                    top_gate_label = pya.Text(
                        gate_label_name,
                        pya.Trans(
                            pya.Point(
                                gate_label_x,
                                top_gate_label_y
                            )
                        )
                    )

                    self.cell.shapes(
                        poly_label_index
                    ).insert(top_gate_label)

                    bottom_gate_label = pya.Text(
                        gate_label_name,
                        pya.Trans(
                            pya.Point(
                                gate_label_x,
                                bottom_gate_label_y
                            )
                        )
                    )

                    self.cell.shapes(
                        poly_label_index
                    ).insert(bottom_gate_label)