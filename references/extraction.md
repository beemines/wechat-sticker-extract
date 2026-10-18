# 原始附件提取：命令与版本边界

## 一次提取

先确认账号目录与聊天名。这两个路径变量由当前环境提供；示例聊天名为虚构名称。

```powershell
$stickerSkillRoot = 'C:\Users\当前用户\.codex\skills\wechat-sticker-extract'
$stickerAccountDir = 'D:\微信文件\xwechat_files\wxid_当前账号'
$stickerOutputDir = Join-Path (Get-Location).Path 'wechat_emoji'

python "$stickerSkillRoot\scripts\extract_sticker.py" list `
  --account-dir $stickerAccountDir --chat '小林' `
  --after '2026-10-18T16:00:00+08:00' --before '2026-10-18T17:00:00+08:00'

# 从上一步选择正确的分库和消息 ID；不能把该示例数值直接用于真实账号。
python "$stickerSkillRoot\scripts\extract_sticker.py" export `
  --account-dir $stickerAccountDir --chat '小林' `
  --message-db 'message_0.db' --local-id 275 `
  --output-dir $stickerOutputDir --name '兔子吃饭' `
  --preview-dir "$stickerOutputDir\.qa"
```

`--chat` 默认精确匹配联系人备注／昵称。只有需要且唯一时才显式加 `--contains`；若已经知道确切微信 username，可用 `--username` 跳过联系人查询。`--local-id` 必须配合 `--message-db`，因为不同分库的本地消息 ID 可能重复。`--md5` 可用于同一表情多次出现的情况。列表不输出 AES key、下载 URL 或普通聊天内容。

列表只包含时间、分库、消息 ID、MD5 和尺寸，不包含发送者或邻近聊天正文。不能仅凭“出现于这个时间段”认定视觉目标。可返回已授权的微信界面核对消息，或把少量限定候选导出到独立临时目录，查看预览后仅保留匹配者。

注意：`--md5` 是在每个分库 SQL 查询的条数上限之后筛选，默认只看最新 32 条表情。较旧 MD5 未命中不代表资源不存在；应保留截图对应的 `--after/--before` 窗口，指定已知分库，必要时把 `--limit` 提高到最多 200。已知旧消息 ID 时优先直接使用分库＋`--local-id`，不受新表情数量影响。

若用户明确要求“这个聊天最新一张表情”，可以用 `export ... --latest`。自动检索会比较各匹配分库的记录时间，不能找到第一个含此聊天的分库就提前认定它是最新。

已有依赖位于另一个兼容 Python 环境时，可以把 `--deps-dir <目录>` 放在 `list/export/verify` 子命令前。需要安装依赖时优先小型独立环境，不复用或重建 Wan2.2、ComfyUI 等无关模型环境。

## 已验证的结构

- `db_storage/contact/contact.db` 的 `contact` 表包含 `username`、`remark`、`nick_name`。
- 聊天表名为 `Msg_`＋`MD5(username UTF-8)`，位于 `db_storage/message/message_N.db`。
- `local_type=47` 是表情消息。`message_content` 可能以 `28 b5 2f fd` 开头，代表 Zstandard；不是普通 UTF-8 文本。
- XML `<emoji>` 中的 `md5` 用于核验原图；`cdnurl`、`externurl`、`encrypturl` 是原资源候选；`thumburl` 不能作为原始动图替代。
- 部分下载内容需要消息内的 `aeskey` 处理；应对候选明文字节做 MD5 核验后再保存，不能仅凭文件头判断成功。
- 表情收藏库和缓存都不等于聊天全部表情。收到但未收藏的表情可能仅在消息附件记录里出现。

## 版本与读取

内置数据库读取模块按数据库 salt 精确匹配 `Config.Cipher` 并认证数据库第一页；本技能只调用限时精确查找，不调用全内存候选字符串后备扫描。

内置模块包含 4.1.13.12、4.1.13.65、4.1.15.13 的精确适配；4.1.15.53 已在本次真实提取中验证相同布局可用，并且匹配目标数据库盐、认证第一页成功。其他版本不能因此宣称支持：需要针对具体版本验证布局与认证结果。

源库和 WAL 始终只读；仅应用相同 WAL salt 下最后一次提交之前的完整帧。在内存副本中把 SQLite 读写版本标记改为非 WAL，以免内存连接寻找外部 WAL；不修改源文件。

权限不足时使用工具提供的正常审批机制，明确读取所选账号的表情附件，不借助修改系统安全设置、关闭防护或扩大到所有账号来处理。

## 成功标准和验证

`verify --file <动图> --md5 <附件MD5>` 是离线核验，不访问微信。输出含 `format`、`size`、`frames`、`duration_ms`、`loop`、`attachment_md5_matches`、SHA-256。

脚本只有全部帧可解码、帧数大于 1 且原图 MD5 与附件一致时才导出。`visual_match_checked` 初始为 false：脚本的结构核验不等于已与用户截图完成视觉比对。Agent 应查看 `--preview-dir` 的预览并确认目标，而不是根据扩展名或输出路径推断成功。

离线维护测试：`python scripts/test_extract_sticker.py`。它使用人工生成的图像与 SQLite 数据，不读真实联系人、聊天或进程内存。跨 Python 环境借用依赖时保持 CPython 次版本和位数一致。

验证边界：离线测试覆盖精确 MD5／动画帧门槛、旧消息选择、压缩附件和资源域名；真实 4.1.15.53 提取验证了目标数据库认证、消息定位和一条原始 GIF 的完整下载。它们不等于已经穷举所有 WAL 写入时序、所有加密资源变体或未来微信版本。
