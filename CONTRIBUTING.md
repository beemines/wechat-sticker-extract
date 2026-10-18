# 参与贡献

欢迎改进版本兼容、附件解析、错误提示与文档。提交前请确认问题与本项目的 Windows 微信表情提取范围相关。

## 本地验证

在仓库根目录使用 Python 3.11+：

```powershell
python -m pip install -r .\requirements.txt
python .\scripts\test_extract_sticker.py
```

测试仅使用人工生成的图片、XML 和 SQLite 数据。新增测试也应使用合成数据，不提交个人账号、聊天库、密钥或私有下载地址。

## 修改代码

- 说明触发条件、修改后的行为和验证结果。
- 新增微信版本适配时，验证目标数据库认证与实际提取，不仅修改版本号。
- 保留只读源库、内存快照、原图 MD5 核验和有限读取范围。
- 修改文档媒体时，保持“界面重绘、非实际录屏”的说明。
- 保留内置组件的版权和许可证文件。

提交 Issue 时请提供已脱敏的 Windows、微信、Python 版本及错误类别。安全问题请按 [SECURITY.md](SECURITY.md) 反馈。
