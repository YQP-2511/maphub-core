"""
调试脚本 - 检查数据库中的表信息和数据内容
"""

import asyncio
import aiosqlite
from pathlib import Path

async def show_database_tables():
    """显示数据库中的表信息和数据内容"""
    db_path = Path("data/ogc_layers.db")
    
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as conn:
        # 获取所有表名
        cursor = await conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        tables = await cursor.fetchall()
        
        print(f"数据库中的表 (共{len(tables)}个):")
        print("=" * 80)
        
        for (table_name,) in tables:
            await show_table_details(conn, table_name)

async def show_table_details(conn, table_name):
    """显示单个表的详细信息和数据内容"""
    print(f"\n表名: {table_name}")
    print("-" * 60)
    
    # 获取记录数
    cursor = await conn.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = (await cursor.fetchone())[0]
    print(f"记录数: {count}")
    
    # 显示表中的数据内容
    if count > 0:
        print(f"\n表数据内容:")
        
        # 如果是layer_resources表，只显示关键字段
        if table_name == 'layer_resources':
            await show_layer_resources_data(conn)
        else:
            # 其他表显示所有字段
            await show_all_table_data(conn, table_name)
    else:
        print("表中无数据")
    
    print("\n" + "=" * 80)

async def show_layer_resources_data(conn):
    """显示layer_resources表的关键数据"""
    cursor = await conn.execute("""
        SELECT service_name, service_url, service_type, layer_name
        FROM layer_resources 
        ORDER BY service_name, service_type, layer_name
    """)
    rows = await cursor.fetchall()
    
    print(f"{'序号':<4} {'服务名':<20} {'服务类型':<8} {'图层名':<25} {'服务URL'}")
    print("-" * 100)
    
    for i, (service_name, service_url, service_type, layer_name) in enumerate(rows, 1):
        # 截断过长的字段以保持格式整齐
        service_name_short = service_name[:18] + ".." if len(service_name) > 20 else service_name
        layer_name_short = layer_name[:23] + ".." if len(layer_name) > 25 else layer_name
        service_url_short = service_url[:50] + ".." if len(service_url) > 52 else service_url
        
        print(f"{i:<4} {service_name_short:<20} {service_type:<8} {layer_name_short:<25} {service_url_short}")

async def show_all_table_data(conn, table_name):
    """显示其他表的完整数据"""
    # 获取表结构
    cursor = await conn.execute(f"PRAGMA table_info({table_name})")
    columns = await cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    # 限制显示前10条记录
    cursor = await conn.execute(f"SELECT * FROM {table_name} LIMIT 10")
    rows = await cursor.fetchall()
    
    # 打印表头
    header = " | ".join(f"{col:15}" for col in column_names)
    print(f"  {header}")
    print(f"  {'-' * len(header)}")
    
    # 打印数据行
    for row in rows:
        row_data = " | ".join(f"{str(val)[:15]:15}" for val in row)
        print(f"  {row_data}")

if __name__ == "__main__":
    asyncio.run(show_database_tables())