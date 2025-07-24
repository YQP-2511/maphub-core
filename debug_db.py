"""
调试脚本 - 检查数据库中的图层数据
"""

import asyncio
import aiosqlite
from pathlib import Path

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
        
        # 查询所有图层的基本信息
        cursor = await conn.execute("""
            SELECT resource_id, service_name, service_type, layer_name, layer_title
            FROM layer_resources 
            ORDER BY service_name, service_type, layer_name
        """)
        all_layers = await cursor.fetchall()
        
        print(f"\n所有图层详情 (共{len(all_layers)}个):")
        for i, (resource_id, service_name, service_type, layer_name, layer_title) in enumerate(all_layers, 1):
            print(f"{i:2d}. [{service_type}] {service_name} - {layer_name}")
            print(f"     资源ID: {resource_id}")
            if layer_title:
                print(f"     标题: {layer_title}")
            print()
        
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
        else:
            print("未发现重复图层")

if __name__ == "__main__":
    asyncio.run(debug_database())