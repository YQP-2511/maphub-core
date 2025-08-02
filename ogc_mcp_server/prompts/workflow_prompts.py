"""地理数据可视化工作流提示词模块

基于FastMCP最佳实践设计的核心提示词模板，引导AI正确使用多图层可视化工具。
强调数据发现优先原则，让AI自主选择WMS、WFS或WMTS服务类型，实现灵活的图层组合。
AI必须自动进行数据查询和可视化，不询问用户是否需要可视化。
"""

import logging
from fastmcp import FastMCP
from pydantic import Field
from typing_extensions import Annotated

logger = logging.getLogger(__name__)

# 创建工作流提示词子服务器
workflow_prompts_server = FastMCP(name="地理数据可视化工作流")


@workflow_prompts_server.prompt(
    name="geo_visualization_workflow",
    description="地理数据可视化核心工作流程，AI必须自动进行数据查询和可视化，不询问用户",
    tags={"visualization", "workflow", "geospatial", "multi-layer", "ai-driven", "wmts", "auto-visualization"}
)
def geo_visualization_workflow(
    analysis_goal: Annotated[str, Field(description="分析目标，如：查看某地区的人口分布、分析土地利用情况等")],
    target_region: Annotated[str, Field(description="目标区域，如：北京市、长江流域、全国等")] = "不限定区域",
    data_types: Annotated[str, Field(description="期望的数据类型，如：底图、人口数据、交通网络等")] = "相关的所有数据类型"
) -> str:
    """地理数据可视化核心工作流程
    
    这是标准化的地理数据可视化工作流程，AI必须自动执行数据发现、图层选择、
    可视化创建的完整流程。不要询问用户是否需要可视化，直接一气呵成完成整个流程。
    请使用该MCP服务提供的工具，用户的一切需求都需要从该服务的工具中获取。
    """
    
    return f"""# 🗺️ 地理数据可视化核心工作流

## 🎯 任务目标
**分析目标**：{analysis_goal}
**目标区域**：{target_region}  
**数据需求**：{data_types}

---

## ⚠️ 重要指导原则

### 🚀 AI自动执行原则
**AI必须自动完成以下流程，不要询问用户是否需要可视化：**
1. **自动发现数据** - 使用数据发现工具查找相关图层
2. **自动选择图层** - 根据分析目标智能选择合适的图层和服务类型
3. **自动创建可视化** - 直接创建可视化，不询问用户意见
4. **一气呵成** - 从数据查询到可视化展示一次性完成

### 🎯 核心工作模式
**数据发现优先 + AI智能选择服务类型 + 自动可视化创建**
在进行任何可视化操作之前，必须通过数据发现了解所有可用资源！然后根据数据特性和分析需求智能选择WMS、WFS或WMTS服务，最后自动创建可视化。

---

## 🔧 可用工具清单

### 📊 管理工具（Management Tools）
- `mgmt_list_layers_from_resource` - 获取完整图层清单

### 🎨 可视化工具（Visualization Tools）
- `wms_add_wms_layer` - 添加WMS图层（栅格/底图）
- `wfs_add_wfs_layer` - 添加WFS图层（矢量/要素）
- `wmts_add_wmts_layer` - 添加WMTS图层（瓦片地图）
- `viz_create_composite_visualization` - 创建复合可视化（自动应用智能中心点）
- `viz_clear_visualization_layers` - 清空当前可视化图层
- `viz_list_current_layers` - 列出当前已添加的图层
---

### 🔍 阶段一：全面数据资源发现（强制执行）

#### 步骤1：获取完整图层清单
**使用 `mgmt_list_layers_from_resource` 工具**：
   - 查看当前可用的图层资源
   - 识别与{target_region}和{analysis_goal}相关的图层
   - 注意图层的服务类型（WMS、WFS、WMTS）

#### 步骤2：分析图层特性和用途
**对于每个相关图层，分析其特性**：

1. **WMS图层特点**：
   - 适合底图、栅格数据、大范围地理背景
   - 快速加载，适合作为空间参考
   - 不支持属性查询，主要用于视觉展示

2. **WFS图层特点**：
   - 适合矢量数据、属性查询、精确要素分析
   - 支持属性过滤和交互式查询
   - 数据量建议控制在1000个要素以内

3. **WMTS图层特点**：
   - 高性能瓦片底图，预渲染数据
   - 多尺度地图可视化，缓存优化
   - 适合作为高质量底图和背景图层



---

### 🎨 阶段二：智能图层选择和添加

#### 步骤1：清空图层列表（开始新可视化）
**使用 `viz_clear_visualization_layers` 工具**：
   - 清除之前的图层，确保干净的开始

#### 步骤2：根据分析需求智能添加图层

**🗺️ 添加底图图层（推荐优先级：WMTS > WMS）**：

**选择WMTS的情况**：
- 需要高质量、多尺度的底图
- 对加载性能要求较高
- 作为主要的地理背景参考
- **使用 `wmts_add_wmts_layer` 工具**
- 可选参数：tile_matrix_set（瓦片矩阵集）、style（样式）、format（格式）

**选择WMS的情况**：
- 需要动态渲染的底图
- 对底图有特殊样式要求
- WMTS不可用时的备选方案
- **使用 `wms_add_wms_layer` 工具**

**📊 添加专题数据图层（根据需求选择）**：

**选择WFS的情况**：
- 需要查看具体要素属性
- 需要精确的矢量边界
- 数据量不大（建议<1000个要素）
- 需要交互式查询和属性过滤
- **使用 `wfs_add_wfs_layer` 工具**
- 重要参数：max_features（控制数据量）、property_filters（属性过滤）

**选择WMS的情况**：
- 数据量很大（>1000个要素）
- 主要关注空间分布模式
- 需要快速加载和显示
- 作为背景参考图层
- **使用 `wms_add_wms_layer` 工具**

**选择WMTS的情况**：
- 预渲染的专题数据
- 需要多尺度展示的数据
- 对性能要求极高的场景
- **使用 `wmts_add_wmts_layer` 工具**

#### 步骤3：检查当前图层状态
**使用 `viz_list_current_layers` 工具**：
   - 确认已添加的图层
   - 检查图层类型和数量
   - 验证图层配置是否正确

---

### 🎨 阶段三：自动创建复合可视化（强制执行）

#### 选择可视化类型并直接创建：

**叠加显示（overlay）**：
- 多个图层在同一地图上叠加显示
- 适合分析图层间的空间关系
- **使用 `viz_create_composite_visualization` 工具**，设置 `visualization_type="overlay"`

**对比显示（comparison）**：
- 每个图层单独显示，便于对比
- 适合比较不同图层的特征
- **使用 `viz_create_composite_visualization` 工具**，设置 `visualization_type="comparison"`

**重要提示**：
- 可视化工具已集成智能中心点计算，会自动应用优化的中心点和缩放级别
- 不需要单独调用中心点工具，直接创建可视化即可

---

### 📊 阶段四：结果分析和解读

1. **访问生成的可视化页面**
2. **分析可视化结果**
3. **提供分析总结**
4. **解释可视化内容和发现**

---

## 🧠 AI决策指南

### 服务类型选择策略：

**优先使用WMTS的场景**：
- 底图和高质量背景图层
- 需要多尺度显示的数据
- 对性能要求很高的场景
- 预渲染的地图数据

**优先使用WMS的场景**：
- 需要动态渲染的图层
- 大数据量图层（>1000要素）
- 栅格数据和影像数据
- WMTS不可用时的备选方案

**优先使用WFS的场景**：
- 需要属性信息的矢量数据
- 小到中等数据量（<1000要素）
- 需要精确边界的图层
- 交互式分析和属性查询需求

### 图层组合建议：
- **高性能组合**：WMTS底图 + WFS专题数据
- **标准组合**：WMS底图 + WFS专题数据  
- **大数据组合**：WMTS底图 + WMS专题数据
- **对比分析**：多个WFS图层 + WMTS底图

### 完整工具使用顺序（必须按顺序执行）：
1. `mgmt_list_layers_from_resource` - 发现数据
2. `viz_clear_visualization_layers` - 清空列表
3. `wmts_add_wmts_layer` / `wms_add_wms_layer` / `wfs_add_wfs_layer` - 添加图层（可多次调用）
4. `viz_list_current_layers` - 检查状态
5. `viz_create_composite_visualization` - 创建可视化（自动应用智能中心点）

---

## ✅ 成功标准
- 数据发现完整
- 服务类型选择合理
- 图层组合有意义
- 自动创建可视化
- 中心点和缩放级别合适
- 可视化结果清晰
- 分析目标达成

## 🚀 核心特性
- **自动化流程**：从数据发现到可视化创建全自动
- **智能中心点**：自动解决多图层叠加的视图焦点问题
- **完整工具链**：从数据发现到可视化创建的全流程支持
- **一气呵成**：不询问用户，直接完成整个可视化流程

现在请开始执行这个工作流程！根据{analysis_goal}的具体需求，智能选择合适的图层和服务类型，并自动创建可视化展示。记住：不要询问用户是否需要可视化，直接执行完整流程！"""


@workflow_prompts_server.prompt(
    name="layer_selection_guide",
    description="图层选择指导提示词，帮助AI根据数据特性选择合适的服务类型，支持WMS/WFS/WMTS三种服务",
    tags={"selection", "guidance", "wms", "wfs", "wmts"}
)
def layer_selection_guide(
    layer_name: Annotated[str, Field(description="图层名称")],
    analysis_purpose: Annotated[str, Field(description="分析目的")] = "一般可视化"
) -> str:
    """图层选择指导提示词"""
    
    return f"""# 🎯 图层选择指导：{layer_name}

## 分析目的：{analysis_purpose}

---

## 🤔 服务类型选择决策

### 选择WMTS的情况：
✅ **需要高性能瓦片底图**
✅ **预渲染的地图数据**
✅ **多尺度地图可视化需求**
✅ **缓存优化的地图服务**
✅ **对加载速度要求极高**
✅ **作为高质量底图或背景**

### 选择WMS的情况：
✅ **适合作为底图或背景图层**
✅ **数据量很大（>1000个要素）**
✅ **主要关注空间分布模式**
✅ **需要动态渲染的图层**
✅ **栅格数据或影像数据**
✅ **作为空间参考背景**

### 选择WFS的情况：
✅ **需要查看具体要素的属性信息**
✅ **需要精确的矢量边界**
✅ **数据量适中（<1000个要素）**
✅ **需要交互式查询和分析**
✅ **矢量数据且关注要素细节**
✅ **需要进行属性统计分析**
✅ **支持属性过滤和CQL查询**

---

## 🛠️ 推荐操作：

1. **首先使用 `mgmt_list_layers_from_resource` 查看图层 {layer_name} 的详细信息**

2. **根据图层的服务类型（WMS/WFS/WMTS）和你的分析目的选择**

3. **根据上述指导原则选择最适合的服务类型**

4. **使用相应的工具添加图层：**
   - WMTS: `wmts_add_wmts_layer` - 高性能瓦片地图
   - WMS: `wms_add_wms_layer` - 栅格图像服务
   - WFS: `wfs_add_wfs_layer` - 矢量要素服务

5. **直接创建可视化（不询问用户）：**
   - `viz_create_composite_visualization` - 自动应用智能中心点

---

## 💡 最佳实践建议：

### 底图选择优先级：
1. **WMTS** - 最佳性能和视觉效果
2. **WMS** - 动态渲染，灵活性高
3. **WFS** - 仅在需要底图要素属性时使用

### 专题数据选择：
- **小数据量（<100要素）**：优先WFS
- **中等数据量（100-1000要素）**：WFS或WMS根据需求
- **大数据量（>1000要素）**：优先WMS或WMTS

### 组合建议：
- **高性能组合**：WMTS底图 + WFS专题数据
- **标准组合**：WMS底图 + WFS专题数据
- **大数据组合**：WMTS底图 + WMS专题数据

记住：没有标准答案，要根据具体的分析需求、数据特性和性能要求做出最佳选择！选择完成后直接创建可视化，不要询问用户！"""


@workflow_prompts_server.prompt(
    name="auto_visualization_guide",
    description="自动可视化指导提示词，强调AI必须自动完成整个可视化流程",
    tags={"auto-visualization", "workflow", "mandatory"}
)
def auto_visualization_guide(
    task_type: Annotated[str, Field(description="任务类型")] = "数据查询和可视化"
) -> str:
    """自动可视化指导提示词"""
    
    return f"""# 🚀 自动可视化执行指导

## 任务类型：{task_type}

---

## ⚠️ 强制执行原则

### 🎯 AI必须自动执行以下流程：

1. **数据发现阶段**：
   - 使用 `mgmt_list_layers_from_resource` 自动发现所有相关数据
   - 分析图层特性和适用场景
   - 不询问用户要查看哪些数据

2. **图层选择阶段**：
   - 根据分析目标智能选择合适的图层
   - 自动决定使用WMS、WFS还是WMTS服务
   - 不询问用户偏好，直接做出最佳选择

3. **可视化创建阶段**：
   - 自动添加选定的图层
   - 直接创建复合可视化
   - 不询问用户是否需要可视化

4. **结果展示阶段**：
   - 提供可视化链接
   - 分析可视化结果
   - 解释发现和洞察

---

## 🚫 禁止的行为

### 不要询问用户：
- ❌ "您是否需要可视化这些数据？"
- ❌ "您希望查看哪些图层？"
- ❌ "您偏好哪种可视化类型？"
- ❌ "是否需要创建地图？"

### 正确的做法：
- ✅ 直接发现数据并分析
- ✅ 智能选择最合适的图层
- ✅ 自动创建可视化
- ✅ 提供分析结果和洞察

---

## 🎯 标准执行模板

```

### 场景2：世界地图 + 美国州数据 + 城市点数据
```
target_layer_hint="州数据"
exclude_global_layers=True prefer_vector_data=True

```

### 场景3：多个矢量图层组合
```
target_layer_hint="主要数据"
exclude_global_layers=False
prefer_vector_data=True

```

---

## ✅ 预期效果：

使用智能中心点判断后，您将获得：
- **精确的中心点坐标**
- **合适的缩放级别**
- **优化的边界框**
- **详细的推理过程**
- **图层重要性分析**

这将确保可视化结果能够聚焦到真正重要的数据区域，而不是被全球范
围的底图所影响。

---

## 🚀 工作流程建议：

1. 添加所有需要的图层
2. 使用 `viz_list_current_layers` 检查图层状态
3. 使用 `viz_create_composite_visualization` 创建可视
化
## 🎯 标准执行模板
1. 正在发现相关数据...
2. 找到X个相关图层，分析特性...
3. 选择最适合的图层组合...
4. 创建可视化展示...
5. 可视化创建完成！访问链接：[URL]
6. 分析结果：[洞察和发现]

---

## ✅ 成功标准

- 用户提出需求后，AI立即开始执行
- 不询问任何确认问题
- 自动完成从数据发现到可视化的全流程
- 提供有价值的分析结果和洞察
- 整个过程一气呵成，用户体验流畅

记住：用户的需求就是要进行数据查询和可视化，不需要再次确认！"""