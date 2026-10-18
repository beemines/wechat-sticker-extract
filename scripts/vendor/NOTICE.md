# 第三方 helper

`wechat_meme_export/{__init__,memory,decrypt,exporter}.py` 来自
https://github.com/Ant39140/wechat_meme_export ，MIT License，完整许可见
[LICENSE.wechat_meme_export.txt](LICENSE.wechat_meme_export.txt)。这些文件在打包时原样保留。

本技能的 `extract_sticker.py` 仅调用 `scan_wcdb_config_key` 精确目标数据库查找、页面解密和图片载荷解密；不调用上游 `scan_pid_for_db_key` 的全内存候选字符串扫描，不调用批量导出入口。

资源地址和动态图片来自用户选定消息记录；本技能不附带账号、密钥、聊天库或样例用户表情。
