# 一、MCP资源

## ①图层资源列表(支持动态资源注册，提供OGC标准的url链接，通过访问该OGC服务的WMS1.3.0和WFS2.0.0能力文档用ows-lib解析出可用图层或feturetype)(使用sqlite实现列表持久化存储。字段：resource_id(唯一标识符)、service_name(服务名称)、service_url、service_type、layer_name、layer_title、layer_abstract、created_at、updated_at)。举个例子：我将一个url或多个url丢给客户端(cherry studio)，它会使用注册工具将这些图层注册到mcp资源列表中。url类型：geoserver、mapserver等还有一些经过OGC认证的链接地址


## ②模板图层资源，通过资源列表里的图层名字得知该图层是什么服务(WMS/WFS)，具体的参数(WMS：图层名CRS、BBOX等正确的访问参数；WFS的正确访问格式，featuretype detail等)。这个资源模板是用来从已有的资源列表中找到图层名称。

# 二、MCP工具

## ①GetMap，从图层名称得到结果(资源列表-》模板资源找到图层名称-》根据图层名称获取该WMS图图的正确的访问参数并访问，返回图层的预览链接)

## ②GetFeature，从图层名称得到结果(资源列表-》模板资源找到图层名称-》根据图层名称获取该WFS图层的正确的访问参数并访问，返回图层的预览链接)





