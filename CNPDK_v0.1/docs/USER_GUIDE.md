# CNPDK User Guide / CNPDK 使用手册

## 中文版本

### 1. 手册说明

本手册介绍如何使用CNPDK完成以下工作：

- 新建CNPDK版图；
- 放置和修改PCell；
- 使用Via、Contact和金属层连接器件；
- 添加LVS能够识别的网络标签；
- 运行DRC和LVS；
- 使用参数扫描、环境检查和回归测试工具；
- 查看器件参数和项目验证结果。

如果CNPDK还没有安装，请先阅读`INSTALLATION.md`。

> CNPDK是个人Mini-PDK，适合学习、流程验证和项目展示，不能直接用于商业芯片制造。

---

### 2. 快速开始

#### 2.1 新建Layout

1. 启动KLayout。
2. 新建一个Layout。
3. 将Technology设置为`CNPDK`。
4. 建议将数据库单位DBU设置为：

   ```text
   0.001 µm
   ```

5. 创建一个顶层Cell，例如：

   ```text
   TOP
   ```

6. 尽早保存版图，建议使用GDS格式。

LVS规则需要知道当前GDS的保存目录，因此不要一直使用未保存的临时Layout。

#### 2.2 打开CNPDK Library

在Libraries面板中选择：

```text
CNPDK
```

正常情况下可以看到：

- NMOS
- PMOS
- 电阻P_PO_SAB
- 电容MIM
- 金属通孔
- 接触孔
- GuardRing

如果没有看到Library，请先运行`pymacros/library.py`，然后重新检查。

---

### 3. 放置和修改PCell

#### 3.1 放置器件

1. 在Libraries面板中选择器件。
2. 将器件放入当前顶层Cell。
3. 选中器件实例。
4. 打开实例属性窗口。
5. 修改参数并确认。

PCell会根据参数重新生成几何图形。一般不需要进入PCell内部手动画图。

#### 3.2 不要随意Flatten

在普通版图编辑中，可以保留PCell实例结构。这样便于以后修改W、L、NF等参数。

以下情况才考虑Flatten：

- 导出给不支持PCell的工具；
- 制作最终静态GDS副本；
- 调试某个几何问题。

Flatten之后，器件会变成普通图形，不能再通过PCell参数窗口修改。

---

### 4. MOS器件的基本使用

#### 4.1 NMOS

NMOS主要由以下图层组成：

- Active：有源区；
- Poly：栅极；
- N+ Implant：形成N型源漏区；
- Contact：连接源漏扩散区；
- M1：源漏金属引出。

NMOS本体位于P型衬底中。CNPDK第一版不在NMOS PCell内部生成body tap，建议在器件外放置P+ GuardRing，并通过M1把GuardRing连接到VSS。

#### 4.2 PMOS

PMOS结构与NMOS相似，但它位于N-Well中，并使用P+ Implant形成源漏区。

CNPDK第一版不在PMOS PCell内部生成N-Well tap，建议在PMOS外放置N+ N-Well GuardRing，并通过M1连接到VDD。

#### 4.3 Fingers的含义

`NF`表示沟道数量。

例如：

```text
W = 4 µm
NF = 4
```

表示总宽度为4 µm，由4个并排沟道组成。CNPDK中的`W`是总宽度，不是每根Finger的宽度。

当Gate Contact Position选择`None`时，各根栅极不会自动连在一起，使用者可以按电路需要自行布线。

当选择`Top`或`Bottom`时，PCell会在上方或下方生成Poly Bus、Contact阵列和M1栅极引出。

---

### 5. GuardRing的使用

GuardRing有两种类型：

| 类型 | 主要用途 | 常见连接 |
|---|---|---|
| N+ N-Well | 为PMOS的N-Well提供阱接触 | VDD |
| P+ P-Substrate | 为NMOS周围的P型衬底提供接触 | VSS |

使用步骤：

1. 放置GuardRing。
2. 选择类型。
3. 设置内部宽度和内部高度。
4. 调整位置，使需要保护的器件位于环内。
5. 使用M1将环上的接触金属连接到目标电位。

GuardRing的内部尺寸是中间空白区域的尺寸，不是整个环的外部尺寸。

不要让无关Poly穿过GuardRing的Active。只有Poly与Active交叠时，LVS才可能把该区域解释为MOS沟道。

---

### 6. 电阻与电容

#### 6.1 P+ Poly SAB电阻

CNPDK提供一个简单的P+ Poly SAB电阻。

它使用多晶硅作为电阻主体，SAB层阻止电阻区域形成低阻硅化物，两端通过Contact和M1引出。

估算公式：

```text
R = Rsheet × L / W
```

其中：

- `Rsheet`：方块电阻；
- `L`：电阻长度；
- `W`：电阻宽度。

默认方块电阻为：

```text
311 Ω/□
```

该数值用于项目计算和流程验证，不代表晶圆厂保证的实测值。

#### 6.2 MIM电容

CNPDK的MIM电容使用：

- M2作为下极板；
- FuseTop作为上极板；
- Via2把上极板连接到M3；
- Capacitor Mark用于器件识别。

估算公式：

```text
C = ca × L × W
```

默认单位面积电容：

```text
ca = 0.002 pF/µm²
```

下极板可以直接从M2引出。上极板通过Via2连接到M3。

不要在MIM上方穿过无关的M2或M3走线，以免产生DRC错误或错误连接。

---

### 7. Contact、Via和金属连接

#### 7.1 Contact

CNPDK提供：

- Active–M1 Contact；
- Poly–M1 Contact。

Contact只连接指定的底层和M1。它不会因为几何上经过其他图层，就自动把所有图层连接在一起。

#### 7.2 Via

CNPDK提供：

- M1–M2 Via；
- M2–M3 Via。

Via必须同时与正确的上下金属层重叠，才能形成电连接。

#### 7.3 推荐布线方式

对于简单电路，可以采用：

- M1：器件附近和局部连接；
- M2：较长的横向连接；
- M3：较长的纵向连接；
- Via1/Via2：连接不同金属层。

这只是便于管理的布线习惯，不是强制要求。最终仍需以DRC和LVS结果为准。

---

### 8. 添加网络标签

LVS通过标签名称识别顶层端口和网络。

常用标签层：

| 金属 | 标签层 |
|---|---:|
| M1 | 34/10 |
| M2 | 36/10 |
| M3 | 42/10 |

添加标签时要注意：

1. 标签必须使用对应金属的Label层；
2. 标签放置点必须落在对应金属内部；
3. 同一网络的名称必须完全一致；
4. 注意大小写，例如`VDD`和`vdd`可能被当成不同名称；
5. 标签显示尺寸通常不影响LVS，真正重要的是图层、名称和放置位置。

常见顶层端口：

```text
IN
OUT
VDD
VSS
```

不要直接在Metal 3绘图层`42/0`上创建文字代替M3 Label。M3网络标签应使用`42/10`。

---

### 9. 运行DRC

DRC用于检查几何图形是否满足设计规则，例如：

- 最小宽度；
- 最小间距；
- Contact或Via尺寸；
- 金属包围；
- Implant包围；
- MIM和电阻识别层关系。

基本步骤：

1. 保存当前GDS。
2. 打开CNPDK整合DRC规则。
3. 确认当前顶层Cell正确。
4. 运行规则。
5. 在Marker Database Browser中查看错误。
6. 双击错误，定位到对应版图位置。
7. 修改后重新运行，直到错误数量为0。

DRC报告为0只表示几何规则通过，不代表电路连接一定正确。连接关系需要使用LVS检查。

具体规则与错误编号请阅读`DRC_REFERENCE.md`。

---

### 10. 运行LVS

LVS用于比较：

```text
版图提取电路  vs.  原理图参考网表
```

基本步骤：

1. 在Virtuoso中完成原理图。
2. 通过auCdl导出CDL网表。
3. 将网表放到GDS所在目录。
4. 运行`v_netlist_k_cir.py`转换宏。
5. 确认生成：

   ```text
   <名称>_reference.cir
   ```

6. 在KLayout中打开并保存需要验证的GDS。
7. 确认当前Cell是顶层Cell。
8. 运行CNPDK整合LVS规则。
9. 在Netlist Database Browser中查看结果。

验证通过时，应同时确认：

- 顶层电路匹配；
- Pins匹配；
- Nets匹配；
- Devices匹配；
- W、L、R、C等参数匹配。

不能只因为脚本没有弹出报错，就认为LVS已经通过。

具体器件识别和网络提取逻辑请阅读`LVS_REFERENCE.md`。

---

### 11. 自动化工具

#### 11.1 环境检查

```powershell
python tools\CNPDK_install_check.py --check
```

用于检查文件结构、Python语法、图层和绝对路径残留。

#### 11.2 PCell参数扫描

在KLayout中新建一个空Layout，确认CNPDK Library已经加载，然后运行：

```text
tools/CNPDK_PCell_Parameter_Sweep.py
```

脚本会生成`CNPDK_PCELL_SWEEP`测试Cell，批量放置不同参数的器件。

说明文字使用`200/0`测试层。该层不是制造层，正式导出版图时应删除或排除。

#### 11.3 自动化回归

```powershell
python tools\CNPDK_regression.py
```

该脚本会检查安装包、重新加载Library、生成固定PCell矩阵、运行DRC，并在存在Golden测试数据时运行LVS。

结果保存在：

```text
tests/regression_output/
```

#### 11.4 自动布局布线

`CNPDK_AutoLayout_v1_0.py`可以根据简单网表进行实验性的器件放置和曼哈顿布线。

它适合演示小型电路自动化，不适合代替：

- 工业级APR工具；
- 人工模拟版图优化；
- 最终DRC/LVS签核。

---

### 12. PCell参数参考

#### 12.1 NMOS和PMOS

| 参数 | 含义 | 说明 |
|---|---|---|
| Length / L | 沟道长度 | 影响沟道几何长度 |
| Total Width / W | 总沟道宽度 | 多指结构中所有Finger的总宽度 |
| Fingers / NF | 沟道数量 | 将总宽度分成多个并排沟道 |
| Gate Contact Position | 栅极引出位置 | None、Top或Bottom |
| Add Labels | 添加器件内部标签 | 主要用于观察和调试 |

#### 12.2 P+ Poly SAB电阻

| 参数 | 含义 |
|---|---|
| Length | 电阻主体长度 |
| Width | 电阻主体宽度 |
| Sheet Resistance | 方块电阻，默认311 Ω/□ |
| Estimated Resistance | 按Rsheet×L/W得到的估算值 |

#### 12.3 MIM电容

| 参数 | 含义 |
|---|---|
| Length | 极板长度 |
| Width | 极板宽度 |
| Capacitance Density / ca | 单位面积电容，默认0.002 pF/µm² |
| Estimated Capacitance | 按ca×L×W得到的估算值 |

#### 12.4 Via和Contact

| 参数 | 含义 |
|---|---|
| Type | 选择连接层 |
| Rows | 阵列行数 |
| Columns | 阵列列数 |
| Cut | 孔尺寸 |
| Spacing | 孔间距 |
| Enclosure | 上下材料对孔的包围 |

#### 12.5 GuardRing

| 参数 | 含义 |
|---|---|
| Ring Type | N+ N-Well或P+ P-Substrate |
| Inner Width | 环内部空白区域宽度 |
| Inner Height | 环内部空白区域高度 |

---

### 13. 已完成的验证

| 测试内容 | DRC | LVS |
|---|---|---|
| NMOS | PASS | PASS |
| PMOS | PASS | PASS |
| P+ Poly SAB电阻 | PASS | PASS |
| MIM电容 | PASS | PASS |
| CMOS反相器 | PASS | PASS |
| RC负载CMOS反相器 | 0个错误 | MATCH |
| 断开OUT负向测试 | — | 正确检出网络不匹配 |
| 修改MOS宽度负向测试 | — | 正确检出参数不匹配 |

PCell参数扫描还覆盖了多组W、L、NF、Gate位置、阵列规模以及电阻、电容尺寸，用于检查参数边界和防止后续修改破坏原有功能。

这些结果证明CNPDK的基础PCell、DRC和LVS流程能够形成完整闭环，但不代表已经达到晶圆厂签核标准。

---

### 14. 使用建议

- 每次修改PCell后，先运行参数扫描和DRC；
- 修改器件识别或连接规则后，重新运行所有LVS Golden用例；
- 为每个重要错误保留一个可重复的测试用例；
- 不要把测试文字层写入正式制造数据；
- 发布新版本前运行`CNPDK_regression.py`；
- 备份能够通过DRC/LVS的GDS和参考网表。

---

## English Version

### 1. About This Guide

This guide explains how to:

- create a CNPDK layout;
- place and edit PCells;
- connect devices with metals, contacts, and vias;
- add net labels for LVS;
- run DRC and LVS;
- use the parameter-sweep, environment-check, and regression tools;
- understand the PCell parameters and verified test results.

Read `INSTALLATION.md` first if CNPDK has not yet been installed.

> CNPDK is a personal Mini-PDK for learning, workflow verification, and portfolio demonstration. It must not be used directly for commercial chip manufacturing.

---

### 2. Quick Start

1. Start KLayout and create a new layout.
2. Select `CNPDK` as the Technology.
3. Use a DBU of `0.001 µm`.
4. Create a top cell, such as `TOP`.
5. Save the layout as a GDS file.
6. Open the Libraries panel and select the `CNPDK` Library.

The Library should contain NMOS, PMOS, P+ Poly SAB resistor, MIM capacitor, Via, Contact, and GuardRing PCells.

Saving the layout early is important because the LVS flow uses the GDS directory to locate its reference netlist.

---

### 3. Placing and Editing PCells

Select a device from the Libraries panel and place it in the active top cell. Open the instance properties to change its parameters.

The geometry is regenerated automatically. In normal use, there is no need to manually edit shapes inside a PCell.

Avoid flattening PCells unless a static GDS copy is required. After flattening, parameters such as W, L, and NF can no longer be edited through the PCell interface.

---

### 4. MOS Devices

The NMOS uses Active, Poly, N+ Implant, Contact, and M1 layers. It is placed in the common P-type substrate. Use a P+ P-Substrate GuardRing connected to VSS to provide a substrate contact.

The PMOS is placed inside an N-Well and uses P+ source/drain implants. Use an N+ N-Well GuardRing connected to VDD to provide the well contact.

`NF` is the number of channel fingers. `W` is the total channel width across all fingers.

- `Gate Contact Position = None`: the fingers are not automatically connected.
- `Top`: a Poly bus, Contact array, and M1 gate connection are generated above the device.
- `Bottom`: the same structure is generated below the device.

---

### 5. GuardRing

| Type | Main Purpose | Typical Connection |
|---|---|---|
| N+ N-Well | N-Well contact around PMOS | VDD |
| P+ P-Substrate | Substrate contact around NMOS | VSS |

Set the inner width and height, place the protected device inside the opening, and connect the M1 ring to the required potential.

The entered dimensions describe the empty area inside the ring, not the total outside size.

---

### 6. Resistor and Capacitor

The P+ Poly SAB resistor uses Poly as its resistive body. The SAB layer prevents low-resistance silicidation in the resistor region.

```text
R = Rsheet × L / W
```

The default sheet resistance is `311 Ω/□`. It is a project value for calculation and workflow verification, not a foundry-guaranteed measurement.

The MIM capacitor uses M2 as the bottom plate and FuseTop as the top plate. Via2 connects the top plate to M3.

```text
C = ca × L × W
```

The default capacitance density is `0.002 pF/µm²`.

Avoid routing unrelated M2 or M3 wires across the MIM device.

---

### 7. Contacts, Vias, and Routing

CNPDK supports:

- Active–M1 Contact;
- Poly–M1 Contact;
- M1–M2 Via;
- M2–M3 Via.

A cut connects only the intended lower and upper layers. It does not automatically connect every overlapping layer.

For simple layouts, M1 may be used near devices, M2 for longer horizontal routes, and M3 for longer vertical routes. This is a routing convention rather than a mandatory rule.

---

### 8. Net Labels

| Metal | Label Layer |
|---|---:|
| M1 | 34/10 |
| M2 | 36/10 |
| M3 | 42/10 |

The label origin must lie inside the corresponding metal shape. Net names are case-sensitive in practice, so use consistent names such as:

```text
IN
OUT
VDD
VSS
```

Do not use the M3 drawing layer `42/0` as a substitute for the M3 label layer. M3 labels must use `42/10`.

---

### 9. Running DRC

1. Save the GDS.
2. Open the integrated CNPDK DRC deck.
3. Confirm that the correct top cell is active.
4. Run the deck.
5. Inspect errors in Marker Database Browser.
6. Correct the layout and rerun until the marker count is zero.

DRC checks geometry. A zero-error DRC result does not prove that the circuit is connected correctly.

See `DRC_REFERENCE.md` for the detailed rules and error numbering.

---

### 10. Running LVS

1. Complete the schematic in Virtuoso.
2. Export a CDL netlist through auCdl.
3. Place the netlist in the GDS directory.
4. Run `v_netlist_k_cir.py`.
5. Confirm that a `*_reference.cir` file was generated.
6. Open and save the target GDS in KLayout.
7. Select the intended top cell.
8. Run the integrated CNPDK LVS deck.
9. Inspect the result in Netlist Database Browser.

A valid LVS result requires matching top circuits, pins, nets, devices, and device parameters. The absence of a script error alone does not mean that LVS passed.

See `LVS_REFERENCE.md` for device recognition and extraction details.

---

### 11. Automation Tools

Environment check:

```powershell
python tools\CNPDK_install_check.py --check
```

PCell parameter sweep:

```text
tools/CNPDK_PCell_Parameter_Sweep.py
```

The sweep creates a `CNPDK_PCELL_SWEEP` cell. Layer `200/0` is used only for QA text and should be excluded from manufacturing data.

Automated regression:

```powershell
python tools\CNPDK_regression.py
```

Reports are written to:

```text
tests/regression_output/
```

`CNPDK_AutoLayout_v1_0.py` is an experimental placement and Manhattan-routing tool for small examples. It does not replace industrial APR, manual analog-layout optimization, or final physical verification.

---

### 12. PCell Parameter Reference

#### NMOS and PMOS

| Parameter | Meaning |
|---|---|
| Length / L | Channel length |
| Total Width / W | Total width across all fingers |
| Fingers / NF | Number of channel fingers |
| Gate Contact Position | None, Top, or Bottom |
| Add Labels | Adds internal labels for inspection |

#### P+ Poly SAB Resistor

| Parameter | Meaning |
|---|---|
| Length | Resistor-body length |
| Width | Resistor-body width |
| Sheet Resistance | Default: 311 Ω/□ |
| Estimated Resistance | Calculated from Rsheet × L / W |

#### MIM Capacitor

| Parameter | Meaning |
|---|---|
| Length | Plate length |
| Width | Plate width |
| Capacitance Density / ca | Default: 0.002 pF/µm² |
| Estimated Capacitance | Calculated from ca × L × W |

#### Via and Contact

| Parameter | Meaning |
|---|---|
| Type | Selects the connected layers |
| Rows / Columns | Array dimensions |
| Cut | Cut size |
| Spacing | Cut-to-cut spacing |
| Enclosure | Lower- and upper-layer enclosure |

#### GuardRing

| Parameter | Meaning |
|---|---|
| Ring Type | N+ N-Well or P+ P-Substrate |
| Inner Width | Width of the opening |
| Inner Height | Height of the opening |

---

### 13. Verified Results

| Test | DRC | LVS |
|---|---|---|
| NMOS | PASS | PASS |
| PMOS | PASS | PASS |
| P+ Poly SAB resistor | PASS | PASS |
| MIM capacitor | PASS | PASS |
| CMOS inverter | PASS | PASS |
| RC-loaded CMOS inverter | Zero errors | MATCH |
| Open-OUT negative test | — | Net mismatch detected |
| Modified-MOS-width negative test | — | Parameter mismatch detected |

The PCell sweep covers multiple W, L, NF, gate positions, array sizes, and resistor/capacitor dimensions. These results demonstrate a complete basic PCell–DRC–LVS workflow, but they do not represent foundry sign-off qualification.

---

### 14. Recommended Practice

- Run the parameter sweep and DRC after changing a PCell.
- Rerun all Golden LVS cases after changing extraction or connectivity rules.
- Keep a reproducible test case for every important bug.
- Exclude QA text layers from final manufacturing data.
- Run `CNPDK_regression.py` before releasing a new version.
- Back up GDS and reference-netlist pairs that have passed DRC and LVS.

