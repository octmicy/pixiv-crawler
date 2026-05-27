"""麦麦!来点二次元图片! — 插件配置模型。

WebUI 配置表单依赖此模块生成多语言界面。
"""

from __future__ import annotations

from typing import ClassVar, Dict, Literal, Optional

from maibot_sdk import Field, PluginConfigBase

# ═══════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════

CONFIG_SCHEMA_VERSION = "3.0.0"


# ═══════════════════════════════════════════════════════════════════════
# i18n 辅助
# ═══════════════════════════════════════════════════════════════════════

def _schema_i18n(
    *,
    label_en: str,
    label_ja: str,
    hint_en: Optional[str] = None,
    hint_ja: Optional[str] = None,
    placeholder_en: Optional[str] = None,
    placeholder_ja: Optional[str] = None,
) -> Dict[str, Dict[str, str]]:
    """构造 WebUI 配置项多语言说明，外层 label/hint 保留中文字段。"""
    i18n: Dict[str, Dict[str, str]] = {
        "en_US": {"label": label_en},
        "ja_JP": {"label": label_ja},
    }
    if hint_en is not None:
        i18n["en_US"]["hint"] = hint_en
    if hint_ja is not None:
        i18n["ja_JP"]["hint"] = hint_ja
    if placeholder_en is not None:
        i18n["en_US"]["placeholder"] = placeholder_en
    if placeholder_ja is not None:
        i18n["ja_JP"]["placeholder"] = placeholder_ja
    return i18n


# ═══════════════════════════════════════════════════════════════════════
# 配置模型
# ═══════════════════════════════════════════════════════════════════════


class PluginSection(PluginConfigBase):
    """插件基础设置"""
    __ui_label__: ClassVar[str] = "插件总开关"
    __ui_order__: ClassVar[int] = 0

    config_version: str = Field(
        default=CONFIG_SCHEMA_VERSION,
        description="配置 schema 版本，请勿手动修改。",
        json_schema_extra={
            "disabled": True,
            "hidden": True,
            "label": "配置版本",
            "i18n": _schema_i18n(label_en="Config version", label_ja="設定バージョン"),
            "order": 99,
        },
    )
    enabled: bool = Field(
        default=True,
        description="总开关。关闭后插件完全停止工作，不会爬取也不会发图。",
        json_schema_extra={
            "label": "启用插件",
            "hint": "关闭后插件完全停止工作，不会爬取也不会发图。",
            "i18n": _schema_i18n(
                label_en="Enable plugin",
                label_ja="プラグインを有効化",
                hint_en="Master switch. When OFF, the plugin stops entirely — no crawling, no image sending.",
                hint_ja="マスタースイッチ。OFFにするとクロールも画像送信も完全に停止します。",
            ),
            "order": 0,
        },
    )


class ApiSection(PluginConfigBase):
    """图片来源设置"""
    __ui_label__: ClassVar[str] = "图片来源"
    __ui_order__: ClassVar[int] = 1

    tag_templates: list[str] = Field(
        default=["少女"],
        description="要搜索的标签列表。每个条目是一个搜索模板，多个标签用逗号分隔表示 AND 组合。",
        json_schema_extra={
            "label": "搜索标签",
            "hint": "每行一个搜索模板。逗号分隔 = 同时包含（AND），如「少女,猫」= 必须同时有少女和猫。不同行 = 独立搜索。",
            "placeholder": "少女\n猫耳,萝莉\n风景",
            "order": 0,
        },
    )
    # 向后兼容：旧版 tags（单个标签列表），仅当 tag_templates 为空时自动转换
    tags: list[str] = Field(
        default=[],
        description="（已弃用）旧版单标签列表，请使用「搜索标签」。",
        json_schema_extra={
            "label": "旧版标签（已弃用）",
            "hint": "已弃用，请使用上方的「搜索标签」。旧版数据会自动迁移。",
            "i18n": _schema_i18n(
                label_en="Legacy tags (deprecated)",
                label_ja="旧タグ（非推奨）",
                hint_en="Deprecated. Use 'Search Tags' above. Legacy data is auto-migrated.",
                hint_ja="非推奨。上の「検索タグ」を使用してください。旧データは自動移行されます。",
            ),
            "order": 99,
        },
    )
    per_tag_count: int = Field(
        default=25,
        description="每个标签总共缓存多少张图。Lolicon 每次最多返回20张，超出会自动分批请求。",
        json_schema_extra={
            "label": "每标签缓存数",
            "hint": "每个标签总共缓存多少张图。Lolicon 每次最多返回20张，超出会自动分批。建议 20~50。",
            "i18n": _schema_i18n(
                label_en="Images per tag",
                label_ja="タグごとの画像数",
                hint_en="How many images to cache per tag. Lolicon returns max 20 per request; excess is auto-batched. Recommended: 20-50.",
                hint_ja="タグごとにキャッシュする画像数。Loliconは1リクエスト最大20枚、超過は自動バッチ処理。推奨: 20-50。",
            ),
            "order": 1,
        },
    )
    age_rating: Literal["safe", "all", "r18"] = Field(
        default="all",
        description="内容分级。safe=仅全年龄，all=不过滤，r18=仅R18。",
        json_schema_extra={
            "label": "内容分级",
            "hint": "safe = 仅全年龄安全内容；all = 不过滤（可能含R18）；r18 = 仅R18内容。",
            "i18n": _schema_i18n(
                label_en="Content rating",
                label_ja="コンテンツレーティング",
                hint_en="safe = SFW only; all = no filter (may include NSFW); r18 = NSFW only.",
                hint_ja="safe = 全年齢のみ；all = フィルターなし（R18含む）；r18 = R18のみ。",
            ),
            "order": 2,
        },
    )
    exclude_ai: bool = Field(
        default=True,
        description="过滤掉 AI 生成的图片，只保留人类画师作品。",
        json_schema_extra={
            "label": "排除AI作品",
            "hint": "开启后过滤掉 AI 生成的图片，只保留人类画师的作品。",
            "i18n": _schema_i18n(
                label_en="Exclude AI art",
                label_ja="AI作品を除外",
                hint_en="Filters out AI-generated images, keeping only human-drawn artwork.",
                hint_ja="AI生成画像を除外し、人間の作品のみを保持します。",
            ),
            "order": 3,
        },
    )
    image_size: Literal["original", "regular", "small", "thumb", "mini"] = Field(
        default="regular",
        description="下载的图片分辨率。",
        json_schema_extra={
            "label": "图片分辨率",
            "hint": "regular = 中等清晰度（推荐，适合聊天）；original = 原图（可能很大）；small/thumb/mini = 更小更省流量。",
            "i18n": _schema_i18n(
                label_en="Image resolution",
                label_ja="画像解像度",
                hint_en="regular = medium quality (recommended for chat); original = full size (may be large); small/thumb/mini = smaller, saves bandwidth.",
                hint_ja="regular = 中画質（チャット向け推奨）；original = フルサイズ（大きい場合あり）；small/thumb/mini = 小さい、帯域節約。",
            ),
            "order": 4,
        },
    )


class ProxySection(PluginConfigBase):
    """网络代理设置"""
    __ui_label__: ClassVar[str] = "网络代理"
    __ui_order__: ClassVar[int] = 2

    enabled: bool = Field(
        default=False,
        description="是否通过代理下载图片。国内通常不需要，图片走 i.pixiv.re CDN。",
        json_schema_extra={
            "label": "启用代理",
            "hint": "图片通过 i.pixiv.re CDN 分发，国内可直连，通常不需要开代理。",
            "i18n": _schema_i18n(
                label_en="Enable proxy",
                label_ja="プロキシを有効化",
                hint_en="Images are served via i.pixiv.re CDN, accessible from most regions. Proxy usually not needed.",
                hint_ja="画像は i.pixiv.re CDN 経由で配信。多くの地域から直接アクセス可能。通常プロキシは不要。",
            ),
            "order": 0,
        },
    )
    url: str = Field(
        default="http://127.0.0.1:7890",
        description="代理地址。支持 HTTP 和 SOCKS5。",
        json_schema_extra={
            "label": "代理地址",
            "hint": "支持 HTTP 和 SOCKS5，如 http://127.0.0.1:7890 或 socks5://127.0.0.1:1080。",
            "i18n": _schema_i18n(
                label_en="Proxy URL",
                label_ja="プロキシ URL",
                hint_en="HTTP or SOCKS5. E.g. http://127.0.0.1:7890 or socks5://127.0.0.1:1080.",
                hint_ja="HTTP または SOCKS5。例: http://127.0.0.1:7890 や socks5://127.0.0.1:1080。",
                placeholder_en="http://127.0.0.1:7890",
                placeholder_ja="http://127.0.0.1:7890",
            ),
            "placeholder": "http://127.0.0.1:7890",
            "order": 1,
        },
    )


class ScheduleSection(PluginConfigBase):
    """定时与自动爬取"""
    __ui_label__: ClassVar[str] = "定时与自动爬取"
    __ui_order__: ClassVar[int] = 3

    enabled: bool = Field(
        default=False,
        description="开启后按下方设定的时间自动爬取新图片。",
        json_schema_extra={
            "label": "启用定时爬取",
            "hint": "开启后每天在指定时间自动爬取新图片补充库存。",
            "i18n": _schema_i18n(
                label_en="Enable scheduled crawl",
                label_ja="定期クロールを有効化",
                hint_en="Automatically crawls for new images at the scheduled times every day.",
                hint_ja="毎日指定時間に新しい画像を自動クロールします。",
            ),
            "order": 0,
        },
    )
    times: list[str] = Field(
        default=["03:00", "15:00"],
        description="每天自动爬取的时间点，24小时制。",
        json_schema_extra={
            "label": "爬取时间",
            "hint": "每天自动爬取的时间点，24小时制 HH:MM。建议设在凌晨等低峰时段。",
            "i18n": _schema_i18n(
                label_en="Crawl schedule",
                label_ja="クロール時刻",
                hint_en="Daily crawl times in 24h HH:MM format. Recommended: off-peak hours like late night.",
                hint_ja="毎日のクロール時刻（24時間表記 HH:MM）。深夜のオフピーク時間を推奨。",
                placeholder_en='["03:00", "15:00"]',
                placeholder_ja='["03:00", "15:00"]',
            ),
            "placeholder": '["03:00", "15:00"]',
            "order": 1,
        },
    )
    auto_crawl_when_empty: bool = Field(
        default=True,
        description="当图片库存用完、用户又要图时，自动触发一次爬取。",
        json_schema_extra={
            "label": "库存为空时自动爬取",
            "hint": "用户要图但库存已空时，自动触发一次爬取补充，用户无需手动操作。",
            "i18n": _schema_i18n(
                label_en="Auto-crawl when empty",
                label_ja="空のとき自動クロール",
                hint_en="When user requests images but the warehouse is empty, automatically triggers a crawl to refill.",
                hint_ja="ユーザーが画像をリクエストしたが在庫が空の場合、自動的にクロールして補充します。",
            ),
            "order": 2,
        },
    )
    auto_crawl_count: int = Field(
        default=10,
        description="自动爬取时每个标签拉取多少张图。",
        json_schema_extra={
            "label": "自动爬取数量/标签",
            "hint": "库存为空触发自动爬取时，每个标签拉取多少张图。",
            "i18n": _schema_i18n(
                label_en="Auto-crawl count per tag",
                label_ja="自動クロール数/タグ",
                hint_en="Number of images per tag when auto-crawling on empty warehouse.",
                hint_ja="空在庫時の自動クロールでタグあたり取得する画像数。",
            ),
            "order": 3,
        },
    )
    crawl_trigger_keywords: list[str] = Field(
        default=["立刻爬取", "立即爬取", "立刻爬图", "立即爬图", "马上爬", "现在爬", "爬图", "开始爬"],
        description="用户发送这些关键词时手动触发爬取。",
        json_schema_extra={
            "label": "手动爬取关键词",
            "hint": "用户发送这些关键词时立刻触发一次爬取，无需等待定时任务。",
            "i18n": _schema_i18n(
                label_en="Manual crawl trigger words",
                label_ja="手動クロールキーワード",
                hint_en="Users type these words to immediately trigger a crawl, without waiting for the schedule.",
                hint_ja="これらのキーワードでスケジュールを待たず即座にクロールを実行します。",
                placeholder_en="立刻爬取, 马上爬",
                placeholder_ja="立刻爬取, 马上爬",
            ),
            "placeholder": "立刻爬取, 马上爬",
            "order": 2,
        },
    )


class AtModeSection(PluginConfigBase):
    """触发条件"""
    __ui_label__: ClassVar[str] = "触发条件"
    __ui_order__: ClassVar[int] = 4

    enabled: bool = Field(
        default=True,
        description="开启后只有 @机器人 的消息才会触发发图，防止误触发。",
        json_schema_extra={
            "label": "需要 @ 才触发",
            "hint": "开启后群聊中必须 @机器人 才会发图。关闭则任何含关键词的消息都会触发。",
            "i18n": _schema_i18n(
                label_en="Require @-mention to trigger",
                label_ja="@メンションが必要",
                hint_en="When ON, only @-mentioned messages trigger image sending. When OFF, any message with keywords triggers.",
                hint_ja="ONにすると@メンションされたメッセージのみ画像送信をトリガー。OFFだとキーワード含む全メッセージが対象。",
            ),
            "order": 0,
        },
    )
    require_at_group: bool = Field(
        default=True,
        description="群聊中是否需要 @ 机器人才触发。",
        json_schema_extra={
            "label": "群聊需要 @",
            "hint": "群聊场景下是否需要 @ 机器人才触发发图。",
            "i18n": _schema_i18n(
                label_en="Require @ in group chats",
                label_ja="グループチャットで@必須",
                hint_en="Whether group chat messages must @-mention the bot to trigger.",
                hint_ja="グループチャットでボットへの@メンションが必要かどうか。",
            ),
            "order": 1,
        },
    )
    require_at_private: bool = Field(
        default=False,
        description="私聊中是否也需要 @ 才触发。通常关闭即可。",
        json_schema_extra={
            "label": "私聊也需要 @",
            "hint": "私聊场景通常不需要 @，直接发关键词即可触发。",
            "i18n": _schema_i18n(
                label_en="Require @ in private chats",
                label_ja="プライベートチャットで@必須",
                hint_en="Usually OFF for private chats — just type the keyword directly.",
                hint_ja="通常プライベートチャットではOFF。キーワードを直接入力するだけ。",
            ),
            "order": 2,
        },
    )
    bot_name: str = Field(
        default="麦麦",
        description="机器人在群里的昵称，用于检测 @ 提及。",
        json_schema_extra={
            "label": "机器人昵称",
            "hint": "用于检测消息中是否 @了机器人。需要和机器人在群里的昵称一致。",
            "i18n": _schema_i18n(
                label_en="Bot nickname",
                label_ja="ボットのニックネーム",
                hint_en="Used to detect @-mentions in messages. Must match the bot's nickname in the group.",
                hint_ja="メッセージ内の@メンション検出に使用。グループでのボットのニックネームと一致させてください。",
            ),
            "order": 3,
        },
    )
    reject_message: str = Field(
        default="",
        description="未 @ 时的拦截提示语。留空则静默忽略不回复。",
        json_schema_extra={
            "label": "未 @ 时的回复",
            "hint": "当消息未 @ 机器人时回复的提示语。留空 = 静默忽略，不回复任何内容。",
            "i18n": _schema_i18n(
                label_en="Reply when not @-mentioned",
                label_ja="@未メンション時の返信",
                hint_en="Reply text when the message doesn't @-mention the bot. Leave empty = silently ignore.",
                hint_ja="@メンションされていない場合の返信テキスト。空欄 = 無視して返信なし。",
                placeholder_en="Leave empty = silent ignore",
                placeholder_ja="空欄 = サイレント無視",
            ),
            "placeholder": "留空 = 静默忽略",
            "order": 4,
        },
    )


class SendSection(PluginConfigBase):
    """发图设置"""
    __ui_label__: ClassVar[str] = "发图设置"
    __ui_order__: ClassVar[int] = 5

    trigger_keywords: list[str] = Field(
        default=["涩图", "色图", "瑟图", "来点图", "来点好康", "美图"],
        description="触发发图的关键词列表。消息中包含任意一个即触发。",
        json_schema_extra={
            "label": "发图触发词",
            "hint": "消息中包含任意一个关键词即触发发图。支持自定义，每行一个。",
            "i18n": _schema_i18n(
                label_en="Image trigger keywords",
                label_ja="画像トリガーキーワード",
                hint_en="Any message containing one of these keywords triggers image sending. One per line.",
                hint_ja="メッセージにこれらのキーワードのいずれかが含まれると画像送信をトリガー。1行に1つ。",
                placeholder_en="setu, 涩图, 美图",
                placeholder_ja="涩图, 色图, 美图",
            ),
            "placeholder": "涩图, 色图, 来点图",
            "order": 0,
        },
    )
    count: int = Field(
        default=3,
        description="每次触发时发送几张图片。",
        json_schema_extra={
            "label": "每次发几张",
            "hint": "每次触发发图时发送几张图片。库存不足时自动发剩余全部。",
            "i18n": _schema_i18n(
                label_en="Images per trigger",
                label_ja="トリガーあたりの送信枚数",
                hint_en="How many images to send each time. If stock is low, sends whatever is left.",
                hint_ja="トリガーごとに送信する画像数。在庫不足時は残り全部を送信。",
            ),
            "order": 1,
        },
    )


class StorageSection(PluginConfigBase):
    """存储设置"""
    __ui_label__: ClassVar[str] = "存储管理"
    __ui_order__: ClassVar[int] = 6

    image_dir: str = Field(
        default="images",
        description="图片存储目录名，相对于插件根目录。",
        json_schema_extra={
            "label": "图片存储目录",
            "hint": "图片缓存在插件目录下的哪个文件夹。默认 images/，一般不需要改。",
            "i18n": _schema_i18n(
                label_en="Image storage directory",
                label_ja="画像保存ディレクトリ",
                hint_en="Subfolder under the plugin root to store cached images. Default: images/. Usually no need to change.",
                hint_ja="プラグインルート配下のキャッシュ画像保存フォルダ。デフォルト: images/。通常変更不要。",
            ),
            "order": 0,
        },
    )
    max_total_images: int = Field(
        default=50,
        description="图片库存上限。超出时自动删除最旧的图片。0 = 不限制。",
        json_schema_extra={
            "label": "库存上限",
            "hint": "最多缓存多少张图片。超出后自动删最旧的来腾出空间。设 0 则不限制。",
            "i18n": _schema_i18n(
                label_en="Max image stock",
                label_ja="最大画像ストック",
                hint_en="Maximum cached images. Oldest auto-deleted when exceeded. Set 0 for unlimited.",
                hint_ja="キャッシュ画像の上限。超過時は最も古いものを自動削除。0で無制限。",
            ),
            "order": 1,
        },
    )
    max_image_size_mb: float = Field(
        default=20.0,
        description="单张图片大小上限(MB)。超过此大小的图片跳过不下载。",
        json_schema_extra={
            "label": "单张大小上限(MB)",
            "hint": "超过此大小的图片直接跳过不下载，避免占用过多空间。",
            "i18n": _schema_i18n(
                label_en="Max single image size (MB)",
                label_ja="単一画像の最大サイズ(MB)",
                hint_en="Images larger than this are skipped to save storage.",
                hint_ja="このサイズを超える画像はストレージ節約のためスキップ。",
            ),
            "order": 2,
        },
    )


class PixivCrawlerConfig(PluginConfigBase):
    """插件完整配置"""
    __ui_label__ = "全部配置"

    plugin: PluginSection = Field(default_factory=PluginSection)
    api: ApiSection = Field(default_factory=ApiSection)
    proxy: ProxySection = Field(default_factory=ProxySection)
    schedule: ScheduleSection = Field(default_factory=ScheduleSection)
    at_mode: AtModeSection = Field(default_factory=AtModeSection)
    send: SendSection = Field(default_factory=SendSection)
    storage: StorageSection = Field(default_factory=StorageSection)


PixivCrawlerConfig.model_rebuild()
