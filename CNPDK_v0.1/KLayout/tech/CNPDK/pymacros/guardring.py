# -*- coding: utf-8 -*-
"""CNPDK rectangular Guard Ring PCell.

UI parameters:
    1. Guard Ring type
    2. Inner width
    3. Inner height

N+ N-Well Ring:
    solid N-Well + Active ring + N+ ring + Contact arrays + M1 ring

P+ Substrate Ring:
    Active ring + P+ ring + Contact arrays + M1 ring
"""

import math
import pya


class GuardRingPCell(pya.PCellDeclarationHelper):
    # CNPDK GDS layers
    L_NWELL = pya.LayerInfo(21, 0)
    L_ACTIVE = pya.LayerInfo(22, 0)
    L_PPLUS = pya.LayerInfo(31, 0)
    L_NPLUS = pya.LayerInfo(32, 0)
    L_CONTACT = pya.LayerInfo(33, 0)
    L_METAL1 = pya.LayerInfo(34, 0)

    # Fixed simplified GF180MCU-derived dimensions, in um
    CONTACT_SIZE = 0.22
    CONTACT_SPACE = 0.25
    CONTACT_PITCH = CONTACT_SIZE + CONTACT_SPACE

    ACTIVE_ENC_CONTACT = 0.07
    IMPLANT_ENC_ACTIVE = 0.16
    NWELL_ENC_ACTIVE = 0.43
    M1_ENC_CONTACT = 0.06

    # One contact row fits inside a 0.52 um Active ring with 0.15 um
    # Active enclosure on both sides.
    RING_WIDTH = 0.52

    MIN_INNER_WIDTH = 1.0
    MIN_INNER_HEIGHT = 1.0

    TYPE_NWELL_NPLUS = 0
    TYPE_PSUB_PPLUS = 1

    def __init__(self):
        super(GuardRingPCell, self).__init__()

        ring_type = self.param(
            "ring_type",
            self.TypeList,
            "保护环类型 / Guard Ring Type",
            default=self.TYPE_NWELL_NPLUS
        )
        ring_type.add_choice(
            "N+ N阱保护环（PMOS） / N+ N-Well Ring (PMOS)",
            self.TYPE_NWELL_NPLUS
        )
        ring_type.add_choice(
            "P+ 衬底保护环（NMOS） / P+ Substrate Ring (NMOS)",
            self.TYPE_PSUB_PPLUS
        )

        self.param(
            "inner_width",
            self.TypeDouble,
            "内部宽度 / Inner Width (um)",
            default=5.0
        )
        self.param(
            "inner_height",
            self.TypeDouble,
            "内部高度 / Inner Height (um)",
            default=5.0
        )

    def display_text_impl(self):
        type_name = (
            "NPLUS_NWELL" if self.ring_type == self.TYPE_NWELL_NPLUS
            else "PPLUS_PSUB"
        )
        return "CNPDK_GUARD_RING_%s_IW%.3f_IH%.3f" % (
            type_name,
            self.inner_width,
            self.inner_height
        )

    def coerce_parameters_impl(self):
        self.inner_width = max(
            float(self.inner_width), self.MIN_INNER_WIDTH
        )
        self.inner_height = max(
            float(self.inner_height), self.MIN_INNER_HEIGHT
        )

        if self.ring_type not in (
                self.TYPE_NWELL_NPLUS, self.TYPE_PSUB_PPLUS):
            self.ring_type = self.TYPE_NWELL_NPLUS

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

        def insert_ring(layer_index, outer_box, inner_box):
            ring_region = pya.Region(make_box(*outer_box))
            ring_region -= pya.Region(make_box(*inner_box))
            self.cell.shapes(layer_index).insert(ring_region)

        nwell_layer = self.layout.layer(self.L_NWELL)
        active_layer = self.layout.layer(self.L_ACTIVE)
        pplus_layer = self.layout.layer(self.L_PPLUS)
        nplus_layer = self.layout.layer(self.L_NPLUS)
        contact_layer = self.layout.layer(self.L_CONTACT)
        metal1_layer = self.layout.layer(self.L_METAL1)

        # The origin is at the center of the Guard Ring.
        inner_x1 = -0.5 * self.inner_width
        inner_y1 = -0.5 * self.inner_height
        inner_x2 = 0.5 * self.inner_width
        inner_y2 = 0.5 * self.inner_height

        active_outer_x1 = inner_x1 - self.RING_WIDTH
        active_outer_y1 = inner_y1 - self.RING_WIDTH
        active_outer_x2 = inner_x2 + self.RING_WIDTH
        active_outer_y2 = inner_y2 + self.RING_WIDTH

        active_outer = (
            active_outer_x1, active_outer_y1,
            active_outer_x2, active_outer_y2
        )
        active_inner = (inner_x1, inner_y1, inner_x2, inner_y2)

        # 1. Active is a hollow rectangular ring.
        insert_ring(active_layer, active_outer, active_inner)

        # 2. Implant encloses both the outer and inner edges of Active.
        implant_outer = (
            active_outer_x1 - self.IMPLANT_ENC_ACTIVE,
            active_outer_y1 - self.IMPLANT_ENC_ACTIVE,
            active_outer_x2 + self.IMPLANT_ENC_ACTIVE,
            active_outer_y2 + self.IMPLANT_ENC_ACTIVE
        )
        implant_inner = (
            inner_x1 + self.IMPLANT_ENC_ACTIVE,
            inner_y1 + self.IMPLANT_ENC_ACTIVE,
            inner_x2 - self.IMPLANT_ENC_ACTIVE,
            inner_y2 - self.IMPLANT_ENC_ACTIVE
        )

        if self.ring_type == self.TYPE_NWELL_NPLUS:
            insert_ring(nplus_layer, implant_outer, implant_inner)

            # N-Well is deliberately SOLID, not hollow.  It fills the Guard
            # Ring interior so that overlapping PMOS N-Wells merge with it.
            insert_box(
                nwell_layer,
                active_outer_x1 - self.NWELL_ENC_ACTIVE,
                active_outer_y1 - self.NWELL_ENC_ACTIVE,
                active_outer_x2 + self.NWELL_ENC_ACTIVE,
                active_outer_y2 + self.NWELL_ENC_ACTIVE
            )
        else:
            insert_ring(pplus_layer, implant_outer, implant_inner)

        # 3. M1 is a hollow ring.  With the contact row centered in the
        # 0.52 um ring, it encloses each contact by 0.15 um (> 0.06 um).
        insert_ring(metal1_layer, active_outer, active_inner)

        # Contact centers lie on the center line of each ring side.
        left_cx = inner_x1 - 0.5 * self.RING_WIDTH
        right_cx = inner_x2 + 0.5 * self.RING_WIDTH
        bottom_cy = inner_y1 - 0.5 * self.RING_WIDTH
        top_cy = inner_y2 + 0.5 * self.RING_WIDTH

        def edge_positions(start, stop):
            """Distribute contacts uniformly between two fixed corner cuts.

            The two endpoints are always present.  The number of intervals is
            the largest integer that still keeps center pitch >= 0.47 um, so
            this places the maximum possible number of cuts without violating
            the 0.25 um minimum cut-to-cut spacing.
            """
            length = stop - start
            intervals = max(1, int(math.floor(
                (length + 1.0e-12) / self.CONTACT_PITCH
            )))
            actual_pitch = length / intervals
            return [
                start + index * actual_pitch
                for index in range(intervals + 1)
            ]

        # The endpoints are the four intersections of the horizontal and
        # vertical ring center lines.  They become four shared corner cuts.
        horizontal_centers = edge_positions(left_cx, right_cx)
        vertical_centers = edge_positions(bottom_cy, top_cy)

        half_contact = 0.5 * self.CONTACT_SIZE

        # Top and bottom arrays include all four corner contacts.
        for cx in horizontal_centers:
            insert_box(
                contact_layer,
                cx - half_contact, top_cy - half_contact,
                cx + half_contact, top_cy + half_contact
            )
            insert_box(
                contact_layer,
                cx - half_contact, bottom_cy - half_contact,
                cx + half_contact, bottom_cy + half_contact
            )

        # Left and right arrays omit their endpoints because those four corner
        # contacts were already inserted by the top and bottom arrays.
        for cy in vertical_centers[1:-1]:
            insert_box(
                contact_layer,
                left_cx - half_contact, cy - half_contact,
                left_cx + half_contact, cy + half_contact
            )
            insert_box(
                contact_layer,
                right_cx - half_contact, cy - half_contact,
                right_cx + half_contact, cy + half_contact
            )