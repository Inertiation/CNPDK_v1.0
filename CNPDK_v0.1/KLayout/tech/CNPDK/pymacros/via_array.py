import pya


class ViaArrayPCell(pya.PCellDeclarationHelper):
    """
    CNPDK通用金属通孔阵列PCell

    支持：
    1. Via1：Metal1 - Via1 - Metal2
    2. Via2：Metal2 - Via2 - Metal3
    """

    def __init__(self):
        super(ViaArrayPCell, self).__init__()

        # ========================================================
        # 通孔类型选择
        # ========================================================

        via_type_parameter = self.param(
            "via_type",
            self.TypeList,
            "通孔类型 / Via Type"
        )

        via_type_parameter.add_choice(
            "M1-M2通孔 / Via1",
            1
        )

        via_type_parameter.add_choice(
            "M2-M3通孔 / Via2",
            2
        )

        # ========================================================
        # 几何参数，单位为μm
        # ========================================================

        self.param(
            "cut",
            self.TypeDouble,
            "通孔尺寸 / Via Size (μm)",
            default=0.26
        )

        self.param(
            "spacing",
            self.TypeDouble,
            "通孔间距 / Via Spacing (μm)",
            default=0.26
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
            "下层金属包围 / Bottom Enclosure (μm)",
            default=0.06
        )

        self.param(
            "top_enclosure",
            self.TypeDouble,
            "上层金属包围 / Top Enclosure (μm)",
            default=0.06
        )

    def display_text_impl(self):
        """
        在KLayout版图层级中显示PCell实例名称。
        """

        if self.via_type == 1:
            via_name = "Via1：M1-M2"
        else:
            via_name = "Via2：M2-M3"

        return (
            "%s 通孔阵列（%d×%d）"
            % (
                via_name,
                self.columns,
                self.rows
            )
        )

    def coerce_parameters_impl(self):
        """
        检查并修正用户输入的非法参数。
        """

        # Via尺寸不得小于0.26μm
        if self.cut < 0.26:
            self.cut = 0.26

        # 阵列行数、列数至少为1
        if self.rows < 1:
            self.rows = 1

        if self.columns < 1:
            self.columns = 1

        # 普通Via阵列最小间距
        minimum_spacing = 0.26

        # 4×4及以上阵列最小间距使用0.36μm
        if self.rows >= 4 and self.columns >= 4:
            minimum_spacing = 0.36

        if self.spacing < minimum_spacing:
            self.spacing = minimum_spacing

        # 当前教学版本统一采用0.06μm金属包围
        if self.bottom_enclosure < 0.06:
            self.bottom_enclosure = 0.06

        if self.top_enclosure < 0.06:
            self.top_enclosure = 0.06

        # 防止出现不支持的通孔类型
        if self.via_type not in (1, 2):
            self.via_type = 1

    def produce_impl(self):
        """
        生成上下层金属和Via阵列。
        """

        # ========================================================
        # 根据UI选择自动确定图层
        # ========================================================

        if self.via_type == 1:

            # M1 - Via1 - M2
            bottom_layer_info = pya.LayerInfo(
                34,
                0,
                "第一层金属 / Metal 1"
            )

            via_layer_info = pya.LayerInfo(
                35,
                0,
                "第一层通孔 / Via 1"
            )

            top_layer_info = pya.LayerInfo(
                36,
                0,
                "第二层金属 / Metal 2"
            )

        else:

            # M2 - Via2 - M3
            bottom_layer_info = pya.LayerInfo(
                36,
                0,
                "第二层金属 / Metal 2"
            )

            via_layer_info = pya.LayerInfo(
                38,
                0,
                "第二层通孔 / Via 2"
            )

            top_layer_info = pya.LayerInfo(
                42,
                0,
                "第三层金属 / Metal 3"
            )

        # 将LayerInfo转换为当前Layout中的图层索引
        bottom_layer_index = self.layout.layer(
            bottom_layer_info
        )

        via_layer_index = self.layout.layer(
            via_layer_info
        )

        top_layer_index = self.layout.layer(
            top_layer_info
        )

        # ========================================================
        # 单位转换
        # ========================================================

        dbu = self.layout.dbu

        def to_dbu(value_um):
            """
            把μm转换为KLayout数据库整数单位。
            """

            return int(round(value_um / dbu))

        cut = to_dbu(self.cut)
        spacing = to_dbu(self.spacing)

        bottom_enclosure = to_dbu(
            self.bottom_enclosure
        )

        top_enclosure = to_dbu(
            self.top_enclosure
        )

        rows = self.rows
        columns = self.columns

        # ========================================================
        # 计算Via阵列尺寸
        # ========================================================

        # 相邻Via起点之间的距离
        pitch = cut + spacing

        # 整个Via阵列的宽度
        array_width = (
            columns * cut
            + (columns - 1) * spacing
        )

        # 整个Via阵列的高度
        array_height = (
            rows * cut
            + (rows - 1) * spacing
        )

        # 将阵列中心放置在PCell原点
        x_start = -(array_width // 2)
        y_start = -(array_height // 2)

        # ========================================================
        # 生成Via阵列
        # ========================================================

        for row in range(rows):
            for column in range(columns):

                x1 = x_start + column * pitch
                y1 = y_start + row * pitch

                x2 = x1 + cut
                y2 = y1 + cut

                via_box = pya.Box(
                    x1,
                    y1,
                    x2,
                    y2
                )

                self.cell.shapes(
                    via_layer_index
                ).insert(via_box)

        # ========================================================
        # 生成下层金属
        # ========================================================

        bottom_metal_box = pya.Box(
            x_start - bottom_enclosure,
            y_start - bottom_enclosure,
            x_start + array_width + bottom_enclosure,
            y_start + array_height + bottom_enclosure
        )

        self.cell.shapes(
            bottom_layer_index
        ).insert(bottom_metal_box)

        # ========================================================
        # 生成上层金属
        # ========================================================

        top_metal_box = pya.Box(
            x_start - top_enclosure,
            y_start - top_enclosure,
            x_start + array_width + top_enclosure,
            y_start + array_height + top_enclosure
        )

        self.cell.shapes(
            top_layer_index
        ).insert(top_metal_box)


