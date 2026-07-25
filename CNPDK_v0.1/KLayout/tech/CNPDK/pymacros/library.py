# $autorun
# -*- coding: utf-8 -*-

import os
import sys
import pya


# ================================================================
# 1. 获取library.py所在目录
# ================================================================

current_directory = os.path.dirname(
    os.path.abspath(__file__)
)


# ================================================================
# 2. 将当前目录加入Python模块搜索路径
# ================================================================

if current_directory not in sys.path:
    sys.path.insert(
        0,
        current_directory
    )


# ================================================================
# 3. 导入各个PCell类
# ================================================================

from via_array import ViaArrayPCell
from contact_array import ContactArrayPCell
from nmos import NMOSPCell
from pmos import PMOSPCell
from guardring import GuardRingPCell
from rpposab import PPlusPolySABResistorPCell
from mim import MIMCapacitorPCell

# ================================================================
# 4. 创建并注册CNPDK Library
# ================================================================

class CNPDKLibrary(pya.Library):
    """
    CNPDK统一Library注册入口。

    当前包含：
    - VIA_ARRAY
    - CONTACT_ARRAY
    - NMOS
    """

    def __init__(self):
        super(CNPDKLibrary, self).__init__()

        self.description = (
            "CNPDK 中英双语个人Mini-PDK"
        )

        # --------------------------------------------------------
        # 注册Via阵列PCell
        # --------------------------------------------------------

        self.layout().register_pcell(
            "金属通孔",
            ViaArrayPCell()
        )

        # --------------------------------------------------------
        # 注册Contact阵列PCell
        # --------------------------------------------------------

        self.layout().register_pcell(
            "接触孔",
            ContactArrayPCell()
        )

        # --------------------------------------------------------
        # 注册NMOS PCell
        # --------------------------------------------------------

        self.layout().register_pcell(
            "NMOS",
            NMOSPCell()
        )

        # --------------------------------------------------------
        # 注册Library名称
        # --------------------------------------------------------

        self.register("CNPDK")

        self.layout().register_pcell(
           "PMOS",
           PMOSPCell()
        )
        
        self.layout().register_pcell(
            "GuardRing",
            GuardRingPCell()
        )
        
        self.layout().register_pcell(
           "电阻P_PO_SAB",
           PPlusPolySABResistorPCell()
        )
        
        self.layout().register_pcell(
           "电容MIM",
           MIMCapacitorPCell()
        )
        
        

# ================================================================
# 5. 运行library.py时创建Library
# ================================================================

CNPDKLibrary()