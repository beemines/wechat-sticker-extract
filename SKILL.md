---
name: wechat-sticker-extract
description: Use when a user wants the original GIF or animated sticker from a Windows WeChat 4.x chat, including screenshot-identified stickers, missing favorites, failed 添加到表情, and no 另存为 menu. Not for generating animation from a still screenshot or bulk chat export.
---

# 提取微信原始表情动图

从用户已登录、已授权访问的微信账号中提取**指定表情附件原文件**。截图用于确定目标，不能从截图还原原始动画。

## 主流程

1. 确定聊天、目标消息和输出目录。默认保存到当前工作目录下的 `wechat_emoji` 文件夹，缺少时创建；用户明确指定其他目录时遵从用户。调用脚本时将该目录传给 `--output-dir`。截图不是最新消息时，结合发送者、邻近消息和时间定位；不能直接取“最新一张”。使用现有本地配置或文件元数据确认 `xwechat_files/<账号>`，不硬编码其他人的账号路径。
2. 若微信提供直接保存原文件的入口，可优先使用；电脑操作须遵守 `computer-use` 技能。没有“另存为”或添加失败后，转附件路线，不反复点击添加、转发或发送消息。
3. 运行 `scripts/extract_sticker.py list`，仅查询该聊天的 `local_type=47` 表情记录。已知分库就传 `--message-db`；旧截图用带时区的时间范围缩小查询，再用分库＋消息 ID 或附件 MD5 固定目标。若同一时间段有多个候选，列表本身不能确定截图对应哪张：结合授权范围内的微信界面定位，或将少量候选导出到独立临时目录进行视觉比对；仍不明确时询问具体缺项，不批量当作成品交付。
4. 运行 `export` 获取原资源。脚本使用有界、目标 salt 匹配且首页面认证通过的微信数据库读取；数据库在内存里解密，恢复已提交 WAL，解开 Zstandard 消息字段，从 `<emoji>` 读取原始资源地址。下载限于匹配表情的腾讯资源域名，必要时解密图片载荷。
5. 检查输出：实际格式、全部动画帧、尺寸、时长、循环信息，以及与消息附件 MD5 一致。用 `view_image` 检查独立预览图中的角色、文字，和用户截图比对；原文件不同动画相位是正常的。确认后给出绝对路径链接。

## 执行

脚本是 Windows 工具，依赖 Python 3.11+（需 SQLite `deserialize`）、`cryptography`、`Pillow`、`zstandard`。优先使用已有合适环境；也支持 `--deps-dir <已有site-packages目录>`，无需下载视频模型。先运行 `python scripts/extract_sticker.py --help`。

命令示例和数据库结构见 [references/extraction.md](references/extraction.md)。

| 情况 | 处理 |
|---|---|
| 表情在聊天里但未收藏 | 查对应消息附件；收藏数据库不包含所有收到的表情 |
| 只有加密缓存，改后缀打不开 | 不把缓存文件当 GIF；通过消息中的原资源信息恢复 |
| 截图是旧消息 | 明确分库、消息 ID／MD5；只有用户确实要最新表情时才用 `--latest` |
| 工具读不到微信或不支持版本 | 说明具体权限／版本问题，按环境正常审批；不退回无限制内存扫描 |
| 只下载到单帧缩略图或 MD5 不符 | 不交付为原始动图；继续原资源字段或明确失败 |
| 原始格式是 WebP／APNG | 按真实格式保留；用户要求 GIF 时另行转换并注明转码 |

## 读取范围与输出约束

- 仅处理用户选定账号、聊天和表情附件；不输出普通聊天内容、数据库密钥、AES key、签名 URL，不把数据库或用户截图传给第三方服务。
- 完整聊天库只做内存快照，不保存明文副本。遇到未知版本、账号歧义或目标不明确时报告具体缺项，不能悄悄改读其他账号或其他聊天。
- 不修改微信源数据库，不自动发消息、发布、上传网盘或购买表情。需要这些动作时另按用户指令处理。
- 输出是原图文件与不含密钥的核验 JSON；不覆盖同名不同内容的成品。交付时只链接用户需要的动图，不暴露临时调试数据。
