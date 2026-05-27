# 麦麦!来点二次元图片!

[MaiBot](https://github.com/MaiM-with-u/MaiBot) 二次元随机图片插件，基于 [Lolicon API](https://api.lolicon.app/setu/v2)。**无需 Pixiv 账号，无需 Token，开箱即用。**

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🔍 多标签组合搜索 | 支持 AND 组合（如「少女,猫」= 同时包含两者），每标签独立缓存 |
| ⏰ 定时自动爬取 | 设定每天几点自动补充图片库存 |
| 📦 空库自动爬取 | 库存用完时自动触发补充，用户无感 |
| 🎯 @触发 | 群聊中 @机器人 + 关键词才发图，防止误触发 |
| 🚫 AI过滤 | 可选排除 AI 生成图片，只保留人类画师作品 |
| 📐 分辨率可选 | original / regular(推荐) / small / thumb / mini |
| 🔞 内容分级 | safe(全年龄) / all(不过滤) / r18(仅R18) |
| 🔁 发图去重 | 已发图片自动记录，永不重复发送 |
| 🗜️ 大图压缩 | 超 12MB 自动缩放到 2048px，节省流量 |
| 🌐 代理可选 | 国内直连 i.pixiv.re CDN 即可，通常无需代理 |

## 🚀 快速开始

### 1. 安装

将 `pixiv-crawler/` 文件夹放到 MaiBot 的 `plugins/` 目录下：

```
MaiBot/
└── plugins/
    └── pixiv-crawler/
        ├── plugin.py
        ├── config.py
        ├── config.toml
        ├── _manifest.json
        └── README.md
```

### 2. 配置

启动 MaiBot 后在 WebUI 中配置，或直接编辑 `config.toml`：

```toml
[api]
tag_templates = ["少女", "猫耳,萝莉", "风景"]
per_tag_count = 25
age_rating = "all"
exclude_ai = true
image_size = "regular"

[send]
trigger_keywords = ["涩图", "色图", "来点图", "美图"]
count = 3

[storage]
max_total_images = 50
```

### 3. 使用

```
# 首次补充图片库存
@麦麦 立刻爬取

# 发图（群聊需 @）
@麦麦 涩图
@麦麦 来点图
@麦麦 美图

# 私聊直接发（默认无需 @）
涩图
```

## ⚙️ 配置详解

### 图片来源

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `tag_templates` | `["少女"]` | 搜索标签列表。逗号分隔 = AND 组合 |
| `per_tag_count` | `25` | 每个标签缓存多少张图（Lolicon 单次最多20，自动分批） |
| `age_rating` | `"all"` | `safe` = 全年龄 / `all` = 不过滤 / `r18` = 仅R18 |
| `exclude_ai` | `true` | 排除 AI 生成图片 |
| `image_size` | `"regular"` | 图片分辨率，推荐 `regular` |

### 触发条件

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `trigger_keywords` | `["涩图", "色图", ...]` | 发图触发词，消息含任意一个即触发 |
| `count` | `3` | 每次发几张 |
| `enabled`（@模式） | `true` | 是否需要 @ 机器人才触发 |
| `require_at_group` | `true` | 群聊是否需要 @ |
| `require_at_private` | `false` | 私聊是否需要 @（通常关闭） |

### 定时爬取

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `enabled` | `false` | 是否启用定时爬取 |
| `times` | `["03:00", "15:00"]` | 每天爬取时间（24小时制） |
| `auto_crawl_when_empty` | `true` | 库存为空时自动爬取 |
| `auto_crawl_count` | `10` | 自动爬取时每标签拉取数 |

### 存储

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `max_total_images` | `50` | 库存上限，超出删最旧的。0 = 不限 |
| `max_image_size_mb` | `20.0` | 单张大小上限(MB)，超限跳过 |

## 🔧 API 说明

- **端点**: `POST https://api.lolicon.app/setu/v2`
- **图片CDN**: `i.pixiv.re`（国内可直连）
- **无需鉴权**，无频率限制（合理使用）
- 每次最多返回 20 张随机图，超出 `per_tag_count` 会自动分批

## 📋 从旧版迁移

从 v2.x（duckMo 版本）升级：

1. 替换 `plugin.py` 和 `config.py` 为 v3.0.0 版本
2. `config.toml` 中旧的 `tags = [...]` 会自动迁移到 `tag_templates`
3. 旧图片保留在 `images/` 目录下不会丢失

## 📄 License

MIT
