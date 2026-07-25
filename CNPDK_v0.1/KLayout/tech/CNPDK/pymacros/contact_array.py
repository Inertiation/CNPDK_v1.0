import pya


class ContactArrayPCell(pya.PCellDeclarationHelper):
    """
    CNPDK通用Contact阵列PCell

    支持：
    1. Active/COMP - Contact - Metal1
    2. Poly2 - Contact - Metal1
    """

    def __init__(self):
        super(ContactArrayPCell, self).__init__()

        # ========================================================
        # Contact类型选择
        # ========================================================

        contact_type_parameter = self.param(
            "contact_type",
            self.TypeList,
            "接触类型 / Contact Type",
            default=0
        )

        contact_type_parameter.add_choice(
            "有源区-M1 / Active-Metal1",
            0
        )

        contact_type_parameter.add_choice(
            "多晶硅-M1 / Poly-Metal1",
            1
        )

        # ========================================================
        # 几何参数，单位为μm
        # ========================================================

        self.param(
            "cut",
            self.TypeDouble,
            "接触孔尺寸 / Contact Size (μm)",
            default=0.22
        )

        self.param(
            "spacing",
            self.TypeDouble,
            "接触孔间距 / Contact Spacing (μm)",
            default=0.25
        )

        self.param(
            "rows",
            self.TypeInt,
            "阵列行数 / Rows",
            default=1
        )

        self.param(
            "columns",
            self.TypeInt,
            "阵列列数 / Columns",
            default=1
        )

        self.param(
            "bottom_enclosure",
            self.TypeDouble,
            "下层包围量 / Bottom Enclosure (μm)",
            default=0.07
        )

        self.param(
            "metal1_enclosure",
            self.TypeDouble,
            "M1包围量 / Metal1 Enclosure (μm)",
            default=0.06
        )

    def display_text_impl(self):
        """
        显示PCell实例名称。
        """

        if self.contact_type == 0:
            contact_name = "Active-M1接触"
        else:
            contact_name = "Poly-M1接触"

        return (
            "%s（%d×%d）"
            % (
                contact_name,
                self.columns,
                self.rows
            )
        )

    def coerce_parameters_impl(self):
        """
        检查并修正用户输入参数。
        """

        # GF180MCU Contact采用固定0.22μm尺寸
        self.cut = 0.22

        # 阵列行数和列数至少为1
        if self.rows < 1:
            self.rows = 1

        if self.columns < 1:
            self.columns = 1

        # 普通Contact阵列最小间距
        minimum_spacing = 0.25

        # 4×4及以上阵列最小间距
        if self.rows >= 4 and self.columns >= 4:
            minimum_spacing = 0.28

        if self.spacing < minimum_spacing:
            self.spacing = minimum_spacing

        # Active和Poly对Contact至少包围0.07μm
        if self.bottom_enclosure < 0.07:
            self.bottom_enclosure = 0.07

        # 当前教学版本统一采用0.06μm M1包围
        if self.metal1_enclosure < 0.06:
            self.metal1_enclosure = 0.06

        # 防止出现不支持的Contact类型
        if self.contact_type not in (0, 1):
            self.contact_type = 0

    def produce_impl(self):
        """
        生成下层图形、Contact阵列和Metal1。
        """

        # ========================================================
        # 根据UI选择确定下层图层
        # ========================================================

        if self.contact_type == 0:

            # Active/COMP - Contact - Metal1
            bottom_layer_info = pya.LayerInfo(
                22,
                0,
                "有源区 / Active"
            )

        else:

            # Poly2 - Contact - Metal1
            bottom_layer_info = pya.LayerInfo(
                30,
                0,
                "多晶硅 / Poly"
            )

        contact_layer_info = pya.LayerInfo(
            33,
            0,
            "接触孔 / Contact"
        )

        metal1_layer_info = pya.LayerInfo(
            34,
            0,
            "第一层金属 / Metal 1"
        )

        # 转换为当前Layout中的图层索引
        bottom_layer_index = self.layout.layer(
            bottom_layer_info
        )

        contact_layer_index = self.layout.layer(
            contact_layer_info
        )

        metal1_layer_index = self.layout.layer(
            metal1_layer_info
        )

        # ========================================================
        # 单位转换
        # ========================================================

        dbu = self.layout.dbu

        def to_dbu(value_um):
            """
            将μm转换为KLayout数据库整数单位。
            """

            return int(round(value_um / dbu))

        cut = to_dbu(self.cut)
        spacing = to_dbu(self.spacing)

        bottom_enclosure = to_dbu(
            self.bottom_enclosure
        )

        metal1_enclosure = to_dbu(
            self.metal1_enclosure
        )

        rows = self.rows
        columns = self.columns

        # ========================================================
        # Contact阵列尺寸计算
        # ========================================================

        pitch = cut + spacing

        array_width = (
            columns * cut
            + (columns - 1) * spacing
        )

        array_height = (
            rows * cut
            + (rows - 1) * spacing
        )

        # 让阵列中心位于PCell原点
        x_start = -(array_width // 2)
        y_start = -(array_height // 2)

        # ========================================================
        # 生成Contact阵列
        # ========================================================

        for row in range(rows):
            for column in range(columns):

                x1 = x_start + column * pitch
                y1 = y_start + row * pitch

                x2 = x1 + cut
                y2 = y1 + cut

                contact_box = pya.Box(
                    x1,
                    y1,
                    x2,
                    y2
                )

                self.cell.shapes(
                    contact_layer_index
                ).insert(contact_box)

        # ========================================================
        # 生成下层Active或Poly
        # ========================================================

        bottom_box = pya.Box(
            x_start - bottom_enclosure,
            y_start - bottom_enclosure,
            x_start + array_width + bottom_enclosure,
            y_start + array_height + bottom_enclosure
        )

        self.cell.shapes(
            bottom_layer_index
        ).insert(bottom_box)

        # ========================================================
        # 生成Metal1
        # ========================================================

        metal1_box = pya.Box(
            x_start - metal1_enclosure,
            y_start - metal1_enclosure,
            x_start + array_width + metal1_enclosure,
            y_start + array_height + metal1_enclosure
        )

        self.cell.shapes(
            metal1_layer_index
        ).insert(metal1_box)