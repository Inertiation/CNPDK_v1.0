# -*- coding: utf-8 -*-
"""CNPDK P+ unsilicided Poly resistor PCell.

The structure corresponds conceptually to a normal rpposab resistor:
    Poly + P+ Implant + SAB + RES_MK + Contact + Metal1

The sheet resistance defaults to a user-provided educational reference value
and can be changed in the PCell UI.  It is used only for geometrical estimation
and is not a qualified GF180MCU production value.
"""

import math
import pya


class PPlusPolySABResistorPCell(pya.PCellDeclarationHelper):
    # CNPDK GDS layers
    L_POLY = pya.LayerInfo(30, 0)
    L_PPLUS = pya.LayerInfo(31, 0)
    L_CONTACT = pya.LayerInfo(33, 0)
    L_METAL1 = pya.LayerInfo(34, 0)
    L_SAB = pya.LayerInfo(49, 0)
    L_RES_MK = pya.LayerInfo(110, 5)

    # Default educational nominal value, ohm/square.  The user can override
    # it from the PCell UI for resistance estimation in another process.
    DEFAULT_SHEET_RESISTANCE = 311.0

    # Simplified GF180MCU-derived dimensions, in um.
    MIN_RESISTOR_WIDTH = 0.80
    MIN_EFFECTIVE_LENGTH = 0.50

    CONTACT_SIZE = 0.22
    CONTACT_SPACE = 0.25
    CONTACT_PITCH = CONTACT_SIZE + CONTACT_SPACE

    POLY_ENC_CONTACT = 0.07
    M1_ENC_CONTACT = 0.06
    SAB_TO_CONTACT = 0.22

    PPLUS_OVERLAP_POLY = 0.30
    SAB_OVERLAP_POLY_WIDTH = 0.28

    def __init__(self):
        super(PPlusPolySABResistorPCell, self).__init__()

        self.param(
            "length",
            self.TypeDouble,
            "有效长度 / Effective Length (um)",
            default=10.0
        )
        self.param(
            "width",
            self.TypeDouble,
            "电阻宽度 / Resistor Width (um)",
            default=1.0
        )
        self.param(
            "sheet_resistance",
            self.TypeDouble,
            "方块电阻 / Sheet Resistance (ohm/square)\n"
            "Sheet Resistance的默认值为311 Ohms",
            default=self.DEFAULT_SHEET_RESISTANCE
        )
        self.param(
            "estimated_resistance",
            self.TypeDouble,
            "预估阻值 / Estimated Resistance (ohm)",
            default=3110.0,
            readonly=True
        )

    def display_text_impl(self):
        return "CNPDK_PPLUS_POLY_SAB_R_L%.3f_W%.3f_RS%.2f_R%.2f" % (
            self.length,
            self.width,
            self.sheet_resistance,
            self.estimated_resistance
        )

    def coerce_parameters_impl(self):
        self.length = max(
            float(self.length), self.MIN_EFFECTIVE_LENGTH
        )
        self.width = max(
            float(self.width), self.MIN_RESISTOR_WIDTH
        )
        self.sheet_resistance = max(float(self.sheet_resistance), 0.001)

        # First-order geometry estimate:
        # R = Rsheet * Leffective / Weffective
        self.estimated_resistance = (
            self.sheet_resistance * self.length / self.width
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

        poly_layer = self.layout.layer(self.L_POLY)
        pplus_layer = self.layout.layer(self.L_PPLUS)
        contact_layer = self.layout.layer(self.L_CONTACT)
        metal1_layer = self.layout.layer(self.L_METAL1)
        sab_layer = self.layout.layer(self.L_SAB)
        res_mk_layer = self.layout.layer(self.L_RES_MK)

        # One Poly terminal consists of:
        # outer Poly enclosure + Contact + SAB-to-Contact spacing.
        terminal_length = (
            self.POLY_ENC_CONTACT
            + self.CONTACT_SIZE
            + self.SAB_TO_CONTACT
        )

        poly_x1 = 0.0
        poly_y1 = 0.0
        sab_x1 = terminal_length
        sab_x2 = sab_x1 + self.length
        poly_x2 = sab_x2 + terminal_length
        poly_y2 = self.width

        # 1. The full Poly strip includes the two contact terminal regions.
        insert_box(
            poly_layer,
            poly_x1, poly_y1,
            poly_x2, poly_y2
        )

        # 2. P+ implant dopes the complete Poly strip and overlaps it.
        insert_box(
            pplus_layer,
            poly_x1 - self.PPLUS_OVERLAP_POLY,
            poly_y1 - self.PPLUS_OVERLAP_POLY,
            poly_x2 + self.PPLUS_OVERLAP_POLY,
            poly_y2 + self.PPLUS_OVERLAP_POLY
        )

        # 3. SAB defines the unsilicided effective resistor length.  It extends
        # beyond both Poly edges in the width direction by 0.28 um.
        insert_box(
            sab_layer,
            sab_x1,
            poly_y1 - self.SAB_OVERLAP_POLY_WIDTH,
            sab_x2,
            poly_y2 + self.SAB_OVERLAP_POLY_WIDTH
        )

        # 4. RES_MK has the same effective length as SAB and covers the Poly
        # resistor width.  It is an identification layer for DRC/LVS.
        insert_box(
            res_mk_layer,
            sab_x1, poly_y1,
            sab_x2, poly_y2
        )

        # 5. Fit the maximum DRC-compliant number of contacts across the width.
        usable_contact_height = (
            self.width - 2.0 * self.POLY_ENC_CONTACT
        )
        contact_count = max(1, int(math.floor(
            (usable_contact_height + self.CONTACT_SPACE)
            / self.CONTACT_PITCH
        )))

        contact_array_height = (
            contact_count * self.CONTACT_SIZE
            + (contact_count - 1) * self.CONTACT_SPACE
        )
        contact_y0 = 0.5 * (self.width - contact_array_height)

        left_contact_x1 = self.POLY_ENC_CONTACT
        right_contact_x1 = poly_x2 - self.POLY_ENC_CONTACT - self.CONTACT_SIZE

        for row in range(contact_count):
            cy1 = contact_y0 + row * self.CONTACT_PITCH
            cy2 = cy1 + self.CONTACT_SIZE

            insert_box(
                contact_layer,
                left_contact_x1, cy1,
                left_contact_x1 + self.CONTACT_SIZE, cy2
            )
            insert_box(
                contact_layer,
                right_contact_x1, cy1,
                right_contact_x1 + self.CONTACT_SIZE, cy2
            )

        # 6. Independent M1 landing pads form the two resistor terminals.
        insert_box(
            metal1_layer,
            left_contact_x1 - self.M1_ENC_CONTACT,
            contact_y0 - self.M1_ENC_CONTACT,
            left_contact_x1 + self.CONTACT_SIZE + self.M1_ENC_CONTACT,
            contact_y0 + contact_array_height + self.M1_ENC_CONTACT
        )
        insert_box(
            metal1_layer,
            right_contact_x1 - self.M1_ENC_CONTACT,
            contact_y0 - self.M1_ENC_CONTACT,
            right_contact_x1 + self.CONTACT_SIZE + self.M1_ENC_CONTACT,
            contact_y0 + contact_array_height + self.M1_ENC_CONTACT
        )