"""地理数据可视化工作流提示词模块

基于FastMCP最佳实践设计的核心提示词模板，引导AI正确使用多图层可视化工具。
强调数据发现优先原则，让AI自主选择WMS或WFS服务类型，实现灵活的图层组合。
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
    description="地理数据可视化核心工作流程，强调数据发现优先和AI自主选择服务类型",
    tags={"visualization", "workflow", "geospatial", "multi-layer", "ai-driven"}
)
def geo_visualization_workflow(
    analysis_goal: Annotated[str, Field(description="分析目标，如：查看某地区的人口分布、分析土地利用情况等")],
    target_region: Annotated[str, Field(description="目标区域，如：北京市、长江流域、全国等")] = "不限定区域",
    data_types: Annotated[str, Field(description="期望的数据类型，如：底图、人口数据、交通网络等")] = "相关的所有数据类型"
) -> str:
    """地理数据可视化核心工作流程
    
    这是标准化的地理数据可视化工作流程，集成了数据发现、AI自主服务选择、
    多图层组合和可视化创建的完整流程。让AI根据数据特性智能选择WMS或WFS服务。
    """
    
    return f"""# 🗺️ 地理数据可视化核心工作流

## 🎯 任务目标
**分析目标**：{analysis_goal}
**目标区域**：{target_region}  
**数据需求**：{data_types}

---

## 📋 标准执行流程

### ⚠️ 核心原则：数据发现优先 + AI智能选择服务类型
**在进行任何可视化操作之前，必须通过数据发现了解所有可用资源！然后根据数据特性和分析需求智能选择WMS或WFS服务。**

---

### 🔍 阶段一：全面数据资源发现（强制执行）

#### 步骤1：获取完整图层清单
**使用 `list_layers_from_resource` 工具**：
   - 查看当前可用的图层资源
   - 识别与{target_region}和{analysis_goal}相关的图层
   - 注意图层的服务类型（WMS、WFS、BOTH）

#### 步骤2：分析图层特性和用途
**对于每个相关图层，分析其特性**：
1. **WMS图层特点**：适合底图、栅格数据、大范围地理背景
2. **WFS图层特点**：适合矢量数据、属性查询、精确要素分析
3. **BOTH类型图层**：可以选择WMS或WFS，根据具体需求决定

---

### 🎨 阶段二：智能图层选择和添加

#### 步骤1：清空图层列表（开始新可视化）
**使用 `clear_visualization_layers` 工具**：
   - 清除之前的图层，确保干净的开始

#### 步骤2：根据分析需求智能添加图层

**🗺️ 添加底图图层（推荐使用WMS）**：
- **使用 `add_wms_layer` 工具**添加底图
- 选择合适的底图图层（如行政区划、地形图等）
- WMS适合提供地理背景和空间参考

**📊 添加专题数据图层（根据需求选择）**：

**选择WFS的情况**：
- 需要查看具体要素属性
- 需要精确的矢量边界
- 数据量不大（建议<1000个要素）
- 需要交互式查询
- **使用 `add_wfs_layer` 工具**，设置合适的max_features

**选择WMS的情况**：
- 数据量很大
- 主要关注空间分布模式
- 需要快速加载和显示
- 作为背景参考图层
- **使用 `add_wms_layer` 工具**

#### 步骤3：检查当前图层状态
**使用 `list_current_layers` 工具**：
   - 确认已添加的图层
   - 检查图层类型和数量

---

### 🎯 阶段三：创建复合可视化

#### 选择可视化类型：

**叠加显示（overlay）**：
- 多个图层在同一地图上叠加显示
- 适合分析图层间的空间关系
- **使用 `create_composite_visualization` 工具**，设置 `visualization_type="overlay"`

**对比显示（comparison）**：
- 每个图层单独显示，便于对比
- 适合比较不同图层的特征
- **使用 `create_composite_visualization` 工具**，设置 `visualization_type="comparison"`

---

### 📊 阶段四：结果分析和解读

1. **访问生成的可视化页面**
2. **分析可视化结果**
3. **提供分析总结**

---

## 🧠 AI决策指南

### 服务类型选择策略：

**优先使用WMS的场景**：
- 底图和背景图层
- 大数据量图层（>1000要素）
- 栅格数据
- 需要快速加载的图层

**优先使用WFS的场景**：
- 需要属性信息的矢量数据
- 小到中等数据量（<1000要素）
- 需要精确边界的图层
- 交互式分析需求

**图层组合建议**：
- 底图（WMS）+ 专题数据（WFS）
- 多个WMS图层叠加
- 根据分析目标灵活组合

### 工具使用顺序：
1. `list_layers_from_resource` - 发现数据
2. `clear_visualization_layers` - 清空列表
3. `add_wms_layer` / `add_wfs_layer` - 添加图层（可多次调用）
4. `list_current_layers` - 检查状态
5. `create_composite_visualization` - 创建可视化

---

## ✅ 成功标准
- 数据发现完整
- 服务类型选择合理
- 图层组合有意义
- 可视化结果清晰
- 分析目标达成

现在请开始执行这个工作流程！根据{analysis_goal}的具体需求，智能选择合适的图层和服务类型。"""


@workflow_prompts_server.prompt(
    name="layer_selection_guide",
    description="图层选择指导提示词，帮助AI根据数据特性选择合适的服务类型",
    tags={"selection", "guidance", "wms", "wfs"}
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

### 选择WMS的情况：
✅ **适合作为底图或背景图层**
✅ **数据量很大（>1000个要素）**
✅ **主要关注空间分布模式**
✅ **需要快速加载和显示**
✅ **栅格数据或影像数据**
✅ **作为空间参考背景**

### 选择WFS的情况：
✅ **需要查看具体要素的属性信息**
✅ **需要精确的矢量边界**
✅ **数据量适中（<1000个要素）**
✅ **需要交互式查询和分析**
✅ **矢量数据且关注要素细节**
✅ **需要进行属性统计分析**

---

## 🛠️ 推荐操作：

1. **首先使用 `list_layers_from_resource` 查看图层 {layer_name} 的详细信息**
2. **根据图层的服务类型（WMS/WFS/BOTH）和你的分析目的选择**
3. **如果是BOTH类型，根据上述指导原则选择最适合的服务类型**
4. **使用相应的工具添加图层：**
   - WMS: `add_wms_layer`
   - WFS: `add_wfs_layer`

记住：没有标准答案，要根据具体的分析需求和数据特性做出最佳选择！"""


