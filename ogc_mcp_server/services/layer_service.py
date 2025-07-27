"""
图层服务模块

提供OGC服务图层的注册和管理功能
"""

import logging
from typing import List, Dict, Any, Optional
from fastmcp import Context

from ..database import get_layer_repository, LayerResourceCreate, LayerResourceUpdate
from ..utils import get_ogc_parser

logger = logging.getLogger(__name__)


async def register_ogc_layers(
    service_urls: List[str],
    service_name: Optional[str] = None,
    service_type: Optional[str] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """注册OGC服务图层
    
    解析OGC服务的能力文档，提取图层信息并注册到资源列表中
    实现智能图层管理：
    - 同一图层支持多种服务类型：合并为BOTH类型
    - 图层名相同，类型相同：跳过注册
    - 解析后没找到该图层：删除该资源
    
    Args:
        service_urls: OGC服务URL列表
        service_name: 服务名称（可选）
        service_type: 服务类型，WMS或WFS（可选，不提供则自动检测）
        ctx: MCP上下文对象
        
    Returns:
        注册结果字典，包含成功和失败的统计信息
    """
    if ctx:
        await ctx.info(f"开始注册OGC服务图层，共 {len(service_urls)} 个服务")
    
    # 获取依赖
    repository = await get_layer_repository()
    parser = await get_ogc_parser()
    
    # 统计信息
    total_services = len(service_urls)
    successful_services = 0
    failed_services = 0
    total_layers = 0
    successful_layers = 0
    failed_layers = 0
    skipped_layers = 0
    deleted_layers = 0
    merged_layers = 0
    
    results = {
        "summary": {},
        "services": [],
        "errors": []
    }
    
    # 处理每个服务URL
    for i, url in enumerate(service_urls):
        if ctx:
            await ctx.info(f"正在处理服务: {url}")
            await ctx.report_progress(progress=i, total=total_services)
        
        service_result = {
            "url": url,
            "status": "success",
            "layers": [],
            "deleted_layers": [],
            "error": None
        }
        
        try:
            logger.info(f"开始解析OGC服务: {url}")
            
            # 解析服务获取图层信息
            parsed_layers = await parser.parse_ogc_service(
                url=url,
                service_type=service_type,
                service_name=service_name
            )
            
            total_layers += len(parsed_layers)
            
            # 获取当前数据库中该服务的所有图层
            existing_layers = await repository.get_layers_by_service_url(url)
            
            # 按图层名称分组解析到的图层，检测多服务类型支持
            parsed_layers_by_name = {}
            for layer in parsed_layers:
                if layer.layer_name not in parsed_layers_by_name:
                    parsed_layers_by_name[layer.layer_name] = []
                parsed_layers_by_name[layer.layer_name].append(layer)
            
            # 创建解析到的图层集合（按图层名称）
            parsed_layer_names = set(parsed_layers_by_name.keys())
            
            # 处理每个图层名称
            for layer_name, layer_variants in parsed_layers_by_name.items():
                try:
                    # 检查该图层是否已存在（按service_url和layer_name查找）
                    existing_layer = None
                    for existing in existing_layers:
                        if existing.layer_name == layer_name:
                            existing_layer = existing
                            break
                    
                    # 确定最终的服务类型
                    service_types = [layer.service_type for layer in layer_variants]
                    if len(service_types) > 1:
                        final_service_type = "BOTH"
                    else:
                        final_service_type = service_types[0]
                    
                    # 使用第一个变体作为基础信息（它们的基础信息应该相同）
                    base_layer = layer_variants[0]
                    
                    if existing_layer:
                        # 检查是否需要更新服务类型
                        if existing_layer.service_type != final_service_type:
                            # 更新服务类型
                            update_data = LayerResourceUpdate(service_type=final_service_type)
                            updated_layer = await repository.update(existing_layer.resource_id, update_data)
                            
                            if updated_layer:
                                merged_layers += 1
                                service_result["layers"].append({
                                    "name": layer_name,
                                    "type": final_service_type,
                                    "status": "merged",
                                    "previous_type": existing_layer.service_type,
                                    "resource_id": existing_layer.resource_id
                                })
                                logger.info(f"图层服务类型已合并: {layer_name} ({existing_layer.service_type} -> {final_service_type})")
                            else:
                                failed_layers += 1
                                service_result["layers"].append({
                                    "name": layer_name,
                                    "type": final_service_type,
                                    "status": "merge_failed",
                                    "error": "update_failed"
                                })
                        else:
                            # 服务类型相同，跳过
                            skipped_layers += 1
                            service_result["layers"].append({
                                "name": layer_name,
                                "type": final_service_type,
                                "status": "skipped",
                                "reason": "already_exists"
                            })
                            logger.info(f"图层已存在，跳过: {layer_name} ({final_service_type})")
                    else:
                        # 创建新图层资源
                        new_layer = LayerResourceCreate(
                            service_name=base_layer.service_name,
                            service_url=base_layer.service_url,
                            service_type=final_service_type,
                            layer_name=base_layer.layer_name,
                            layer_title=base_layer.layer_title,
                            layer_abstract=base_layer.layer_abstract
                        )
                        
                        created_layer = await repository.create(new_layer)
                        successful_layers += 1
                        
                        service_result["layers"].append({
                            "name": layer_name,
                            "type": final_service_type,
                            "status": "created",
                            "resource_id": created_layer.resource_id
                        })
                        
                        logger.info(f"图层注册成功: {layer_name} ({final_service_type})")
                    
                except Exception as e:
                    failed_layers += 1
                    error_msg = f"处理图层失败 {layer_name}: {e}"
                    logger.error(error_msg)
                    
                    service_result["layers"].append({
                        "name": layer_name,
                        "type": "unknown",
                        "status": "failed",
                        "error": str(e)
                    })
                    
                    results["errors"].append(error_msg)
            
            # 删除数据库中存在但解析结果中不存在的图层
            for existing_layer in existing_layers:
                if existing_layer.layer_name not in parsed_layer_names:
                    try:
                        success = await repository.delete(existing_layer.resource_id)
                        if success:
                            deleted_layers += 1
                            service_result["deleted_layers"].append({
                                "name": existing_layer.layer_name,
                                "type": existing_layer.service_type,
                                "resource_id": existing_layer.resource_id,
                                "reason": "not_found_in_service"
                            })
                            logger.info(f"删除不存在的图层: {existing_layer.layer_name} ({existing_layer.service_type})")
                    except Exception as e:
                        error_msg = f"删除图层失败 {existing_layer.layer_name} ({existing_layer.service_type}): {e}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)
            
            successful_services += 1
            logger.info(f"服务解析完成: {url}, 共处理 {len(parsed_layers_by_name)} 个图层，合并 {merged_layers} 个，删除 {len(service_result['deleted_layers'])} 个过期图层")
            
        except Exception as e:
            failed_services += 1
            error_msg = f"解析服务失败 {url}: {e}"
            logger.error(error_msg)
            
            service_result["status"] = "failed"
            service_result["error"] = str(e)
            results["errors"].append(error_msg)
        
        results["services"].append(service_result)
    
    # 汇总统计信息
    results["summary"] = {
        "total_services": total_services,
        "successful_services": successful_services,
        "failed_services": failed_services,
        "total_layers": total_layers,
        "successful_layers": successful_layers,
        "failed_layers": failed_layers,
        "skipped_layers": skipped_layers,
        "deleted_layers": deleted_layers,
        "merged_layers": merged_layers
    }
    
    if ctx:
        await ctx.report_progress(progress=total_services, total=total_services)
        await ctx.info(
            f"图层注册完成: 成功服务 {successful_services}/{total_services}, "
            f"成功图层 {successful_layers}/{total_layers}, "
            f"跳过图层 {skipped_layers}, 合并图层 {merged_layers}, 删除图层 {deleted_layers}"
        )
    
    logger.info(f"图层注册任务完成: {results['summary']}")
    return results


async def list_registered_layers(
    service_type: Optional[str] = None,
    service_name: Optional[str] = None,
    layer_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    ctx: Context = None
) -> Dict[str, Any]:
    """列出已注册的图层资源
    
    查询已注册的OGC图层资源，支持按服务类型、服务名称、图层名称进行筛选
    
    Args:
        service_type: 按服务类型筛选（可选）
        service_name: 按服务名称筛选（可选）
        layer_name: 按图层名称筛选（可选）
        limit: 返回结果数量限制
        offset: 结果偏移量
        ctx: MCP上下文对象
        
    Returns:
        图层资源列表和统计信息
    """
    if ctx:
        await ctx.info(f"正在查询图层资源，筛选条件: 类型={service_type}, 服务={service_name}, 图层={layer_name}")
    
    try:
        # 获取仓储
        repository = await get_layer_repository()
        
        # 构建查询对象
        from ..database.models import LayerResourceQuery
        query = LayerResourceQuery(
            service_type=service_type,
            service_name=service_name,
            layer_name=layer_name,
            limit=limit,
            offset=offset
        )
        
        # 查询图层资源
        layers = await repository.list_resources(query)
        total_count = await repository.count(query)
        
        # 转换为字典格式（只包含基础元数据）
        layer_list = []
        for layer in layers:
            layer_dict = {
                "resource_id": layer.resource_id,
                "service_name": layer.service_name,
                "service_url": layer.service_url,
                "service_type": layer.service_type,
                "layer_name": layer.layer_name,
                "layer_title": layer.layer_title,
                "layer_abstract": layer.layer_abstract,
                "created_at": layer.created_at.isoformat(),
                "updated_at": layer.updated_at.isoformat()
            }
            layer_list.append(layer_dict)
        
        result = {
            "layers": layer_list,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(layers) < total_count
            },
            "filters": {
                "service_type": service_type,
                "service_name": service_name,
                "layer_name": layer_name
            }
        }
        
        if ctx:
            await ctx.info(f"查询完成，共找到 {len(layers)} 个图层资源（总计 {total_count} 个）")
        
        logger.info(f"图层资源查询完成: 返回 {len(layers)}/{total_count} 个结果")
        return result
        
    except Exception as e:
        error_msg = f"查询图层资源失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


async def delete_layer_resource(
    resource_id: str,
    ctx: Context = None
) -> Dict[str, Any]:
    """删除图层资源
    
    从资源列表中删除指定的图层资源
    
    Args:
        resource_id: 图层资源ID
        ctx: MCP上下文对象
        
    Returns:
        删除结果字典，包含操作状态和被删除的资源信息
    """
    if ctx:
        await ctx.info(f"正在删除图层资源: {resource_id}")
    
    try:
        # 获取仓储
        repository = await get_layer_repository()
        
        # 首先检查资源是否存在
        existing_layer = await repository.get_by_id(resource_id)
        if not existing_layer:
            error_msg = f"图层资源不存在: {resource_id}"
            logger.warning(error_msg)
            if ctx:
                await ctx.error(error_msg)
            
            return {
                "status": "failed",
                "error": "resource_not_found",
                "message": error_msg,
                "resource_id": resource_id
            }
        
        # 记录要删除的资源信息
        deleted_info = {
            "resource_id": existing_layer.resource_id,
            "service_name": existing_layer.service_name,
            "service_url": existing_layer.service_url,
            "service_type": existing_layer.service_type,
            "layer_name": existing_layer.layer_name,
            "layer_title": existing_layer.layer_title
        }
        
        # 执行删除操作
        success = await repository.delete(resource_id)
        
        if success:
            result = {
                "status": "success",
                "message": f"图层资源删除成功: {existing_layer.layer_name}",
                "deleted_resource": deleted_info
            }
            
            if ctx:
                await ctx.info(f"图层资源删除成功: {existing_layer.layer_name}")
            
            logger.info(f"图层资源删除成功: {resource_id} - {existing_layer.layer_name}")
            return result
        else:
            error_msg = f"删除图层资源失败: {resource_id}"
            logger.error(error_msg)
            if ctx:
                await ctx.error(error_msg)
            
            return {
                "status": "failed",
                "error": "delete_failed",
                "message": error_msg,
                "resource_id": resource_id
            }
            
    except Exception as e:
        error_msg = f"删除图层资源时发生错误: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        
        return {
            "status": "failed",
            "error": "exception",
            "message": error_msg,
            "resource_id": resource_id
        }


async def update_layer_resource(
    resource_id: str,
    updates: Dict[str, Any],
    ctx: Context = None
) -> Dict[str, Any]:
    """更新图层资源信息
    
    更新已注册图层资源的元数据信息
    
    Args:
        resource_id: 图层资源ID
        updates: 要更新的字段字典
        ctx: MCP上下文对象
        
    Returns:
        更新结果字典，包含操作状态和更新后的资源信息
    """
    if ctx:
        await ctx.info(f"正在更新图层资源: {resource_id}")
    
    try:
        # 获取仓储
        repository = await get_layer_repository()
        
        # 检查资源是否存在
        existing_layer = await repository.get_by_id(resource_id)
        if not existing_layer:
            error_msg = f"图层资源不存在: {resource_id}"
            logger.warning(error_msg)
            if ctx:
                await ctx.error(error_msg)
            
            return {
                "status": "failed",
                "error": "resource_not_found",
                "message": error_msg,
                "resource_id": resource_id
            }
        
        # 构建更新对象
        from ..database.models import LayerResourceUpdate
        update_data = LayerResourceUpdate(**updates)
        
        # 执行更新操作
        updated_layer = await repository.update(resource_id, update_data)
        
        if updated_layer:
            result = {
                "status": "success",
                "message": f"图层资源更新成功: {updated_layer.layer_name}",
                "updated_resource": {
                    "resource_id": updated_layer.resource_id,
                    "service_name": updated_layer.service_name,
                    "service_url": updated_layer.service_url,
                    "service_type": updated_layer.service_type,
                    "layer_name": updated_layer.layer_name,
                    "layer_title": updated_layer.layer_title,
                    "layer_abstract": updated_layer.layer_abstract,
                    "updated_at": updated_layer.updated_at.isoformat()
                }
            }
            
            if ctx:
                await ctx.info(f"图层资源更新成功: {updated_layer.layer_name}")
            
            logger.info(f"图层资源更新成功: {resource_id} - {updated_layer.layer_name}")
            return result
        else:
            error_msg = f"更新图层资源失败: {resource_id}"
            logger.error(error_msg)
            if ctx:
                await ctx.error(error_msg)
            
            return {
                "status": "failed",
                "error": "update_failed",
                "message": error_msg,
                "resource_id": resource_id
            }
            
    except Exception as e:
        error_msg = f"更新图层资源时发生错误: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        
        return {
            "status": "failed",
            "error": "exception",
            "message": error_msg,
            "resource_id": resource_id
        }


async def get_layer_statistics(ctx: Context = None) -> Dict[str, Any]:
    """获取图层资源统计信息
    
    统计已注册图层的各种信息，包括服务类型分布、服务数量等
    
    Args:
        ctx: MCP上下文对象
        
    Returns:
        统计信息字典
    """
    if ctx:
        await ctx.info("正在获取图层资源统计信息")
    
    try:
        # 获取仓储
        repository = await get_layer_repository()
        
        # 获取总数统计
        from ..database.models import LayerResourceQuery
        total_query = LayerResourceQuery()
        total_count = await repository.count(total_query)
        
        # 按服务类型统计
        wms_query = LayerResourceQuery(service_type="WMS")
        wms_count = await repository.count(wms_query)
        
        wfs_query = LayerResourceQuery(service_type="WFS")
        wfs_count = await repository.count(wfs_query)
        
        # 获取所有图层用于详细统计
        all_layers = await repository.list_resources(LayerResourceQuery(limit=10000))
        
        # 按服务名称统计
        service_stats = {}
        
        for layer in all_layers:
            # 服务统计
            service_key = f"{layer.service_name} ({layer.service_type})"
            if service_key not in service_stats:
                service_stats[service_key] = {
                    "service_name": layer.service_name,
                    "service_type": layer.service_type,
                    "service_url": layer.service_url,
                    "layer_count": 0
                }
            service_stats[service_key]["layer_count"] += 1
        
        # 构建统计结果
        result = {
            "total_layers": total_count,
            "service_type_distribution": {
                "WMS": wms_count,
                "WFS": wfs_count
            },
            "service_statistics": list(service_stats.values()),
            "top_services": sorted(
                service_stats.values(), 
                key=lambda x: x["layer_count"], 
                reverse=True
            )[:10]
        }
        
        if ctx:
            await ctx.info(f"统计信息获取完成: 总计 {total_count} 个图层")
        
        logger.info(f"图层资源统计完成: 总计 {total_count} 个图层")
        return result
        
    except Exception as e:
        error_msg = f"获取图层统计信息失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise