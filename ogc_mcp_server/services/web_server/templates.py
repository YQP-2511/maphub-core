"""Web模板模块

提供Web页面模板生成功能
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class WebTemplates:
    """Web模板生成器"""
    
    def generate_index_page(self, visualizations: Dict[str, Any], 
                           server_info: Dict[str, Any]) -> str:
        """生成首页HTML
        
        Args:
            visualizations: 可视化列表
            server_info: 服务器信息
            
        Returns:
            首页HTML内容
        """
        # 统计信息
        total_viz = len(visualizations)
        wms_count = len([v for v in visualizations.values() if v['type'] == 'wms'])
        geojson_count = len([v for v in visualizations.values() if v['type'] == 'geojson'])
        
        # 生成可视化列表HTML
        viz_list_html = ""
        if visualizations:
            viz_list_html = "<div class='visualization-grid'>"
            for viz_id, viz_info in visualizations.items():
                viz_list_html += self._generate_viz_card(viz_id, viz_info)
            viz_list_html += "</div>"
        else:
            viz_list_html = """
            <div class='empty-state'>
                <div class='empty-icon'>🗺️</div>
                <h3>暂无可视化内容</h3>
                <p>使用MCP工具生成地图可视化后，结果将在这里显示</p>
            </div>
            """
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OGC Web可视化服务器</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }}
        
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-2px);
        }}
        
        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #3498db;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .section-title {{
            font-size: 1.8em;
            color: #2c3e50;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
        }}
        
        .visualization-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .viz-card {{
            background: white;
            border: 1px solid #e1e8ed;
            border-radius: 8px;
            overflow: hidden;
            transition: all 0.3s;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .viz-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }}
        
        .viz-header {{
            padding: 20px;
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
        }}
        
        .viz-type {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        
        .viz-title {{
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .viz-subtitle {{
            opacity: 0.9;
            font-size: 0.9em;
        }}
        
        .viz-body {{
            padding: 20px;
        }}
        
        .viz-info {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .info-item {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            border-left: 3px solid #3498db;
        }}
        
        .info-label {{
            font-size: 0.8em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }}
        
        .info-value {{
            font-weight: bold;
            color: #2c3e50;
        }}
        
        .viz-actions {{
            display: flex;
            gap: 10px;
        }}
        
        .btn {{
            flex: 1;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            text-decoration: none;
            text-align: center;
            font-weight: bold;
            transition: all 0.2s;
            cursor: pointer;
        }}
        
        .btn-primary {{
            background: #3498db;
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #2980b9;
        }}
        
        .btn-secondary {{
            background: #95a5a6;
            color: white;
        }}
        
        .btn-secondary:hover {{
            background: #7f8c8d;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }}
        
        .empty-icon {{
            font-size: 4em;
            margin-bottom: 20px;
        }}
        
        .empty-state h3 {{
            font-size: 1.5em;
            margin-bottom: 10px;
            color: #2c3e50;
        }}
        
        .footer {{
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 20px;
            margin-top: 40px;
        }}
        
        .api-info {{
            background: #e8f4fd;
            border: 1px solid #bee5eb;
            border-radius: 8px;
            padding: 20px;
            margin-top: 30px;
        }}
        
        .api-title {{
            color: #0c5460;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .api-url {{
            background: #d1ecf1;
            padding: 8px 12px;
            border-radius: 4px;
            font-family: monospace;
            color: #0c5460;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌍 OGC Web可视化服务器</h1>
            <p>统一的地理空间数据可视化平台</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{total_viz}</div>
                <div class="stat-label">总可视化</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{wms_count}</div>
                <div class="stat-label">WMS地图</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{geojson_count}</div>
                <div class="stat-label">GeoJSON地图</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{server_info['port']}</div>
                <div class="stat-label">服务端口</div>
            </div>
        </div>
        
        <div class="content">
            <h2 class="section-title">📊 可视化内容</h2>
            {viz_list_html}
            
            <div class="api-info">
                <div class="api-title">🔗 API接口</div>
                <div class="api-url">{server_info['base_url']}/api/visualizations</div>
            </div>
        </div>
        
        <div class="footer">
            <p>© 2024 OGC MCP服务器 | 地理空间数据可视化平台</p>
        </div>
    </div>
    
    <script>
        // 自动刷新页面（每30秒）
        setTimeout(function() {{
            location.reload();
        }}, 30000);
        
        // 添加一些交互效果
        document.addEventListener('DOMContentLoaded', function() {{
            console.log('OGC Web可视化服务器已加载');
        }});
    </script>
</body>
</html>"""
        
        return html_content
    
    def _generate_viz_card(self, viz_id: str, viz_info: Dict[str, Any]) -> str:
        """生成可视化卡片HTML
        
        Args:
            viz_id: 可视化ID
            viz_info: 可视化信息
            
        Returns:
            卡片HTML
        """
        viz_type = viz_info['type'].upper()
        layer_name = viz_info['layer_name']
        layer_info = viz_info['layer_info']
        created_time = datetime.fromtimestamp(viz_info['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        
        # 根据类型设置不同的样式
        type_color = "#3498db" if viz_type == "WMS" else "#27ae60"
        type_icon = "🗺️" if viz_type == "WMS" else "📍"
        
        # 获取统计信息
        stats_html = ""
        if viz_type == "GEOJSON" and 'geojson_stats' in viz_info:
            stats = viz_info['geojson_stats']
            stats_html = f"""
            <div class="info-item">
                <div class="info-label">要素数量</div>
                <div class="info-value">{stats.get('feature_count', 0)}</div>
            </div>
            <div class="info-item">
                <div class="info-label">几何类型</div>
                <div class="info-value">{', '.join(stats.get('geometry_types', []))}</div>
            </div>
            """
        else:
            stats_html = f"""
            <div class="info-item">
                <div class="info-label">服务类型</div>
                <div class="info-value">{viz_type}</div>
            </div>
            <div class="info-item">
                <div class="info-label">坐标系</div>
                <div class="info-value">{layer_info.get('crs', 'EPSG:4326')}</div>
            </div>
            """
        
        return f"""
        <div class="viz-card">
            <div class="viz-header" style="background: linear-gradient(135deg, {type_color}, {type_color}dd);">
                <div class="viz-type">{type_icon} {viz_type}</div>
                <div class="viz-title">{layer_info.get('layer_title', layer_name)}</div>
                <div class="viz-subtitle">{layer_info.get('service_name', 'N/A')}</div>
            </div>
            <div class="viz-body">
                <div class="viz-info">
                    {stats_html}
                    <div class="info-item">
                        <div class="info-label">创建时间</div>
                        <div class="info-value">{created_time}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">图层名称</div>
                        <div class="info-value">{layer_name}</div>
                    </div>
                </div>
                <div class="viz-actions">
                    <a href="{viz_info['url']}" class="btn btn-primary" target="_blank">
                        🔍 查看地图
                    </a>
                    <button class="btn btn-secondary" onclick="copyUrl('{viz_info['url']}')">
                        📋 复制链接
                    </button>
                </div>
            </div>
        </div>
        
        <script>
        function copyUrl(url) {{
            navigator.clipboard.writeText(url).then(function() {{
                alert('链接已复制到剪贴板');
            }});
        }}
        </script>
        """