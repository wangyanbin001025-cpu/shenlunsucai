# 从零新建申论素材库网站（Render 免费版 + Neon PostgreSQL）

本说明对应本项目压缩包中的 `render.yaml`，它会创建一个新的 Render Web Service，名称默认为 `shenlun-material-library-new`。不会要求你删除旧网站。

## 重要原则

- 必须给 Render 配置 `DATABASE_URL` 并在 `/api/health` 确认 `database` 为 `postgresql`，否则程序会回退到临时 SQLite，免费 Render 上的数据可能丢失。
- 账号、会话、素材和收藏存在 PostgreSQL。`config.json`（每日更新来源、时间等）仍在 Render 临时文件系统里，免费实例休眠/重启后可能丢失；这不影响 PostgreSQL 中的账号和文章。
- 如果旧站还有数据，先从旧站导出 JSON 并保存到电脑；导出文件不包含可迁移的密码和账号。新数据库需重新注册账号，再导入 JSON。
- 不要把数据库连接字符串、`.env`、`config.json`、数据库文件或用户数据备份上传到 GitHub。

## 一、创建数据库（Neon）

1. 打开 https://neon.tech/ 并登录/注册。
2. 点击创建新 Project，项目名可以写 `shenlun-material-library-db`；Region 选择尽量靠近 Render 服务运行区域的地点（可选项以控制台为准）。
3. 创建完成后进入 **Connect** / **Connection Details**。
4. 选择刚创建的数据库与角色，勾选 **Pooled connection**（如果控制台提供此选项），复制连接字符串。
5. 连接字符串包含数据库密码，应保存在自己可访问的安全位置，不能贴到聊天、README 或 GitHub。

连接字符串通常类似下面格式（仅为格式示例，不要照抄）：

`postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require`

## 二、创建全新的 GitHub 仓库

1. 打开 https://github.com/new 。
2. Repository name 填 `shenlun-material-library-new`（也可以自定义），选择 **Private**，不要勾选自动添加 README、`.gitignore` 或 License（项目中已有文件）。
3. 点击 **Create repository**。
4. 在电脑上下载本项目 ZIP 并解压。
5. 打开解压后的 `shenlun-material-library/` 文件夹。
6. 将这个文件夹**里面的全部内容**上传到新仓库的根目录，而不是把外层 `shenlun-material-library` 文件夹再套一层。上传后，仓库首页应直接看见 `render.yaml`、`Dockerfile`、`server.py`、`db_layer.py`、`updater.py` 和 `static/` 文件夹。
7. 在 GitHub 网页中点击 **Add file → Upload files**，拖入文件和 `static` 目录中的文件；如果浏览器无法一次上传整个文件夹，可分批上传：先上传根目录文件，再新建/进入 `static` 目录并上传其中的文件。确保 `static/index.html` 和 `static/app.js` 路径正确。
8. 在页面底部填写提交说明，例如 `Initial new deployment`，点击 **Commit changes**。
9. 检查仓库根目录：`render.yaml` 必须在第一层，不能位于 `shenlun-material-library/render.yaml` 这样的二级路径。

建议先不要注册新账号，直到数据库连接验证成功。

## 三、创建新的 Render 网站

1. 打开 https://dashboard.render.com/ 并登录。
2. 确认 Render 已连接你的 GitHub 账号。若仓库列表看不到新仓库，进入 Render 的 GitHub/App 权限设置，允许 Render 访问新仓库。
3. 点击 **New + → Blueprint**（不是进入旧网站的设置页）。
4. 选择刚刚创建的 GitHub 仓库，分支选择 `main`，点击 Connect。
5. Render 会读取仓库根目录的 `render.yaml`。确认计划为 **Free**，服务名称是 `shenlun-material-library-new`，健康检查地址为 `/api/health`。
6. 如果 Blueprint 部署流程询问 `DATABASE_URL`，将第一步复制的完整 Neon 连接字符串粘贴进去。不要加引号，不要在前后加空格。
7. 点击部署/应用 Blueprint，等待构建和部署结束。若流程没有询问 `DATABASE_URL`，继续下一节手动添加。

如果提示服务名称已经被占用，先在 GitHub 仓库根目录打开 `render.yaml`，将 `shenlun-material-library-new` 改成另一个未使用名称，例如 `shenlun-material-library-new-2`，提交更改后重新创建 Blueprint。

## 四、确认 DATABASE_URL 已保存

1. 在 Render Dashboard 打开**新建的** `shenlun-material-library-new` 服务。
2. 进入 **Environment** 页面。
3. 检查是否存在环境变量 `DATABASE_URL`。如果没有，点击新增环境变量：
   - Key：`DATABASE_URL`
   - Value：粘贴 Neon 的完整连接字符串
4. 点击 Save Changes。Render 通常会因环境变量变动重新部署；若没有，进入 **Manual Deploy → Deploy latest commit**。
5. 等待最新部署显示 Live。

## 五、验证是否真的连接到了 PostgreSQL

1. 在 Render 服务页面复制该新服务的 `onrender.com` 地址。
2. 在浏览器打开 `https://你的新域名.onrender.com/api/health`。
3. 正确结果必须包含：

`"ok": true` 和 `"database": "postgresql"`

如果显示 `"database": "sqlite"`，不要在新网站录入重要数据。回到 Render 的 Environment 检查 `DATABASE_URL` 的拼写、值是否保存；同时查看 **Logs** 里的数据库连接错误。确认后重新部署再查一次。

## 六、注册、建测试文章、验证持久化

1. 先确认健康接口显示 `postgresql`。
2. 打开新网站首页，注册一个新账号并登录。
3. 新增一篇标题为“持久化测试”的文章，保存后刷新页面。
4. 退出并重新登录，确认账号与测试文章仍存在。
5. 在 Render 对新服务执行一次 **Manual Deploy → Deploy latest commit**，部署完成后重新登录并检查文章。
6. 如旧站导出过 JSON，登录新网站并使用网页导入功能导入。核对新增、更新和跳过数量，再抽查文章内容。

## 七、以后如何更新网站

1. 在本地编辑代码，或在 GitHub 直接修改文件。
2. 提交到 `main` 分支。
3. Render 自动部署；如果未自动触发，在新服务里手动部署最新 commit。
4. 更新后检查 `/api/health` 的 `database` 仍然是 `postgresql`。

## 常见问题

- **首页 404**：先检查仓库根目录是否有 `static/index.html`，并检查 Render 实际连接的是新仓库和 `main` 分支。
- **账号可以注册但之后丢失/无法登录**：优先检查 `/api/health` 是否返回 `postgresql`，而不是 `sqlite`。
- **数据库连接失败/500**：检查 `DATABASE_URL` 是否完整、有没有多余空格、Neon 项目/compute 是否可用；查看 Render Logs 的报错。
- **新站没有旧站文章**：这是新建独立数据库的正常现象。需要先从旧站导出 JSON，再登录新站导入。新旧站账号密码不会自动迁移。
- **文章条数**：代码不设 1000 篇总量上限。列表默认读取 1000 篇，接口单次最多读 5000 篇；最终容量受数据库免费套餐存储额度限制。
- **Render 免费服务休眠**：超过一段时间没有访问后会休眠，初次打开可能需要等待。这不会影响保存在 PostgreSQL 的账号和文章，但应用的本地文件（例如每日更新配置）不是持久化的。

## 免费服务注意事项

免费方案适合个人备考和试用，不代表无限空间或永久可用。数据库服务的免费额度和政策会变化；请定期通过网页导出 JSON 并备份到电脑或云盘。不要把数据库当作唯一备份。
