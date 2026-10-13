# 申论素材库（全新网站部署版）

本项目用于创建一个独立的新申论素材库网站，推荐使用 Render Free Web Service + Neon PostgreSQL。

## 重要
- 先创建 Neon PostgreSQL，再将 `DATABASE_URL` 设置到新 Render 服务。
- 部署后检查 `/api/health` 必须返回 `"database": "postgresql"`。
- 未设置 `DATABASE_URL` 时程序会回退到 SQLite，免费 Render 本地文件不持久。
- 详细步骤请阅读 `CLOUD_DEPLOY.md`。
- 文章不受 1000 篇总量硬限制；列表默认读取 1000 条，API 单次上限 5000 条。实际容量受数据库空间和免费额度约束。
- 定期使用网站导出 JSON 备份。新数据库不自动迁移旧账号、密码或文章。
