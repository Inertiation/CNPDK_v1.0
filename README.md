# CNPDK

## 中文说明

### 项目简介

CNPDK 是一个使用 **KLayout、Python 和 Cadence Virtuoso** 构建的个人 Mini-PDK 项目。项目实现了从图层定义、参数化器件生成，到 DRC、LVS 和自动化回归测试的基本开发流程。

本项目主要用于学习 PDK 开发、模拟版图设计和物理验证，也可作为个人工程能力展示。

### 已实现内容

| 模块 | 功能 | 状态 |
|---|---|---|
| Technology | 图层定义、显示配置和 Library 绑定 | 已完成 |
| Via PCell | M1–M2、M2–M3 通孔阵列 | 已完成 |
| Contact PCell | Active–M1、Poly–M1 接触孔 | 已完成 |
| NMOS / PMOS | 支持 W、L、NF 和 Gate 引出选择 | 已完成 |
| GuardRing | N+ N-Well、P+ P-Substrate 两种类型 | 已完成 |
| Poly Resistor | P+ Poly SAB 电阻及阻值估算 | 已完成 |
| MIM Capacitor | M2、FuseTop、Via2 和 M3 结构 | 已完成 |
| DRC | 按图层分类的整合设计规则 | 已完成 |
| LVS | MOS、电阻和电容的器件提取与比较 | 已完成 |
| Virtuoso | Symbol、Base CDF 和 auCdl 网表输出 | 已完成 |
| 自动化工具 | 安装检查、参数扫描、网表转换和回归测试 | 已完成 |
| SPICE Model / PEX | 精确电学模型和寄生提取 | 暂未实现 |

### 核心图层

| 图层 | GDS Layer/Datatype | 主要用途 |
|---|---:|---|
| N-Well | 21/0 | PMOS 阱区 |
| Active | 22/0 | 有源区 |
| Poly | 30/0 | MOS 栅极和多晶硅电阻 |
| P+ Implant | 31/0 | P 型注入 |
| N+ Implant | 32/0 | N 型注入 |
| Contact | 33/0 | Active/Poly 到 M1 |
| Metal 1 | 34/0 | 第一层金属 |
| Via 1 | 35/0 | M1 到 M2 |
| Metal 2 | 36/0 | 第二层金属 |
| Via 2 | 38/0 | M2 到 M3 |
| Metal 3 | 42/0 | 第三层金属 |
| SAB | 49/0 | 硅化物阻挡层 |
| FuseTop | 75/0 | MIM 上极板 |
| Resistor Mark | 110/5 | 电阻识别层 |
| Capacitor Mark | 117/5 | 电容识别层 |

网络标签层包括：M1 Label `34/10`、M2 Label `36/10` 和 M3 Label `42/10`。

### 目录结构

```text
CNPDK/
├─ CNPDK.lyt
├─ CNPDK.lyp
├─ pymacros/       # PCell与Library注册
├─ drc/            # 整合DRC规则
├─ lvs/            # 整合LVS规则
├─ tools/          # 安装、转换、扫描和回归脚本
```

### 安装与使用

1. 将整个 `CNPDK` 文件夹复制到 KLayout 的 Technology 目录。
2. 启动 KLayout，并选择 `CNPDK` Technology。
3. 确认 Libraries 面板中已经出现 `CNPDK` Library。
4. 新建 Layout，从 Library 中放置所需 PCell。
5. 保存版图后运行整合 DRC。
6. 进行 LVS 时，将 Virtuoso 导出的netlist转换为 `*_reference.cir`，并与 GDS 文件放在同一目录，然后运行整合 LVS。

### 验证结果

- 基础 PCell 已完成独立 DRC 检查。
- MOS 参数扫描覆盖多组 W、L、NF 和 Gate 引出组合。
- NMOS、PMOS、P+ Poly SAB 电阻和 MIM 电容均可被 LVS 提取。
- CMOS 反相器已通过 LVS。
- 包含 NMOS、PMOS、电阻和 MIM 电容的 RC 负载反相器已实现 **DRC 0 错误、LVS 匹配**。
- 网络断路和 MOS 参数不匹配可以被 LVS 正确检测。

### 自动化工具

- `CNPDK_install_check.py`：检查PDK结构、路径和运行环境。
- `CNPDK_PCell_Parameter_Sweep.py`：批量生成PCell参数测试版图。
- `CNPDK_regression.py`：自动执行PCell、DRC和LVS回归测试。
- `CNPDK_netlist_cir.py`：转换Virtuoso导出的网表。
- `CNPDK_AutoLayout_v1_0.py`：实验性自动布局与曼哈顿布线工具。

自动布局工具只用于小型示例和流程研究，不能替代工业级自动布局布线、人工优化或最终DRC/LVS验证。

### 项目限制

- 规则主要参考公开资料并进行了简化。
- 不属于 GF180MCU 或其他工艺的官方兼容 PDK。
- 未经过流片验证。
- 暂无完整 SPICE 模型和 PEX 规则。
- 当前版本主要用于学习、验证流程和个人项目展示。

### 当前版本

**CNPDK v0.1**

当前版本已经完成核心 PCell、整合 DRC、整合 LVS、Virtuoso CDF/CDL 流程以及基础自动化工具。

---

## English Version

### Overview

CNPDK is a personal Mini-PDK project developed with **KLayout, Python, and Cadence Virtuoso**. It implements a basic workflow from layer definition and parameterized device generation to DRC, LVS, and automated regression testing.

The project is intended for learning PDK development, analog layout, and physical verification, as well as demonstrating personal engineering skills.

### Implemented Features

| Module | Function | Status |
|---|---|---|
| Technology | Layer definition, display configuration, and Library binding | Completed |
| Via PCell | M1–M2 and M2–M3 via arrays | Completed |
| Contact PCell | Active–M1 and Poly–M1 contacts | Completed |
| NMOS / PMOS | W, L, NF, and gate-contact options | Completed |
| GuardRing | N+ N-Well and P+ P-Substrate types | Completed |
| Poly Resistor | P+ Poly SAB resistor with resistance estimation | Completed |
| MIM Capacitor | M2, FuseTop, Via2, and M3 structure | Completed |
| DRC | Integrated layer-based design rules | Completed |
| LVS | MOS, resistor, and capacitor extraction and comparison | Completed |
| Virtuoso | Symbols, Base CDF, and auCdl netlist generation | Completed |
| Automation | Installation check, parameter sweep, netlist conversion, and regression | Completed |
| SPICE Model / PEX | Accurate electrical models and parasitic extraction | Not implemented |

### Core Layers

| Layer | GDS Layer/Datatype | Main Purpose |
|---|---:|---|
| N-Well | 21/0 | PMOS well |
| Active | 22/0 | Active area |
| Poly | 30/0 | MOS gate and poly resistor |
| P+ Implant | 31/0 | P-type implant |
| N+ Implant | 32/0 | N-type implant |
| Contact | 33/0 | Active/Poly to M1 |
| Metal 1 | 34/0 | First metal layer |
| Via 1 | 35/0 | M1 to M2 |
| Metal 2 | 36/0 | Second metal layer |
| Via 2 | 38/0 | M2 to M3 |
| Metal 3 | 42/0 | Third metal layer |
| SAB | 49/0 | Silicide blocking layer |
| FuseTop | 75/0 | MIM top plate |
| Resistor Mark | 110/5 | Resistor recognition |
| Capacitor Mark | 117/5 | Capacitor recognition |

The net-label layers include M1 Label `34/10`, M2 Label `36/10`, and M3 Label `42/10`.

### Directory Structure

```text
CNPDK/
├─ CNPDK.lyt
├─ CNPDK.lyp
├─ pymacros/       # PCells and Library registration
├─ drc/            # Integrated DRC deck
├─ lvs/            # Integrated LVS deck
├─ tools/          # Installation, conversion, sweep, and regression tools
```

### Installation and Usage

1. Copy the complete `CNPDK` folder into the KLayout Technology directory.
2. Start KLayout and select the `CNPDK` Technology.
3. Confirm that the `CNPDK` Library is available in the Libraries panel.
4. Create a new layout and place the required PCells.
5. Save the layout and run the integrated DRC deck.
6. For LVS, convert the Virtuoso netlist into a `*_reference.cir` file, place it in the same directory as the GDS file, and run the integrated LVS deck.

Environment check:

```bash
python tools/CNPDK_install_check.py --check
```

Automated regression:

```bash
python tools/CNPDK_regression.py
```

### Verification Results

- Basic PCells have passed individual DRC checks.
- MOS parameter sweeps cover multiple W, L, NF, and gate-contact combinations.
- NMOS, PMOS, P+ Poly SAB resistors, and MIM capacitors can be extracted by LVS.
- A CMOS inverter has passed LVS.
- An RC-loaded inverter containing NMOS, PMOS, resistor, and MIM capacitor devices has achieved **zero DRC errors and an LVS match**.
- Open-net and MOS-parameter mismatch tests are correctly detected by LVS.

### Automation Tools

- `CNPDK_install_check.py`: checks the PDK structure, paths, and environment.
- `CNPDK_PCell_Parameter_Sweep.py`: generates PCell parameter-sweep layouts.
- `CNPDK_regression.py`: runs automated PCell, DRC, and LVS regression tests.
- `v_netlist_k_cir.py`: converts Virtuoso-exported netlists.
- `CNPDK_AutoLayout_v1_0.py`: experimental automatic placement and Manhattan-routing tool.

The automatic layout tool is intended only for small examples and workflow experiments. It does not replace industrial place-and-route tools, manual layout optimization, or final DRC/LVS sign-off.

### Limitations

- The rules are simplified from publicly available references.
- CNPDK is not an officially compatible PDK for GF180MCU or any other process.
- The project has not been validated by fabrication.
- Complete SPICE models and PEX rules are not currently included.
- Density, antenna, ESD, latch-up, reliability, and other full sign-off checks are not covered.
- The current version is intended for learning, workflow verification, and portfolio demonstration.

### Current Version

**CNPDK v0.1**

The current release includes the core PCells, integrated DRC, integrated LVS, the Virtuoso CDF/CDL flow, and basic automation tools.

