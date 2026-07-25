# CNPDK Installation Guide / CNPDK 安装说明

## 中文版本

### 1. 文档目的

本文说明如何在新电脑上安装和检查 CNPDK。

CNPDK 的版图、PCell、DRC 和 LVS 主要运行在 **KLayout** 中；原理图 Symbol、CDF 和 CDL 网表功能运行在 **Cadence Virtuoso** 中。只使用版图功能时，可以只安装 KLayout 部分。

> CNPDK 是个人 Mini-PDK，不是晶圆厂官方 PDK，也没有经过流片或工业签核。

---

### 2. 建议软件环境

| 软件 | 建议环境 | 主要用途 |
|---|---|---|
| KLayout | 0.28或更高版本，项目开发时使用0.30.9 | PCell、版图、DRC、LVS |
| Python | 3.8或更高版本 | 安装检查和自动化脚本 |
| Cadence Virtuoso | 可选，Linux环境 | Symbol、CDF、原理图和CDL网表 |

KLayout内部已经带有可供宏使用的Python环境，因此运行PCell不需要另外安装`pya`。

---

### 3. 安装包结构

安装前请确认CNPDK目录至少包含：

```text
CNPDK/
├─ CNPDK.lyt
├─ CNPDK.lyp
├─ pymacros/
│  ├─ library.py
│  ├─ via_array.py
│  ├─ contact_array.py
│  ├─ nmos.py
│  ├─ pmos.py
│  ├─ guardring.py
│  ├─ rpposab.py
│  └─ mim.py
├─ drc/
├─ lvs/
├─ tools/
├─ tests/
└─ docs/
```

请保持这些文件和文件夹的相对位置不变。CNPDK内部尽量使用相对路径，因此不要只复制单独的`CNPDK.lyt`或某个PCell文件。

---

### 4. Windows下安装KLayout部分

#### 4.1 复制Technology目录

关闭KLayout，然后把完整的`CNPDK`文件夹复制到用户Technology目录：

```text
C:\Users\<用户名>\KLayout\tech\CNPDK
```

安装完成后的示例：

```text
C:\Users\<用户名>\KLayout\tech\CNPDK\CNPDK.lyt
C:\Users\<用户名>\KLayout\tech\CNPDK\CNPDK.lyp
C:\Users\<用户名>\KLayout\tech\CNPDK\pymacros\library.py
```

如果你的KLayout用户目录位于其他位置，也可以安装到对应的`tech`目录。用户名和盘符只属于本机安装路径，不应写死在CNPDK内部脚本中。

#### 4.2 启动并选择Technology

1. 启动KLayout。
2. 新建或打开一个Layout。
3. 在Technology选择位置选择`CNPDK`。
4. 打开Libraries面板，确认可以看到`CNPDK` Library。
5. 展开Library，确认NMOS、PMOS、电阻、MIM、Via、Contact和GuardRing均可见。

#### 4.3 Library没有自动加载时

如果Technology已经出现，但Libraries面板没有`CNPDK`：

1. 打开`Macros > Macro Development`。
2. 找到或导入：

   ```text
   CNPDK\pymacros\library.py
   ```

3. 确认解释器为Python。
4. 勾选`Run on start-up`，或确保文件顶部保留：

   ```python
   # $autorun
   ```

5. 按`Shift+F5`运行一次。
6. 重新查看Libraries面板；必要时重启KLayout。

不要分别重复运行多个会注册同名`CNPDK` Library的入口脚本。正式安装应以`library.py`作为统一注册入口。

---

### 5. 环境检查

打开Windows PowerShell或命令提示符，进入CNPDK根目录，然后运行：

```powershell
python tools\CNPDK_install_check.py --check
```

环境检查主要确认：

- `CNPDK.lyt`和`CNPDK.lyp`是否存在；
- `pymacros`、`drc`、`lvs`和`tools`目录是否完整；
- PCell Python文件能否通过语法检查；
- Layer Properties是否包含预期图层；
- 文件中是否残留旧电脑的绝对路径；
- 当前系统是否能找到KLayout。

如果命令行找不到KLayout，可以在运行回归测试时指定程序路径：

```powershell
python tools\CNPDK_regression.py --klayout "C:\Program Files\KLayout\klayout.exe"
```

也可以设置环境变量：

```powershell
set KLAYOUT_EXE=C:\Program Files\KLayout\klayout.exe
```

---

### 6. 安装后的快速检查

建议按以下顺序确认安装有效：

1. 新建一个Layout并选择CNPDK Technology。
2. 从CNPDK Library放置一个NMOS。
3. 修改W、L、NF和Gate Contact Position。
4. 确认版图会随参数更新。
5. 再分别放置Via、Contact、电阻和MIM电容。
6. 保存测试GDS。
7. 运行整合DRC，确认规则可以打开并生成报告。

如果需要完整检查，可运行：

```powershell
python tools\CNPDK_regression.py
```

回归报告默认保存在：

```text
CNPDK\tests\regression_output\
```

首次安装时，如果尚未放入LVS Golden测试版图，LVS项目显示`SKIP`是正常现象；这不等于LVS规则失败。

---

### 7. Virtuoso部分安装（可选）

只有需要使用CNPDK原理图Symbol、CDF和CDL网表功能时，才需要安装这一部分。

#### 7.1 准备Virtuoso Library

假设CNPDK原理图库位于：

```text
<CNPDK_ROOT>/virtuoso/CN_PDK
```

该目录应包含Virtuoso Library所需的cell、symbol、CDF或相关数据库文件。

#### 7.2 修改cds.lib

在Virtuoso启动目录的`cds.lib`中增加：

```text
DEFINE CN_PDK /实际安装路径/CNPDK/virtuoso/CN_PDK
```

例如：

```text
DEFINE CN_PDK /home/user/PDK/CNPDK/virtuoso/CN_PDK
```

这里的路径需要根据Linux电脑上的实际位置填写。这个设置属于本机Virtuoso环境，不应该写入可移植的KLayout脚本。

#### 7.3 启动检查

1. 从包含正确`cds.lib`的目录启动Virtuoso。
2. 在Library Manager中确认`CN_PDK`可见。
3. 打开NMOS、PMOS、电阻和MIM的symbol。
4. 新建测试schematic并放置器件。
5. 按端口连线，检查Symbol连接点是否正常。
6. 生成auCdl/CDL网表，确认器件模型名和W、L等参数能够输出。

KLayout Library名称使用`CNPDK`，Virtuoso原理图库历史名称使用`CN_PDK`。两者名称不同不会影响LVS，只要参考网表中的器件模型名与LVS规则一致。

---

### 8. 常见安装问题

#### 找不到CNPDK Technology

- 确认`CNPDK.lyt`位于`KLayout\tech\CNPDK`中；
- 确认没有多套嵌套目录，例如`CNPDK\CNPDK\CNPDK.lyt`；
- 重启KLayout。

#### Technology存在，但没有PCell Library

- 运行`pymacros/library.py`；
- 确认解释器是Python；
- 确认脚本设置为启动时运行；
- 查看Console中是否有`ModuleNotFoundError`。

#### 出现`ModuleNotFoundError`

- 确认`library.py`与其他PCell文件都在同一个`pymacros`目录；
- 不要只复制`library.py`；
- 保留文件名，例如`nmos.py`、`pmos.py`，不要随意加括号或版本后缀。

#### 图层颜色或名称不正确

- 确认`CNPDK.lyp`与`CNPDK.lyt`处于同一根目录；
- 检查`CNPDK.lyt`是否使用相对路径引用`CNPDK.lyp`；
- 重新选择CNPDK Technology并加载Layer Properties。

#### DRC或LVS无法运行

- 确认版图已经保存；
- 确认规则文件位于`drc`或`lvs`目录；
- LVS时确认GDS目录中存在对应的`*_reference.cir`；
- 检查当前打开的Cell是否为需要验证的顶层Cell。

---

### 9. 卸载

1. 关闭KLayout。
2. 删除用户Technology目录中的`CNPDK`文件夹。
3. 如果安装了Virtuoso部分，从`cds.lib`中删除或注释`DEFINE CN_PDK ...`。
4. 不要删除个人测试版图和网表，除非已经完成备份。

---

## English Version

### 1. Purpose

This document explains how to install and verify CNPDK on a new computer.

The layout, PCell, DRC, and LVS parts of CNPDK run mainly in **KLayout**. The schematic symbols, CDF, and CDL netlist flow run in **Cadence Virtuoso**. If only the layout flow is required, the KLayout part can be installed independently.

> CNPDK is a personal Mini-PDK. It is not an official foundry PDK and has not been fabricated or qualified for industrial sign-off.

---

### 2. Recommended Environment

| Software | Recommended Environment | Main Purpose |
|---|---|---|
| KLayout | Version 0.28 or later; version 0.30.9 was used during development | PCells, layout, DRC, and LVS |
| Python | Version 3.8 or later | Installation checks and automation |
| Cadence Virtuoso | Optional, running on Linux | Symbols, CDF, schematics, and CDL netlists |

KLayout includes its own Python environment for macros, so a separate installation of `pya` is not required for running the PCells.

---

### 3. Package Structure

Before installation, confirm that the CNPDK directory contains at least:

```text
CNPDK/
├─ CNPDK.lyt
├─ CNPDK.lyp
├─ pymacros/
│  ├─ library.py
│  ├─ via_array.py
│  ├─ contact_array.py
│  ├─ nmos.py
│  ├─ pmos.py
│  ├─ guardring.py
│  ├─ rpposab.py
│  └─ mim.py
├─ drc/
├─ lvs/
├─ tools/
├─ tests/
└─ docs/
```

Keep the relative positions of these files and directories unchanged. CNPDK is designed to use relative paths where possible, so do not copy only `CNPDK.lyt` or an individual PCell file.

---

### 4. Installing the KLayout Part on Windows

#### 4.1 Copy the Technology Directory

Close KLayout and copy the complete `CNPDK` directory into the user Technology directory:

```text
C:\Users\<username>\KLayout\tech\CNPDK
```

Example after installation:

```text
C:\Users\<username>\KLayout\tech\CNPDK\CNPDK.lyt
C:\Users\<username>\KLayout\tech\CNPDK\CNPDK.lyp
C:\Users\<username>\KLayout\tech\CNPDK\pymacros\library.py
```

If your KLayout user directory is stored elsewhere, install CNPDK into the corresponding `tech` directory. The local username and drive letter belong only to the computer-specific installation path and must not be hard-coded inside CNPDK scripts.

#### 4.2 Start KLayout and Select the Technology

1. Start KLayout.
2. Create or open a layout.
3. Select `CNPDK` as the active Technology.
4. Open the Libraries panel and confirm that the `CNPDK` Library is visible.
5. Expand the Library and confirm that NMOS, PMOS, resistor, MIM, Via, Contact, and GuardRing devices are available.

#### 4.3 If the Library Does Not Load Automatically

If the Technology is available but the `CNPDK` Library is missing:

1. Open `Macros > Macro Development`.
2. Locate or import:

   ```text
   CNPDK\pymacros\library.py
   ```

3. Confirm that the interpreter is Python.
4. Enable `Run on start-up`, or keep the following line at the top of the file:

   ```python
   # $autorun
   ```

5. Press `Shift+F5` to run the script once.
6. Check the Libraries panel again and restart KLayout if necessary.

Do not repeatedly run multiple entry scripts that register the same `CNPDK` Library name. The released package should use `library.py` as the single registration entry.

---

### 5. Environment Check

Open Windows PowerShell or Command Prompt, enter the CNPDK root directory, and run:

```powershell
python tools\CNPDK_install_check.py --check
```

The checker verifies:

- the presence of `CNPDK.lyt` and `CNPDK.lyp`;
- the required `pymacros`, `drc`, `lvs`, and `tools` directories;
- Python syntax in the PCell files;
- expected layers in the Layer Properties file;
- absolute paths left from another computer;
- whether KLayout can be found.

If KLayout cannot be found from the command line, specify its executable when running regression:

```powershell
python tools\CNPDK_regression.py --klayout "C:\Program Files\KLayout\klayout.exe"
```

Alternatively, define an environment variable:

```powershell
set KLAYOUT_EXE=C:\Program Files\KLayout\klayout.exe
```

---

### 6. Quick Post-Installation Check

Use the following sequence to confirm that the installation works:

1. Create a new layout and select the CNPDK Technology.
2. Place an NMOS from the CNPDK Library.
3. Change W, L, NF, and Gate Contact Position.
4. Confirm that the generated geometry updates.
5. Place Via, Contact, resistor, and MIM PCells.
6. Save the test GDS.
7. Run the integrated DRC deck and confirm that a report is generated.

For a more complete check, run:

```powershell
python tools\CNPDK_regression.py
```

Regression results are stored by default in:

```text
CNPDK\tests\regression_output\
```

If no LVS Golden layouts have been added yet, an LVS result of `SKIP` is normal during the first installation. It does not mean that the LVS deck has failed.

---

### 7. Installing the Virtuoso Part (Optional)

This section is required only when using the CNPDK schematic symbols, CDF, and CDL netlist flow.

#### 7.1 Prepare the Virtuoso Library

Assume that the CNPDK schematic library is stored at:

```text
<CNPDK_ROOT>/virtuoso/CN_PDK
```

The directory should contain the required Virtuoso cells, symbols, CDF data, or related database files.

#### 7.2 Update cds.lib

Add the following line to the `cds.lib` file in the Virtuoso startup directory:

```text
DEFINE CN_PDK /actual/installation/path/CNPDK/virtuoso/CN_PDK
```

Example:

```text
DEFINE CN_PDK /home/user/PDK/CNPDK/virtuoso/CN_PDK
```

This path must match the actual Linux installation. It is part of the local Virtuoso environment and should not be embedded in portable KLayout scripts.

#### 7.3 Startup Check

1. Start Virtuoso from the directory containing the correct `cds.lib`.
2. Confirm that `CN_PDK` appears in Library Manager.
3. Open the NMOS, PMOS, resistor, and MIM symbols.
4. Create a test schematic and place the devices.
5. Connect the pins and confirm that the symbol terminals work correctly.
6. Generate an auCdl/CDL netlist and confirm that model names and parameters such as W and L are present.

The KLayout Library is named `CNPDK`, while the historical Virtuoso schematic Library is named `CN_PDK`. The different names do not prevent LVS, provided that the device model names in the reference netlist match the LVS rule deck.

---

### 8. Common Installation Problems

#### CNPDK Technology Is Missing

- Confirm that `CNPDK.lyt` is located under `KLayout\tech\CNPDK`.
- Check for accidental nested directories such as `CNPDK\CNPDK\CNPDK.lyt`.
- Restart KLayout.

#### The Technology Exists but the PCell Library Is Missing

- Run `pymacros/library.py`.
- Confirm that the interpreter is Python.
- Enable the startup option for the script.
- Check the Console for `ModuleNotFoundError`.

#### `ModuleNotFoundError`

- Confirm that `library.py` and all PCell files are in the same `pymacros` directory.
- Do not copy only `library.py`.
- Keep the expected filenames, such as `nmos.py` and `pmos.py`, without brackets or version suffixes.

#### Incorrect Layer Colors or Names

- Confirm that `CNPDK.lyp` and `CNPDK.lyt` are in the same root directory.
- Confirm that `CNPDK.lyt` references `CNPDK.lyp` through a relative path.
- Select the CNPDK Technology again and reload the Layer Properties.

#### DRC or LVS Does Not Run

- Confirm that the layout has been saved.
- Confirm that the rule decks are present in the `drc` and `lvs` directories.
- For LVS, confirm that a matching `*_reference.cir` file is present in the GDS directory.
- Confirm that the active cell is the intended top-level cell.

---

### 9. Uninstallation

1. Close KLayout.
2. Delete the `CNPDK` directory from the user Technology directory.
3. If the Virtuoso part was installed, remove or comment out the corresponding `DEFINE CN_PDK ...` line in `cds.lib`.
4. Do not delete personal test layouts or netlists unless they have been backed up.

