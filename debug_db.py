"""
调试脚本 - 检查数据库中的图层数据
"""

import asyncio
import aiosqlite
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from collections import defaultdict

async def debug_database():
    """调试数据库中的图层数据"""
    db_path = Path("data/ogc_layers.db")
    
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as conn:
        # 查询总数
        cursor = await conn.execute("SELECT COUNT(*) as total FROM layer_resources")
        total_result = await cursor.fetchone()
        total_count = total_result[0] if total_result else 0
        
        print(f"数据库中总图层数: {total_count}")
        
        # 按服务类型统计
        cursor = await conn.execute("""
            SELECT service_type, COUNT(*) as count 
            FROM layer_resources 
            GROUP BY service_type
        """)
        type_stats = await cursor.fetchall()
        
        print("\n按服务类型统计:")
        for service_type, count in type_stats:
            print(f"  {service_type}: {count}")
        
        # 查询所有图层的详细信息（包括URL）
        cursor = await conn.execute("""
            SELECT resource_id, service_name, service_url, service_type, layer_name, layer_title
            FROM layer_resources 
            ORDER BY service_name, service_type, layer_name
        """)
        all_layers = await cursor.fetchall()
        
        print(f"\n所有图层详情 (共{len(all_layers)}个):")
        for i, (resource_id, service_name, service_url, service_type, layer_name, layer_title) in enumerate(all_layers, 1):
            print(f"{i:2d}. [{service_type}] {service_name} - {layer_name}")
            print(f"     资源ID: {resource_id}")
            print(f"     服务URL: {service_url}")
            if layer_title:
                print(f"     标题: {layer_title}")
            print()
        
        # URL 格式分析
        await analyze_url_formats(conn)
        
        # 检查是否有重复的图层
        cursor = await conn.execute("""
            SELECT service_url, layer_name, service_type, COUNT(*) as count
            FROM layer_resources 
            GROUP BY service_url, layer_name, service_type
            HAVING COUNT(*) > 1
        """)
        duplicates = await cursor.fetchall()
        
        if duplicates:
            print("发现重复图层:")
            for service_url, layer_name, service_type, count in duplicates:
                print(f"  {service_type} - {layer_name}: {count} 个重复")
                print(f"    URL: {service_url}")
        else:
            print("未发现重复图层")

async def analyze_url_formats(conn):
    """分析数据库中URL的格式"""
    print("\n=== URL 格式分析 ===")
    
    # 获取所有唯一的服务URL
    cursor = await conn.execute("""
        SELECT DISTINCT service_url, service_type
        FROM layer_resources 
        ORDER BY service_url
    """)
    unique_urls = await cursor.fetchall()
    
    print(f"\n唯一服务URL数量: {len(unique_urls)}")
    
    # 按URL格式分类
    url_categories = {
        'with_query_params': [],      # 包含查询参数的URL
        'with_endpoints': [],         # 包含端点的URL
        'base_urls': [],             # 基础URL
        'potential_issues': []        # 可能有问题的URL
    }
    
    endpoint_patterns = ['/ows', '/wms', '/wfs', '/geoserver', '/mapserver', '/cgi-bin']
    
    for service_url, service_type in unique_urls:
        parsed = urlparse(service_url)
        
        # 检查是否包含查询参数
        if parsed.query:
            url_categories['with_query_params'].append((service_url, service_type, parsed.query))
        
        # 检查是否包含常见端点
        elif any(endpoint in parsed.path.lower() for endpoint in endpoint_patterns):
            url_categories['with_endpoints'].append((service_url, service_type, parsed.path))
        
        # 基础URL
        else:
            url_categories['base_urls'].append((service_url, service_type, parsed.path))
        
        # 检查潜在问题
        if not service_url.startswith(('http://', 'https://')):
            url_categories['potential_issues'].append((service_url, service_type, '不是有效的HTTP URL'))
        elif not parsed.netloc:
            url_categories['potential_issues'].append((service_url, service_type, '缺少域名'))
    
    # 输出分析结果
    print(f"\n1. 包含查询参数的URL ({len(url_categories['with_query_params'])}个):")
    for url, service_type, query in url_categories['with_query_params']:
        print(f"   [{service_type}] {url}")
        print(f"       查询参数: {query}")
    
    print(f"\n2. 包含端点的URL ({len(url_categories['with_endpoints'])}个):")
    for url, service_type, path in url_categories['with_endpoints']:
        print(f"   [{service_type}] {url}")
        print(f"       路径: {path}")
    
    print(f"\n3. 基础URL ({len(url_categories['base_urls'])}个):")
    for url, service_type, path in url_categories['base_urls']:
        print(f"   [{service_type}] {url}")
        if path and path != '/':
            print(f"       路径: {path}")
    
    if url_categories['potential_issues']:
        print(f"\n4. 潜在问题的URL ({len(url_categories['potential_issues'])}个):")
        for url, service_type, issue in url_categories['potential_issues']:
            print(f"   [{service_type}] {url}")
            print(f"       问题: {issue}")
    
    # 统计URL域名分布
    await analyze_url_domains(conn)

async def analyze_url_domains(conn):
    """分析URL的域名分布"""
    print("\n=== URL 域名分布 ===")
    
    cursor = await conn.execute("""
        SELECT DISTINCT service_url
        FROM layer_resources
    """)
    urls = await cursor.fetchall()
    
    domain_stats = defaultdict(int)
    
    for (url,) in urls:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain:
                domain_stats[domain] += 1
        except Exception as e:
            print(f"解析URL失败: {url} - {e}")
    
    print(f"\n域名统计 (共{len(domain_stats)}个不同域名):")
    for domain, count in sorted(domain_stats.items(), key=lambda x: x[1], reverse=True):
        cursor = await conn.execute("""
            SELECT COUNT(*) 
            FROM layer_resources 
            WHERE service_url LIKE ?
        """, (f'%{domain}%',))
        layer_count = (await cursor.fetchone())[0]
        print(f"  {domain}: {count} 个服务URL, {layer_count} 个图层")

async def show_url_standardization_examples():
    """显示URL标准化示例"""
    print("\n=== URL 标准化示例 ===")
    
    examples = [
        "http://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0r.cgi?service=wms&request=getcapabilities",
        "http://localhost:8090/geoserver/ows",
        "http://localhost:8090/geoserver",
        "https://ows.terrestris.de/osm/ows?service=WMS&request=GetCapabilities",
        "http://example.com/mapserver/mapserv"
    ]
    
    print("以下是不同URL格式的标准化示例:")
    for i, url in enumerate(examples, 1):
        parsed = urlparse(url)
        # 模拟标准化过程
        standardized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        standardized = standardized.rstrip('/')
        
        print(f"{i}. 原始URL: {url}")
        print(f"   标准化后: {standardized}")
        if parsed.query:
            print(f"   移除的查询参数: {parsed.query}")
        print()

if __name__ == "__main__":
    asyncio.run(debug_database())
    asyncio.run(show_url_standardization_examples())