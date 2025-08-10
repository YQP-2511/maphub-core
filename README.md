# MapHub Core

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0+-green.svg)](https://github.com/jlowin/fastmcp)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

MapHub Core 是一个基于 FastMCP 框架构建的 OGC 服务图层管理和可视化的 MCP 服务器。它提供了完整的 WMS、WFS、WMTS 等 OGC 标准服务支持，实现图层的动态注册、管理和可视化功能。

## 🚀 项目特色

- **🏗️ 模块化架构**: 基于 FastMCP 的服务器组合模式，支持多个子服务器协同工作
- **🌐 OGC 标准支持**: 完整支持 WMS 1.3.0、WFS 2.0.0、WMTS 等 OGC 标准
- **📊 动态图层管理**: 支持图层的动态注册、查询和管理
- **🎨 可视化功能**: 内置 Web 可视化服务器，提供图层预览和交互功能
- **💾 持久化存储**: 使用 SQLite 实现图层元数据的持久化存储
- **🔄 异步处理**: 全异步架构，支持高并发访问

## 📁 项目架构
maphub/
├── 📁 ogc_mcp_server/           # 主要服务器代码
│   ├── 📁 database/             # 数据库层
│   │   ├── connection.py        # 数据库连接管理
│   │   ├── models.py           # 数据模型定义
│   │   └── repository.py       # 数据访问层
│   ├── 📁 prompts/             # 提示词模板
│   │   ├── registration_workflow_prompts.py  # 注册工作流提示词
│   │   └── workflow_prompts.py              # 通用工作流提示词
│   ├── 📁 resources/           # MCP资源
│   │   └── layer_registry.py   # 图层注册表资源
│   ├── 📁 services/            # 业务服务层
│   │   ├── layer_service.py    # 图层服务
│   │ 	├── 📁 ogc_parser.py    # OGC服务解析器功能
│   │   ├── ogc_parser.py       # OGC服务解析器功能访问入口
│   │   └── 📁 web_server/      # Web可视化服务器
│   ├── 📁 tools/               # MCP工具
│   │   ├── management_tools.py      # 管理工具
│   │   ├── visualization_tools.py   # 可视化工具
│   │   ├── wfs_layer_tool.py       # WFS图层工具
│   │   ├── wms_layer_tool.py       # WMS图层工具
│   │   └── wmts_layer_tool.py      # WMTS图层工具
│   └── server.py               # 主服务器入口
├── 📄 run_ogc_mcp_server.py    # 服务器启动脚本
├── 📄 requirements.txt         # 项目依赖
└── 📄 *.md                     # 文档文件

## 🛠️ 技术栈

### 核心框架
- **FastMCP 2.0+**: 现代化的 MCP 服务器框架
- **Python 3.8+**: 主要开发语言
- **Uvicorn**: ASGI 服务器

### OGC 服务支持
- **OWSLib 0.29.0+**: OGC 服务解析库
- **WMS 1.3.0**: Web Map Service 支持
- **WFS 2.0.0**: Web Feature Service 支持
- **WMTS**: Web Map Tile Service 支持

### 数据处理
- **SQLite + aiosqlite**: 异步数据库支持
- **Pydantic 2.0+**: 数据验证和序列化
- **HTTPX**: 异步 HTTP 客户端

### 开发工具
- **pytest**: 测试框架
- **python-dateutil**: 日期时间处理
- **orjson**: 高性能 JSON 处理

## 🚀 快速开始

### 环境要求
- Python 3.8 或更高版本
- pip 包管理器

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/YQP-2511/maphub-core.git
cd maphub-core
```

2. **创建虚拟环境**（推荐）
```bash
python -m venv venv
# Windows
venv\Scripts\activate
```

3. **安装依赖**（使用清华镜像源加速）
```bash
uv pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

4. **启动服务器**
```bash
python run_ogc_mcp_server.py
```

### 服务器配置

服务器启动后将在以下地址提供服务：
- **MCP 服务**: `http://127.0.0.1:3050/mcp`
- **传输协议**: HTTP Streamable with CORS support
- **日志文件**: `ogc_mcp_server.log`

## 📚 功能模块

### 1. 图层管理工具 (mgmt_*)
- `mgmt_register_ogc_services`: 注册 OGC 服务
- `search_and_list_geographic_data`: 搜索和列出所有地理数据图层
- `get_wfs_layer_attributes`: 获取 WFS 图层属性

### 2. WMS 图层工具 (wms_*)
- `add_wms_layer`: 添加 WMS 图层到可视化列表
- 支持栅格数据和底图可视化
- 自动获取图层边界框和坐标系信息

### 3. WFS 图层工具 (wfs_*)
- `add_wfs_layer`: 添加 WFS 图层到可视化列表
- 支持矢量数据和要素查询
- 提供属性信息和几何数据

### 4. WMTS 图层工具 (wmts_*)
- `add_wmts_layer`: 添加 WMTS 瓦片图层
- 支持高性能瓦片地图服务
- 优化的缓存和加载策略

### 5. 可视化工具 (viz_*)
- `create_composite_visualization`: 创建复合可视化地图

### 6. 图层注册表资源 (ogc://)
- `ogc://layers`: 获取所有注册的图层列表
- `ogc://layer/{layer_name}`: 获取特定图层的详细信息

## 🎯 使用示例

1. **服务注册**

   ```
   用户输入：注册["http://states/geoserver/ows"]
   AI判断要注册，调用工具register_ogc_services
   返回：注册服务的信息和解析到的部分图层信息
   ```

2. **资源查询和使用**

   ```
   用户输入：查看美国加州人口数据情况
   AI识别到目标：美国加州，调用search_and_list_geographic_data，从列表中获取可用的图层，判断并找到目标图层
   根据图层名、服务类型调用对应的添加图层工具(add_wmts_layer、add_wfs_layer、add_wms_layer)
   ```

3. **可视化展示**

   ```
   添加图层之后，AI调用create_composite_visualization工具
   返回web部署的链接    
   ```

## 🔧 配置说明

### 数据库配置
项目使用 SQLite 数据库，数据文件自动创建在项目根目录：
- 数据库文件: `ogc_layers.db`
- 支持异步操作和连接池

### 日志配置
- 控制台输出: INFO 级别
- 文件输出: `ogc_mcp_server.log`
- 支持中文编码

### CORS 配置
- 允许所有来源访问
- 支持 GET、POST、OPTIONS 方法
- 允许所有请求头

## 🐛 问题反馈

如果您遇到任何问题或有改进建议，请：

1. 查看 [已知问题](https://github.com/YQP-2511/maphub-core/issues)
2. 创建新的 [Issue](https://github.com/YQP-2511/maphub-core/issues/new)
3. 提供详细的错误信息和复现步骤

## 🙏 致谢

- [FastMCP](https://github.com/jlowin/fastmcp) - 优秀的 MCP 框架
- [OWSLib](https://github.com/geopython/OWSLib) - OGC 服务解析库
- [OGC](https://www.ogc.org/) - 开放地理空间联盟标准
- 所有为本项目做出贡献的开发者

---

⭐ **如果这个项目对您有帮助，请给我们一个星标！**

📧 **联系方式**: [GitHub Issues](https://github.com/YQP-2511/maphub-core/issues)
