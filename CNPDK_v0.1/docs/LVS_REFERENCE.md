# CNPDK LVS Flow and Extraction Logic / CNPDK LVS流程与提取逻辑

## 中文版本

### 1. LVS是什么

LVS是Layout Versus Schematic的缩写，用于比较：

```text
从版图提取出的电路
        和
原理图导出的参考网表
```

它主要回答：

- 版图中有没有少器件或多器件；
- 导线有没有断路或短路；
- 顶层端口名称是否一致；
- MOS的W、L等参数是否一致；
- 电阻和电容数值是否一致。

DRC检查“画得是否符合几何规则”，LVS检查“画出来的电路是否与原理图相同”。

> CNPDK的LVS用于Mini-PDK学习和项目验证，不是晶圆厂签核流程。

---

### 2. 支持的器件

| 版图器件 | 参考网表模型名 | 主要比较参数 |
|---|---|---|
| NMOS | CNPDK_NMOS | W、L、连接关系 |
| PMOS | CNPDK_PMOS | W、L、连接关系 |
| P+ Poly SAB电阻 | CNPDK_RPPOLY | R及几何等效关系 |
| MIM电容 | CNPDK_MIMCAP | C及连接关系 |

第一版LVS不包含完整二极管、BJT、电感、精确寄生器件或Foundry模型。

---

### 3. LVS文件

整合LVS规则位于：

```text
CNPDK/lvs/
```

建议发布文件名：

```text
CNPDK_complete_LVS.lylvs
```

参考网表由Virtuoso导出，再通过转换宏生成：

```text
<名称>_reference.cir
```

运行后，LVS会在GDS目录生成：

```text
<Layout_Cell>_extracted.cir
<Layout_Cell>_LVS.lvsdb
```

---

### 4. 完整运行流程

#### 4.1 在Virtuoso中准备原理图

1. 使用CN_PDK Library中的Symbol建立原理图。
2. 正确连接NMOS、PMOS、电阻和MIM端口。
3. 添加顶层端口，例如：

   ```text
   IN OUT VDD VSS
   ```

4. 检查CDF中的模型名、端口顺序和参数。
5. 通过auCdl导出CDL网表。

MOS参考网表端口顺序为：

```text
D G S B
```

#### 4.2 转换参考网表

1. 将Virtuoso导出的netlist放到GDS所在目录。
2. 在KLayout中运行：

   ```text
   tools/v_netlist_k_cir.py
   ```

3. 确认生成`*_reference.cir`。
4. 打开文件，确认存在`.SUBCKT`、器件行和`.ENDS`。

#### 4.3 运行KLayout LVS

1. 打开并保存目标GDS。
2. 选择需要验证的顶层Cell。
3. 确认GDS目录中有正确的`*_reference.cir`。
4. 打开整合LVS规则。
5. 按`Shift+F5`运行。
6. 在Netlist Database Browser中查看比较结果。

---

### 5. 参考网表自动选择

LVS会按以下顺序寻找参考网表：

1. 优先查找：

   ```text
   <当前Layout Cell名称>_reference.cir
   ```

2. 如果不存在，则选择GDS目录中最近修改的：

   ```text
   *_reference.cir
   ```

3. 从转换宏写入的`Top Cell`注释读取参考顶层名称。
4. 如果没有该注释，则采用文件中最后一个`.SUBCKT`名称。

即使版图顶层叫`TOP`，参考网表顶层叫`LVS_TEST_ALL`，规则也会通过`same_circuit`建立对应，不需要每次手工修改LVS代码。

为了避免选错网表，建议每个Golden测试用例使用单独目录。

---

### 6. 输入图层与标签

LVS使用的主要绘制层与DRC一致。

网络标签层为：

| 金属 | Label层 |
|---|---:|
| Metal1 | 34/10 |
| Metal2 | 36/10 |
| Metal3 | 42/10 |

标签必须放在对应金属内部。

> 发布前必须确认LVS代码中M3标签写为`labels(42, 10)`。早期版本曾使用`42/1`，与最终Layer Properties不一致。

LVS内部还创建一个没有对应GDS编号的逻辑`bulk`层，用于表示共同的P型衬底。它不是需要用户绘制的实体图层。

---

### 7. Poly电阻与普通Poly的分离

同一个Poly图层既可能是：

- MOS栅极；
- 普通Poly导线；
- 电阻主体。

LVS用Resistor Mark进行区分：

```text
resistor_body = Poly ∩ Resistor Mark
poly_wire     = Poly - Resistor Mark
```

这样：

- Resistor Mark内部的Poly用于提取电阻；
- 其他Poly仍用于MOS栅极、栅极引出和电阻端头；
- 电阻主体不会被误判为MOS栅极。

SAB负责表示非硅化区域，但第一版LVS主要通过Resistor Mark识别电阻，SAB关系由DRC保证。

---

### 8. MIM电容的识别

MIM电容只在Capacitor Mark区域内识别：

```text
上极板 = FuseTop ∩ Capacitor Mark
下极板 = Metal2 ∩ Capacitor Mark
```

Via2被分成两类：

```text
MIM Via2    = Via2 ∩ FuseTop
普通Via2   = Via2 - FuseTop
```

MIM Via2只连接：

```text
FuseTop → Via2 → M3
```

普通Via2连接：

```text
M2 → Via2 → M3
```

这种分类非常重要。如果MIM上极板Via2同时把M2和M3连接起来，就会把上下极板短路。

---

### 9. MOS识别逻辑

#### 9.1 PMOS

PMOS需要同时满足：

1. Active位于N-Well内部；
2. Active被P+ Implant覆盖；
3. 普通Poly穿过该Active。

逻辑关系：

```text
PMOS Active = Active ∩ N-Well ∩ P+
PMOS Gate   = PMOS Active ∩ Poly Wire
PMOS S/D    = PMOS Active - PMOS Gate
```

Poly穿过Active的位置形成沟道，沟道两侧剩余的Active形成源漏区域。

#### 9.2 NMOS

NMOS需要同时满足：

1. Active位于N-Well外部；
2. Active被N+ Implant覆盖；
3. 普通Poly穿过该Active。

逻辑关系：

```text
NMOS Active = (Active - N-Well) ∩ N+
NMOS Gate   = NMOS Active ∩ Poly Wire
NMOS S/D    = NMOS Active - NMOS Gate
```

因此，只有Active并不会自动成为MOS。GuardRing虽然也包含Active，但没有Poly穿过时不会被识别为MOS沟道。

---

### 10. Body、N-Well Tap与GuardRing

#### 10.1 PMOS Body

PMOS的Body是N-Well。

N+ Active位于N-Well内部时，被识别为N-Well Tap。通过Contact和M1连接后，可以把整个N-Well网络连接到VDD或其他指定电位。

常见连接：

```text
N-Well → N+ Tap Active → Contact → M1 → VDD
```

#### 10.2 NMOS Body

第一版CNPDK假设所有NMOS共享同一个P型衬底，并将逻辑bulk网络全局连接到：

```text
VSS
```

P+ GuardRing被识别为P-Substrate Tap，并通过Contact和M1连接到衬底网络。

这是一种简化模型，不支持多个相互隔离、分别偏置的P-Well或Deep N-Well区域。

---

### 11. Contact分类

LVS根据Contact所在位置判断它连接什么：

| Contact位置 | 识别结果 |
|---|---|
| NMOS S/D上 | NMOS源漏Contact |
| PMOS S/D上 | PMOS源漏Contact |
| 普通Poly上 | Poly Contact |
| P+ Active、N-Well外 | P-Substrate Contact |
| N+ Active、N-Well内 | N-Well Contact |

DRC会阻止一个Contact同时连接Active和Poly，避免LVS产生不明确连接。

---

### 12. 电气连接关系

CNPDK整合LVS建立以下连接：

```text
NMOS S/D → Contact → M1
PMOS S/D → Contact → M1
Poly Wire → Contact → M1
N-Well → N+ Tap → Contact → M1
P-Substrate Tap → Contact → M1
M1 → Via1 → M2
M2 → Normal Via2 → M3
FuseTop → MIM Via2 → M3
```

M1、M2和M3 Label分别连接到对应金属网络，并形成顶层端口名称。

两个图形仅仅在视觉上靠近并不会导通。只有规则中定义了连接关系，并且相关图形实际交叠时，LVS才认为它们属于同一网络。

---

### 13. 器件参数提取

#### 13.1 MOS

MOS使用四端器件模型：

```text
D G S B
```

L和W来自版图沟道几何。

源漏对于普通MOS在电学上通常具有一定对称性，但参考网表的端口顺序仍应保持一致，避免比较和阅读时混乱。

#### 13.2 电阻

模型名：

```text
CNPDK_RPPOLY
```

计算公式：

```text
R = 311 × L / W
```

单位为欧姆，其中311是第一版采用的方块电阻。

#### 13.3 MIM电容

模型名：

```text
CNPDK_MIMCAP
```

计算公式：

```text
C = 2.0×10⁻¹⁵ × Area
```

其中面积单位为µm²，等价于：

```text
0.002 pF/µm²
```

---

### 14. 网表比较过程

规则完成器件提取和连线后会：

1. 输出版图提取网表；
2. 读取参考网表；
3. 建立不同顶层名称之间的对应；
4. 对齐并展开只存在于版图中的辅助PCell层级；
5. 合并可以等效的器件和网络；
6. 比较拓扑、端口和参数；
7. 在拓扑匹配后检查缺失端口。

`align`和`netlist.simplify`用于减少PCell层级和等效结构差异造成的无意义不匹配，不是为了忽略真实错误。

---

### 15. 如何判断LVS成功

在Netlist Database Browser中，应确认：

- 顶层电路显示绿色双向对应；
- Pins全部绿色；
- Nets全部绿色；
- Devices全部绿色；
- MOS W/L、电阻R、电容C没有黄色参数警告；
- 没有红色断路、短路或缺失器件标记。

不能仅凭以下现象判断成功：

- 规则脚本运行结束；
- 没有弹出异常窗口；
- 只看到顶层名称；
- 只有器件数量相同。

---

### 16. 常见LVS不匹配

#### 16.1 找不到参考网表

原因：

- GDS没有保存；
- GDS目录中没有`*_reference.cir`；
- 转换宏没有成功运行。

#### 16.2 端口不匹配

检查：

- Label是否使用正确层；
- Label原点是否位于金属内；
- 名称大小写是否一致；
- 原理图是否创建了对应顶层Pin。

#### 16.3 网络断路

检查：

- 金属是否真正相交；
- Via是否同时与上下层重叠；
- Contact是否落在正确底层；
- OUT、IN等标签是否放在预期网络。

一个网络断开后，比较器可能重新排列多个网络的对应，因此与该拓扑相关的其他端口也可能同时显示红色。

#### 16.4 网络短路

检查：

- 不同网络金属是否意外重叠；
- Via2是否错误地把MIM上下极板连接；
- GuardRing电源网络是否碰到信号线。

#### 16.5 器件缺失或多出

检查：

- Poly是否真正穿过Active；
- Implant和N-Well位置是否正确；
- Resistor Mark或Capacitor Mark是否存在；
- 器件是否被错误Flatten、删除或分割。

#### 16.6 参数不匹配

检查：

- Virtuoso CDF中的W、L是否输出；
- `propMapping`是否正确；
- PCell参数与原理图实例参数是否一致；
- 电阻Rsheet和电容ca是否采用相同默认值。

---

### 17. 已完成的LVS测试

| 测试 | 结果 |
|---|---|
| 独立NMOS | PASS |
| 独立PMOS | PASS |
| 独立P+ Poly SAB电阻 | PASS |
| 独立MIM电容 | PASS |
| CMOS反相器 | MATCH |
| RC负载CMOS反相器 | MATCH |
| 断开OUT | 成功检测网络不匹配 |
| 将参考MOS W从3改为4 | 成功检测参数不匹配 |

这些测试证明基础器件和组合电路能够完成版图到原理图的比较闭环。

---

### 18. 当前限制与维护建议

当前限制：

- 所有NMOS共享全局P型衬底VSS；
- 不支持隔离P-Well或Deep N-Well；
- 未提取寄生电阻和寄生电容；
- 未实现PEX；
- 未覆盖二极管、BJT、电感和更多器件；
- 器件参数为项目简化值，不是Foundry模型。

维护建议：

- 修改图层编号后同步修改LVS和Layer Properties；
- 修改Label层后重新验证全部端口；
- 修改PCell结构后运行独立器件和组合电路LVS；
- 每个Golden用例单独存放GDS与reference网表；
- 发布前运行`CNPDK_regression.py`。

---

## English Version

### 1. What LVS Does

LVS stands for Layout Versus Schematic. It compares the circuit extracted from the layout with a reference netlist exported from the schematic.

It detects missing or extra devices, opens, shorts, top-level port mismatches, and differences in MOS, resistor, or capacitor parameters.

DRC asks whether the geometry is legal. LVS asks whether the resulting electrical circuit matches the schematic.

> CNPDK LVS is intended for Mini-PDK learning and project verification, not foundry sign-off.

---

### 2. Supported Devices

| Layout Device | Reference Model | Main Compared Data |
|---|---|---|
| NMOS | CNPDK_NMOS | W, L, and connectivity |
| PMOS | CNPDK_PMOS | W, L, and connectivity |
| P+ Poly SAB resistor | CNPDK_RPPOLY | R and geometry |
| MIM capacitor | CNPDK_MIMCAP | C and connectivity |

The first release does not include complete diode, BJT, inductor, parasitic-device, or foundry-model support.

---

### 3. Files and Workflow

The integrated deck is stored under:

```text
CNPDK/lvs/CNPDK_complete_LVS.lylvs
```

The basic flow is:

1. Build the schematic in Virtuoso.
2. Export an auCdl/CDL netlist.
3. Place the netlist in the GDS directory.
4. Run `tools/v_netlist_k_cir.py`.
5. Confirm that a `*_reference.cir` file exists.
6. Open and save the GDS in KLayout.
7. Select the intended top cell and run the integrated LVS deck.
8. Inspect the result in Netlist Database Browser.

The deck writes `<Layout_Cell>_extracted.cir` and `<Layout_Cell>_LVS.lvsdb` into the layout directory.

---

### 4. Automatic Reference Selection

The deck first looks for:

```text
<current_layout_cell>_reference.cir
```

If it is not found, the newest `*_reference.cir` in the GDS directory is used.

The reference top name is read from the converter header or, as a fallback, from the last `.SUBCKT`. `same_circuit` maps different layout and reference top names automatically.

Use one directory per Golden test case to avoid selecting the wrong reference file.

---

### 5. Labels and the Logical Bulk Layer

| Metal | Label Layer |
|---|---:|
| M1 | 34/10 |
| M2 | 36/10 |
| M3 | 42/10 |

The label origin must lie inside the matching metal.

Before release, confirm that the deck uses `labels(42, 10)` for M3. An early version used `42/1`, which does not match the final Layer Properties definition.

The deck creates a logical `bulk` layer for the common P-type substrate. It has no physical GDS layer number and does not need to be drawn.

---

### 6. Resistor and MIM Separation

Resistor Mark separates resistor Poly from normal Poly:

```text
resistor_body = Poly ∩ Resistor Mark
poly_wire     = Poly - Resistor Mark
```

This prevents resistor Poly from being treated as a MOS gate.

The MIM capacitor is recognized only inside Capacitor Mark:

```text
top plate    = FuseTop ∩ Capacitor Mark
bottom plate = Metal2 ∩ Capacitor Mark
```

Via2 is split into:

```text
MIM Via2   = Via2 ∩ FuseTop
normal Via2 = Via2 - FuseTop
```

MIM Via2 connects FuseTop to M3. Normal Via2 connects M2 to M3. This separation prevents the MIM top and bottom plates from being shorted by the connectivity model.

---

### 7. MOS Recognition

PMOS recognition:

```text
PMOS Active = Active ∩ N-Well ∩ P+
PMOS Gate   = PMOS Active ∩ Poly Wire
PMOS S/D    = PMOS Active - PMOS Gate
```

NMOS recognition:

```text
NMOS Active = (Active - N-Well) ∩ N+
NMOS Gate   = NMOS Active ∩ Poly Wire
NMOS S/D    = NMOS Active - NMOS Gate
```

Only the Poly crossing Active forms a MOS channel. A GuardRing contains Active, but it is not recognized as a MOS unless Poly crosses it.

---

### 8. Body and GuardRing Connectivity

The PMOS body is the N-Well. N+ Active inside the N-Well is recognized as a well tap:

```text
N-Well → N+ Tap → Contact → M1
```

The first CNPDK release assumes one common P-type substrate for all NMOS devices. The logical bulk and P+ substrate taps are globally connected to `VSS`.

This is a simplified model and does not support separately biased isolated P-Wells or Deep N-Well structures.

---

### 9. Electrical Connectivity

The deck defines:

```text
NMOS S/D → Contact → M1
PMOS S/D → Contact → M1
Poly Wire → Contact → M1
N-Well → N+ Tap → Contact → M1
P-Substrate Tap → Contact → M1
M1 → Via1 → M2
M2 → Normal Via2 → M3
FuseTop → MIM Via2 → M3
```

M1, M2, and M3 labels attach names to their corresponding conductor networks.

Shapes that only appear visually close are not electrically connected. The required layers must overlap and the connection must be defined by the LVS deck.

---

### 10. Device Parameter Extraction

MOS devices use the four-terminal order:

```text
D G S B
```

W and L are extracted from channel geometry.

The Poly resistor model is `CNPDK_RPPOLY`:

```text
R = 311 × L / W
```

The MIM model is `CNPDK_MIMCAP`:

```text
C = 2.0×10⁻¹⁵ × Area
```

with area in µm², equivalent to `0.002 pF/µm²`.

---

### 11. Comparison Stages

After extraction and connectivity construction, the deck:

1. writes the extracted netlist;
2. reads the reference netlist;
3. maps different top names;
4. aligns and flattens layout-only helper/PCell hierarchy;
5. simplifies equivalent structures;
6. compares topology and parameters;
7. checks missing ports after a successful topology comparison.

`align` and `netlist.simplify` remove harmless representation differences. They are not intended to hide actual circuit errors.

---

### 12. How to Confirm a Match

In Netlist Database Browser, verify that:

- the top circuit has a green bidirectional match;
- all pins are green;
- all nets are green;
- all devices are green;
- W, L, R, and C have no parameter warnings;
- no red open, short, or missing-device markers remain.

A completed script without an exception is not sufficient proof of an LVS match.

---

### 13. Common Mismatches

- **Reference not found:** save the GDS and generate a `*_reference.cir`.
- **Port mismatch:** check label layer, label position, case, and schematic pins.
- **Open net:** check actual metal overlap, vias, contacts, and label placement.
- **Shorted net:** check overlapping routes, MIM Via2 classification, and GuardRing power connections.
- **Missing/extra device:** check Poly–Active crossing, implants, N-Well, and marker layers.
- **Parameter mismatch:** check Virtuoso CDF output, `propMapping`, PCell parameters, Rsheet, and capacitance density.

After one net is opened, the comparison engine may remap several related nets, so more than one port can appear red even when only one physical connection was removed.

---

### 14. Verified Tests and Limitations

Verified cases:

| Test | Result |
|---|---|
| Standalone NMOS | PASS |
| Standalone PMOS | PASS |
| Standalone P+ Poly SAB resistor | PASS |
| Standalone MIM capacitor | PASS |
| CMOS inverter | MATCH |
| RC-loaded CMOS inverter | MATCH |
| Open OUT | Net mismatch detected |
| Reference MOS W changed from 3 to 4 | Parameter mismatch detected |

Current limitations include a common NMOS substrate tied to VSS, no isolated P-Well/Deep N-Well support, no parasitic extraction, no PEX, and no complete diode/BJT/inductor set.

After any change to layers, labels, PCells, extraction, or connectivity, rerun the standalone and combined Golden LVS cases and execute `CNPDK_regression.py` before release.

