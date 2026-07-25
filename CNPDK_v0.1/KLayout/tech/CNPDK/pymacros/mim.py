# -*- coding: utf-8 -*-
"""CNPDK GF180MCU-style MIM Option-A capacitor PCell.

Physical/recognition layers:
    FuseTop 75/0  : MIM top plate; defines effective capacitor area
    Metal2  36/0  : MIM bottom plate
    Via2    38/0  : top-plate connection to Metal3
    Metal3  42/0  : top-terminal routing/landing metal
    CAP_MK 117/5  : MIM capacitor recognition marker

Estimated capacitance uses only the area term:
    C_est [pF] = density [pF/um^2] * length [um] * width [um]
Fringing capacitance and process variation are not included.
"""

import math
import pya


class MIMCapacitorPCell(pya.PCellDeclarationHelper):
    # CNPDK GDS layers
    L_METAL2 = pya.LayerInfo(36, 0)
    L_VIA2 = pya.LayerInfo(38, 0)
    L_METAL3 = pya.LayerInfo(42, 0)
    L_FUSETOP = pya.LayerInfo(75, 0)
    L_CAP_MK = pya.LayerInfo(117, 5)

    # MIM geometry, in um
    MIN_PLATE_SIZE = 5.0
    MAX_PLATE_SIZE = 100.0

    # Metal2 keeps only the official minimum enclosure around FuseTop.  The
    # bottom terminal is routed directly from Metal2 by the layout designer.
    BOTTOM_PLATE_ENCLOSURE = 0.60

    VIA_SIZE = 0.26
    MIM_VIA_SPACE = 0.50
    MIM_VIA_PITCH = VIA_SIZE + MIM_VIA_SPACE
    PLATE_ENC_VIA = 0.40
    M3_ENC_VIA = 0.12

    DEFAULT_DENSITY = 0.002  # pF/um^2, educational nominal default

    def __init__(self):
        super(MIMCapacitorPCell, self).__init__()

        self.param(
            "length",
            self.TypeDouble,
            "上极板长度 / Top Plate Length (um)",
            default=10.0
        )
        self.param(
            "width",
            self.TypeDouble,
            "上极板宽度 / Top Plate Width (um)",
            default=10.0
        )
        self.param(
            "cap_density",
            self.TypeDouble,
            "单位面积电容 / Capacitance Density (pF/um^2)\n"
            "Capacitance Density的默认值为0.002 pF/um^2",
            default=self.DEFAULT_DENSITY
        )
        self.param(
            "estimated_capacitance",
            self.TypeDouble,
            "预估电容 / Estimated Capacitance (pF)",
            default=0.2,
            readonly=True
        )

    def display_text_impl(self):
        return "CNPDK_MIM_CAP_L%.3f_W%.3f_CD%.3f_C%.3f" % (
            self.length,
            self.width,
            self.cap_density,
            self.estimated_capacitance
        )

    def coerce_parameters_impl(self):
        self.length = min(
            max(float(self.length), self.MIN_PLATE_SIZE),
            self.MAX_PLATE_SIZE
        )
        self.width = min(
            max(float(self.width), self.MIN_PLATE_SIZE),
            self.MAX_PLATE_SIZE
        )
        self.cap_density = max(float(self.cap_density), 0.001)

        self.estimated_capacitance = (
            self.cap_density * self.length * self.width
        )

    def can_create_from_shape_impl(self):
        return False

    def transformation_from_shape_impl(self):
        return pya.Trans()

    def get_parameters_from_shape_impl(self):
        pass

    def produce_impl(self):
        dbu = self.layout.dbu

        def to_dbu(value_um):
            return int(round(float(value_um) / dbu))

        def make_box(x1, y1, x2, y2):
            return pya.Box(
                to_dbu(x1), to_dbu(y1),
                to_dbu(x2), to_dbu(y2)
            )

        def insert_box(layer_index, x1, y1, x2, y2):
            self.cell.shapes(layer_index).insert(
                make_box(x1, y1, x2, y2)
            )

        metal2_layer = self.layout.layer(self.L_METAL2)
        via2_layer = self.layout.layer(self.L_VIA2)
        metal3_layer = self.layout.layer(self.L_METAL3)
        fusetop_layer = self.layout.layer(self.L_FUSETOP)
        cap_mk_layer = self.layout.layer(self.L_CAP_MK)

        # ------------------------------------------------------------
        # 1. Effective top plate and recognition mark
        # ------------------------------------------------------------
        top_x1 = 0.0
        top_y1 = 0.0
        top_x2 = self.length
        top_y2 = self.width

        insert_box(
            fusetop_layer,
            top_x1, top_y1,
            top_x2, top_y2
        )

        # CAP_MK exactly coincides with FuseTop in this first version.
        insert_box(
            cap_mk_layer,
            top_x1, top_y1,
            top_x2, top_y2
        )

        # ------------------------------------------------------------
        # 2. Metal2 bottom plate
        # ------------------------------------------------------------
        bottom_x1 = top_x1 - self.BOTTOM_PLATE_ENCLOSURE
        bottom_y1 = top_y1 - self.BOTTOM_PLATE_ENCLOSURE
        bottom_x2 = top_x2 + self.BOTTOM_PLATE_ENCLOSURE
        bottom_y2 = top_y2 + self.BOTTOM_PLATE_ENCLOSURE

        insert_box(
            metal2_layer,
            bottom_x1, bottom_y1,
            bottom_x2, bottom_y2
        )

        # ------------------------------------------------------------
        # 3. Two-column Via2 array for the FuseTop/M3 top terminal
        # ------------------------------------------------------------
        available_height = self.width - 2.0 * self.PLATE_ENC_VIA
        via_count = max(1, int(math.floor(
            (available_height + self.MIM_VIA_SPACE)
            / self.MIM_VIA_PITCH
        )))

        via_array_height = (
            via_count * self.VIA_SIZE
            + (via_count - 1) * self.MIM_VIA_SPACE
        )
        via_y0 = 0.5 * (self.width - via_array_height)

        # Both Via2 columns are inside FuseTop.  Their edge-to-edge spacing is
        # the MIM Via2 array spacing of 0.50 um.
        top_via_x_positions = [
            top_x1 + self.PLATE_ENC_VIA,
            top_x1 + self.PLATE_ENC_VIA + self.MIM_VIA_PITCH
        ]

        for row in range(via_count):
            vy1 = via_y0 + row * self.MIM_VIA_PITCH
            vy2 = vy1 + self.VIA_SIZE

            for vx1 in top_via_x_positions:
                insert_box(
                    via2_layer,
                    vx1, vy1,
                    vx1 + self.VIA_SIZE, vy2
                )

        # ------------------------------------------------------------
        # 4. Metal3 landing for the FuseTop terminal
        # ------------------------------------------------------------
        top_via_x1 = top_via_x_positions[0]
        top_via_x2 = top_via_x_positions[-1] + self.VIA_SIZE

        insert_box(
            metal3_layer,
            top_via_x1 - self.M3_ENC_VIA,
            via_y0 - self.M3_ENC_VIA,
            top_via_x2 + self.M3_ENC_VIA,
            via_y0 + via_array_height + self.M3_ENC_VIA
        )