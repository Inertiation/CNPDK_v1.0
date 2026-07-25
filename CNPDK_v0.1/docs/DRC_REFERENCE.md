# CNPDK DRC Rule Reference / CNPDK DRC规则说明

## 中文版本

### 1. DRC是什么

DRC是Design Rule Check的缩写，用于检查版图几何图形是否满足设定的制造规则。

例如，它会检查：

- 一根金属是否太窄；
- 两根金属是否离得太近；
- Contact或Via是否过小；
- 金属是否完整包围Contact；
- MOS源漏区是否被正确的注入层覆盖；
- 电阻和MIM电容的识别层是否正确。

DRC只检查版图几何关系。DRC为0不代表电路连接一定正确，网络和器件一致性需要通过LVS检查。

> CNPDK规则主要用于个人Mini-PDK的开发学习和流程验证，不是晶圆厂签核规则。

---

### 2. 规则文件与运行方法

整合DRC文件位于：

```text
CNPDK/drc/
```

建议发布文件名：

```text
CNPDK_complete_DRC.lydrc
```

运行步骤：

1. 在KLayout中打开并保存需要检查的GDS。
2. 确认当前顶层Cell正确。
3. 打开整合DRC规则。
4. 按`Shift+F5`运行。
5. 在Marker Database Browser中查看错误。
6. 双击错误，定位到对应几何位置。
7. 修改版图并重新运行。

---

### 3. 错误编号方法

错误名称采用：

```text
组号.序号_LAYER.RULE_NAME
```

例如：

```text
7.2_M1.MIN_SPACE
```

表示：

- `7`：Metal1规则组；
- `2`：该组中的第2条规则；
- `M1.MIN_SPACE`：Metal1最小间距。

同一图层的错误会集中排列，便于定位和维护。

SAB和FuseTop目前没有独立的全局规则，因此编号中保留了相应分组位置，但具体器件规则归入`RES_MK`和`CAP_MK`。

---

### 4. 输入图层

| 名称 | GDS Layer/Datatype | 用途 |
|---|---:|---|
| N-Well | 21/0 | PMOS阱区 |
| Active | 22/0 | 有源区 |
| Poly | 30/0 | MOS栅极和Poly电阻 |
| P+ Implant | 31/0 | P型注入 |
| N+ Implant | 32/0 | N型注入 |
| Contact | 33/0 | Active/Poly到M1 |
| Metal1 | 34/0 | 第一层金属 |
| Via1 | 35/0 | M1到M2 |
| Metal2 | 36/0 | 第二层金属 |
| Via2 | 38/0 | M2到M3或MIM上极板到M3 |
| Metal3 | 42/0 | 第三层金属 |
| SAB | 49/0 | 硅化物阻挡 |
| FuseTop | 75/0 | MIM上极板 |
| Resistor Mark | 110/5 | 电阻识别 |
| Capacitor Mark | 117/5 | MIM电容识别 |

Label层用于LVS网络命名，不参与当前几何DRC。

---

### 5. 派生区域的含义

规则内部会根据绘制图层计算一些“逻辑区域”。它们不是额外的GDS图层。

| 派生区域 | 通俗解释 |
|---|---|
| MOS Gate | Poly与Active交叠的区域 |
| NMOS Gate | 位于N+ Active、N-Well外部的MOS Gate |
| PMOS Gate | 位于P+ Active、N-Well内部的MOS Gate |
| Active Contact | 位于Active上的Contact |
| Poly Contact | 位于Poly上的Contact |
| Resistor Poly | Poly与Resistor Mark交叠的区域 |
| MIM Top | FuseTop与Capacitor Mark交叠的区域 |
| MIM Bottom | 与MIM Top对应的M2下极板 |
| Normal Via2 | 不属于MIM上极板连接的普通Via2 |

这样可以让同一个Poly、M2或Via2图层在不同器件中采用不同检查方式。

---

### 6. 完整规则列表

#### 6.1 N-Well规则

| 编号 | 检查内容 | 最小值 |
|---|---|---:|
| 1.1 | N-Well最小宽度 | 0.86 µm |
| 1.2 | N-Well最小间距 | 0.60 µm |
| 1.3 | N-Well对PMOS P+ Active的包围 | 0.43 µm |
| 1.4 | N-Well对N+ Well Tap的包围 | 0.12 µm |

#### 6.2 Active规则

| 编号 | 检查内容 | 最小值 |
|---|---|---:|
| 2.1 | Active最小宽度 | 0.22 µm |
| 2.2 | Active最小间距 | 0.28 µm |
| 2.3 | Active必须被N+或P+ Implant完整覆盖 | 必须覆盖 |

`2.3`用于避免出现没有器件类型定义的Active。

#### 6.3 Poly和Gate规则

| 编号 | 检查内容 | 最小值或要求 |
|---|---|---:|
| 3.1 | Poly最小宽度 | 0.18 µm |
| 3.2 | Poly最小间距 | 0.24 µm |
| 3.3 | NMOS栅长 | 0.28 µm |
| 3.4 | PMOS栅长 | 0.28 µm |
| 3.5 | Active Contact到MOS Gate间距 | 0.15 µm |
| 3.6 | Poly Contact到Active间距 | 0.17 µm |
| 3.7 | Contact不得位于有效MOS Gate上 | 禁止 |

MOS器件身份由LVS负责识别，因此总DRC中不使用`MOS.GATE.UNDEFINED`规则。

#### 6.4 N+ Implant规则

| 编号 | 检查内容 | 最小值或要求 |
|---|---|---:|
| 4.1 | N+最小宽度 | 0.40 µm |
| 4.2 | N+最小间距 | 0.40 µm |
| 4.3 | N+对NMOS Active的包围 | 0.16 µm |
| 4.4 | N+对N-Well Tap Active的包围 | 0.16 µm |
| 4.5 | N+对NMOS Gate的包围 | 0.23 µm |
| 4.6 | N+与P+不得重叠 | 禁止重叠 |

#### 6.5 P+ Implant规则

| 编号 | 检查内容 | 最小值 |
|---|---|---:|
| 5.1 | P+最小宽度 | 0.40 µm |
| 5.2 | P+最小间距 | 0.40 µm |
| 5.3 | P+对PMOS Active的包围 | 0.16 µm |
| 5.4 | P+对P-Substrate Tap Active的包围 | 0.16 µm |
| 5.5 | P+对PMOS Gate的包围 | 0.23 µm |

#### 6.6 Contact规则

| 编号 | 检查内容 | 最小值或要求 |
|---|---|---:|
| 6.1 | Contact尺寸 | 0.22 µm |
| 6.2 | Contact间距 | 0.25 µm |
| 6.3 | Contact下方必须存在Active或Poly | 必须存在 |
| 6.4 | 一个Contact不得同时连接Active和Poly | 禁止 |
| 6.5 | Active对Contact的包围 | 0.07 µm |
| 6.6 | Poly对Contact的包围 | 0.07 µm |

#### 6.7 Metal1规则

| 编号 | 检查内容 | 最小值 |
|---|---|---:|
| 7.1 | M1宽度 | 0.23 µm |
| 7.2 | M1间距 | 0.23 µm |
| 7.3 | M1对Contact的包围 | 0.06 µm |
| 7.4 | M1对Via1的包围 | 0.06 µm |

#### 6.8 Via1规则

| 编号 | 检查内容 | 最小值 |
|---|---|---:|
| 8.1 | Via1尺寸 | 0.26 µm |
| 8.2 | Via1间距 | 0.26 µm |

#### 6.9 Metal2规则

| 编号 | 检查内容 | 最小值 |
|---|---|---:|
| 9.1 | M2宽度 | 0.28 µm |
| 9.2 | M2间距 | 0.28 µm |
| 9.3 | M2对Via1的包围 | 0.06 µm |
| 9.4 | M2对普通Via2的包围 | 0.06 µm |

MIM上极板使用的Via2不属于普通Via2，因此由电容规则单独检查。

#### 6.10 Via2规则

| 编号 | 检查内容 | 最小值 |
|---|---|---:|
| 10.1 | Via2尺寸 | 0.26 µm |
| 10.2 | Via2间距 | 0.26 µm |

总DRC没有规定所有Via2都必须位于FuseTop内部，也没有规定所有Via2上方必须存在M3。普通M2–M3连接和MIM连接会根据几何位置分别处理。

#### 6.11 Metal3规则

| 编号 | 检查内容 | 最小值 |
|---|---|---:|
| 11.1 | M3宽度 | 0.28 µm |
| 11.2 | M3间距 | 0.28 µm |
| 11.3 | M3对普通Via2的包围 | 0.06 µm |

#### 6.12 SAB说明

SAB可能用于不同类型的非硅化结构，因此没有规定“所有SAB都必须属于电阻”。

电阻相关的SAB关系由Resistor Mark触发，并归入13.x规则组。

#### 6.13 Resistor Mark电阻规则

| 编号 | 检查内容 | 最小值或要求 |
|---|---|---:|
| 13.1 | RES_MK定义的Poly电阻宽度 | 0.80 µm |
| 13.2 | RES_MK定义的Poly电阻间距 | 0.40 µm |
| 13.3 | 电阻区域到Active间距 | 0.60 µm |
| 13.4 | 电阻区域到无关Poly间距 | 0.60 µm |
| 13.5 | P+对电阻区域的包围 | 0.30 µm |
| 13.6 | RES_MK必须被Poly覆盖 | 必须覆盖 |
| 13.7 | RES_MK必须位于SAB内部 | 必须位于内部 |
| 13.8 | 电阻SAB到端头Contact间距 | 0.22 µm |

规则以Resistor Mark为触发条件，因此普通Poly不会被误判为电阻Poly。

旧版中只适用于横向电阻的SAB方向规则已经删除，避免电阻旋转90°后产生误报。

#### 6.14 FuseTop说明

FuseTop目前主要用于MIM电容。具体检查由Capacitor Mark触发，并归入15.x规则组。

#### 6.15 Capacitor Mark电容规则

| 编号 | 检查内容 | 最小值或要求 |
|---|---|---:|
| 15.1 | CAP_MK必须与FuseTop完全重合 | 必须重合 |
| 15.2 | FuseTop最小尺寸 | 5.00 µm × 5.00 µm |
| 15.3 | FuseTop间距 | 0.60 µm |
| 15.4 | M2对MIM上极板的包围 | 0.60 µm |
| 15.5 | MIM下极板到无关M2间距 | 1.20 µm |
| 15.6 | MIM上极板Via2间距 | 0.50 µm |
| 15.7 | FuseTop对MIM Via2的包围 | 0.40 µm |
| 15.8 | M3对MIM Via2的包围 | 0.12 µm |

这里的“无关M2”是指不属于当前MIM下极板的其他M2图形。

---

### 7. 常见错误的理解和修改

#### MIN_WIDTH

表示图形局部过窄。通常需要加宽对应图层，而不是只移动其他图形。

#### MIN_SPACE

表示两个不相连图形距离过近。可以：

- 增大间距；
- 缩短其中一段图形；
- 在确认属于同一网络时，正确连接成连续图形。

不能为了消除错误而盲目删除规则。

#### ENC或ENCLOSURE

表示外层图形对孔或器件区域包围不足。应扩大外层，或把孔向内部移动。

#### NO_BOTTOM_LAYER

表示Contact下方没有有效Active或Poly。应检查Contact类型和放置位置。

#### ACTIVE.NO_IMPLANT

表示Active没有被N+或P+完全覆盖。应补充正确的注入层，而不是随意删除Active。

#### CAP_MK.M2.SPACE.UNRELATED_M2

表示MIM下极板距离其他M2太近。应移动无关走线，尽量避免在MIM附近或上方穿越其他网络。

---

### 8. 规则维护原则

- 通用规则按真实绘制图层分类；
- 器件专用规则由Resistor Mark或Capacitor Mark触发；
- DRC负责几何，不负责判断原理图功能；
- 新增规则前要同时准备合法和非法测试版图；
- 修改PCell后应运行参数扫描和总DRC；
- 删除规则前先确认它是误报，而不是PCell几何错误；
- 发布新版本前运行`CNPDK_regression.py`。

---

## English Version

### 1. What DRC Does

DRC stands for Design Rule Check. It verifies whether the drawn layout geometry satisfies the defined manufacturing-style constraints.

It checks items such as minimum width, minimum spacing, contact and via size, metal enclosure, implant coverage, and device-marker relationships.

DRC checks geometry only. A zero-marker result does not prove that the electrical circuit is correct; connectivity and device matching are verified by LVS.

> The CNPDK rules are intended for personal Mini-PDK development and workflow learning. They are not foundry sign-off rules.

---

### 2. Rule Deck and Execution

The integrated DRC deck is stored in:

```text
CNPDK/drc/
```

Recommended release filename:

```text
CNPDK_complete_DRC.lydrc
```

Save the GDS, select the correct top cell, open the DRC deck, press `Shift+F5`, and inspect the result in Marker Database Browser.

---

### 3. Error Numbering

The naming format is:

```text
group.rule_LAYER.RULE_NAME
```

For example, `7.2_M1.MIN_SPACE` is the second rule in the Metal1 group.

Rules belonging to the same drawn layer are kept together. SAB and FuseTop currently have no independent global checks; their device-specific checks are reported under RES_MK and CAP_MK.

---

### 4. Input and Derived Layers

The main input layers are N-Well `21/0`, Active `22/0`, Poly `30/0`, P+ `31/0`, N+ `32/0`, Contact `33/0`, M1 `34/0`, Via1 `35/0`, M2 `36/0`, Via2 `38/0`, M3 `42/0`, SAB `49/0`, FuseTop `75/0`, Resistor Mark `110/5`, and Capacitor Mark `117/5`.

The rule deck derives logical regions such as MOS gates, Active contacts, Poly contacts, resistor Poly, MIM plates, and normal Via2. These are calculated regions, not additional GDS layers.

---

### 5. Complete Rule Summary

#### N-Well

| ID | Check | Minimum |
|---|---|---:|
| 1.1 | N-Well width | 0.86 µm |
| 1.2 | N-Well spacing | 0.60 µm |
| 1.3 | N-Well enclosure of PMOS P+ Active | 0.43 µm |
| 1.4 | N-Well enclosure of N+ Well Tap | 0.12 µm |

#### Active

| ID | Check | Minimum/Requirement |
|---|---|---:|
| 2.1 | Active width | 0.22 µm |
| 2.2 | Active spacing | 0.28 µm |
| 2.3 | Active covered by N+ or P+ Implant | Required |

#### Poly and Gate

| ID | Check | Minimum/Requirement |
|---|---|---:|
| 3.1 | Poly width | 0.18 µm |
| 3.2 | Poly spacing | 0.24 µm |
| 3.3 | NMOS gate length | 0.28 µm |
| 3.4 | PMOS gate length | 0.28 µm |
| 3.5 | Active Contact to gate spacing | 0.15 µm |
| 3.6 | Poly Contact to Active spacing | 0.17 µm |
| 3.7 | Contact on an active MOS gate | Forbidden |

Device identity belongs to LVS, so the old `MOS.GATE.UNDEFINED` check is not used.

#### N+ Implant

| ID | Check | Minimum/Requirement |
|---|---|---:|
| 4.1 | N+ width | 0.40 µm |
| 4.2 | N+ spacing | 0.40 µm |
| 4.3 | N+ enclosure of NMOS Active | 0.16 µm |
| 4.4 | N+ enclosure of N-Well Tap Active | 0.16 µm |
| 4.5 | N+ enclosure of NMOS gate | 0.23 µm |
| 4.6 | N+ overlapping P+ | Forbidden |

#### P+ Implant

| ID | Check | Minimum |
|---|---|---:|
| 5.1 | P+ width | 0.40 µm |
| 5.2 | P+ spacing | 0.40 µm |
| 5.3 | P+ enclosure of PMOS Active | 0.16 µm |
| 5.4 | P+ enclosure of P-Substrate Tap | 0.16 µm |
| 5.5 | P+ enclosure of PMOS gate | 0.23 µm |

#### Contact

| ID | Check | Minimum/Requirement |
|---|---|---:|
| 6.1 | Contact size | 0.22 µm |
| 6.2 | Contact spacing | 0.25 µm |
| 6.3 | Active or Poly below Contact | Required |
| 6.4 | One Contact touching both Active and Poly | Forbidden |
| 6.5 | Active enclosure of Contact | 0.07 µm |
| 6.6 | Poly enclosure of Contact | 0.07 µm |

#### Metal1 and Via1

| ID | Check | Minimum |
|---|---|---:|
| 7.1 | M1 width | 0.23 µm |
| 7.2 | M1 spacing | 0.23 µm |
| 7.3 | M1 enclosure of Contact | 0.06 µm |
| 7.4 | M1 enclosure of Via1 | 0.06 µm |
| 8.1 | Via1 size | 0.26 µm |
| 8.2 | Via1 spacing | 0.26 µm |

#### Metal2, Via2, and Metal3

| ID | Check | Minimum |
|---|---|---:|
| 9.1 | M2 width | 0.28 µm |
| 9.2 | M2 spacing | 0.28 µm |
| 9.3 | M2 enclosure of Via1 | 0.06 µm |
| 9.4 | M2 enclosure of normal Via2 | 0.06 µm |
| 10.1 | Via2 size | 0.26 µm |
| 10.2 | Via2 spacing | 0.26 µm |
| 11.1 | M3 width | 0.28 µm |
| 11.2 | M3 spacing | 0.28 µm |
| 11.3 | M3 enclosure of normal Via2 | 0.06 µm |

Not every Via2 is required to lie inside FuseTop. Ordinary M2–M3 Via2 and MIM top-plate Via2 are handled separately.

#### RES_MK Resistor Rules

| ID | Check | Minimum/Requirement |
|---|---|---:|
| 13.1 | RES_MK-defined Poly width | 0.80 µm |
| 13.2 | Resistor Poly spacing | 0.40 µm |
| 13.3 | Resistor region to Active | 0.60 µm |
| 13.4 | Resistor region to unrelated Poly | 0.60 µm |
| 13.5 | P+ enclosure of resistor region | 0.30 µm |
| 13.6 | RES_MK covered by Poly | Required |
| 13.7 | RES_MK inside SAB | Required |
| 13.8 | SAB to terminal Contact | 0.22 µm |

These checks are triggered by Resistor Mark, so ordinary Poly is not treated as resistor Poly. A former orientation-specific SAB rule was removed to allow rotated resistors.

#### CAP_MK MIM Rules

| ID | Check | Minimum/Requirement |
|---|---|---:|
| 15.1 | CAP_MK coincident with FuseTop | Required |
| 15.2 | FuseTop size | 5.00 µm × 5.00 µm |
| 15.3 | FuseTop spacing | 0.60 µm |
| 15.4 | M2 enclosure of MIM top plate | 0.60 µm |
| 15.5 | MIM bottom plate to unrelated M2 | 1.20 µm |
| 15.6 | MIM top Via2 spacing | 0.50 µm |
| 15.7 | FuseTop enclosure of MIM Via2 | 0.40 µm |
| 15.8 | M3 enclosure of MIM Via2 | 0.12 µm |

“Unrelated M2” means an M2 shape that is not part of the current MIM bottom plate.

---

### 6. Understanding Common Errors

- `MIN_WIDTH`: widen the reported shape.
- `MIN_SPACE`: move or shorten one shape, or correctly merge shapes that belong to the same net.
- `ENC`: enlarge the enclosing layer or move the cut inward.
- `NO_BOTTOM_LAYER`: place the Contact on valid Active or Poly.
- `ACTIVE.NO_IMPLANT`: add the correct N+ or P+ coverage.
- `CAP_MK.M2.SPACE.UNRELATED_M2`: move unrelated M2 routing away from the MIM device.

Do not remove a rule only to make a marker disappear. First determine whether the problem is a false positive or an actual layout defect.

---

### 7. Maintenance Principles

- Organize general checks by drawn layer.
- Trigger device-specific checks with Resistor Mark or Capacitor Mark.
- Keep electrical device identity in LVS rather than DRC.
- Add both legal and illegal test layouts for every new rule.
- Run the PCell sweep and integrated DRC after changing a PCell.
- Run `CNPDK_regression.py` before releasing a new version.

