# Agora 代理操作指南

本文件适用于整个仓库。修改 `frontend/` 时还必须遵守
`frontend/AGENTS.md`。这里记录长期有效的产品操作、开发、治理和发布流程；
不要把某个临时 PR 的票数、账号或凭据写进本文件。

## 项目与线上环境

- 生产站：<https://agora.invisible.best/>
- GitHub 仓库：<https://github.com/snowflake-chan/agora>
- 生产 API 前缀：`https://agora.invisible.best/api/v1`
- 本地完整站点默认地址：`http://localhost:8080`
- `frontend/`：Astro SSR + Svelte 5 + TypeScript
- `backend/`：FastAPI + SQLAlchemy + Alembic
- PostgreSQL 保存业务数据，Redis 用于实时事件和限流。
- Nginx 将 `/api/` 转发到后端，其余请求转发到 Astro 前端。

## 网站使用流程

### 账号与内容

1. 在 `/register` 注册。注册成功后会通过 HttpOnly Cookie 自动登录。
2. 在 `/login` 登录，在个人资料页修改昵称、简介和密码。
3. 首页同时展示帖子和变更提案。用户可以选择：
   - `For you`：综合新鲜度、有效互动、关注关系和治理状态。
   - `Trending`：近期互动增长较快的内容。
   - `Following`：只显示已关注作者的内容，并按时间排序。
   - `Latest`：完整时间线，按发布时间排序。
4. 登录用户可以发布帖子、回复、点赞、分享、关注作者和接收通知。
5. 首页通过 `/api/v1/posts/-/feed/stream` 的 SSE 事件刷新内容。发布事件应触发
   首屏数据重新获取；不要用高频轮询替代现有实时机制。

### 设置

设置入口位于 `/settings`。偏好保存在当前浏览器的 `localStorage`，不是账号级设置。

- 语言：英语 `en`、日语 `ja`、繁体中文 `zh-TW`；默认英语。
- 不提供简体中文 `zh-CN`。新增界面文案时必须同步维护三种现有语言。
- 主题：Agora 默认主题、TikTok、Claude、Apple、Google。
- 亮度：亮色或暗色；默认暗色。
- 首页布局：
  - `split`：大屏左侧列表、右侧正文。
  - `pages`：点击列表项后进入独立详情页。
  - 小屏始终使用独立详情页，不强制双栏。
- 动效：跟随系统、舒适、减少动效。

不要改变现有默认视觉，除非任务明确要求。设计参考位于
`frontend/designs/`，它们是参考资产，不是独立运行的产品页面。

## 本地开发

### Docker 全栈

优先使用 Docker 验证前后端集成：

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f backend frontend nginx
```

停止服务时使用：

```powershell
docker compose down
```

除非用户明确要求删除本地数据，不要运行 `docker compose down -v`。

Docker 启动后，后端容器会先运行 `alembic upgrade head`，再启动 Uvicorn。
本地默认凭据只用于本地 Compose，不得复制到生产配置。

### 前端

要求 Node.js `>=22.12.0`。从 `frontend/` 运行：

```powershell
pnpm install
pnpm astro dev --background
pnpm test
pnpm build
```

用 `pnpm astro dev status`、`pnpm astro dev logs` 和
`pnpm astro dev stop` 管理后台开发服务器。

### 后端

要求 Python 3.12。依赖位于 `backend/requirements-dev.txt`。后端测试需要可用的
PostgreSQL 和 Redis，并正确设置 `DATABASE_URL`、`JWT_SECRET` 和 `REDIS_URL`。

从 `backend/` 运行：

```powershell
python -m pip install -r requirements-dev.txt
alembic upgrade head
python -m pytest tests/ -v --tb=short
```

数据库结构变化必须新增 Alembic migration。迁移应能处理生产环境中断后重试的情况，
并同时验证升级路径；不要只修改 ORM 模型。

### 提交前验证

按改动范围选择验证，但用户可见或跨模块改动至少执行：

```powershell
Set-Location frontend
pnpm test
pnpm build
Set-Location ..\backend
python -m pytest tests/ -v --tb=short
Set-Location ..
docker compose build
```

CI 在 PR 和 `main` push 上运行后端测试，以及前后端 Docker 镜像构建。不要把本地通过
当成 CI 已通过，也不要在检查仍运行或失败时提交治理投票。

## PR、民主治理与发布

生产变更必须走以下顺序：

1. 从最新 `main` 创建功能分支。代理分支默认使用 `codex/<topic>`。
2. 完成范围内实现、迁移、测试和文档，检查工作树中是否有用户的无关改动。
3. 推送分支并创建目标为 `main` 的 GitHub PR。
4. 将 PR 标记为 Ready for review，确认它不是 Draft、仍然 Open、可合并且 CI 通过。
5. 登录生产站，在 `/patches/new` 创建变更草稿：
   - 标题说明用户可感知的结果。
   - 正文说明改动、原因、风险和验证结果。
   - `pr_number` 必须对应同一仓库中的真实 PR。
   - 正文应包含 GitHub PR 链接。
6. 检查草稿无误后提交投票。标准投票窗口为 72 小时；活跃创作者在提交时
   若过去 90 天内至少有一项本人提案已合并，则本次窗口固定为 24 小时。
7. 社区投票和讨论结束后，由服务端计票；不要手动合并或提前部署。
8. 提案通过后，服务端使用 `GITHUB_TOKEN` 合并 PR，然后启动部署助手。
9. 在 GitHub、生产站和生产日志三处核对最终状态，再宣告发布完成。

一个独立改动只创建一个活动提案。被新 PR 完整取代的冲突 PR 不应重复发起投票；
应在旧 PR 公开说明替代关系，并在替代 PR 合并后关闭旧 PR。

多个 PR 修改同一文件时，按依赖顺序治理。在前一个 PR 合并后、后一个提案计票前，
必须把最新 `main` 合入后一个分支，解决冲突、重新测试并推送，确保治理通过后能够合并。

## 计票规则与状态

状态主路径为：

```text
draft -> voting -> passed -> merged
                   |          |
                   |          +-> deployment starts
                   +-> failed when GitHub merge fails

voting -> rejected when the proposal lacks a strict majority
```

计票实现位于 `backend/app/patches/routes.py`：

- 可投 `for`、`against`、`abstain`，同一账号可以修改自己的票。
- 投票窗口在提交时由服务端判定并形成快照：标准窗口为 72 小时；活跃创作者窗口为
  24 小时。活跃创作者指过去 90 天内至少有一项本人提案进入 `merged` 的作者。
- 开发者、管理员、公会角色或客户端请求参数都不能直接获得或指定 24 小时窗口。
  窗口缩短不改变 PR 就绪检查、多数决门槛、自动计票和合并流程。
- `total = for + against + abstain`。
- 至少有一票，且 `for > total / 2` 才通过。
- 平票、无票或赞成票未超过全部票的一半都会被拒绝。
- `abstain` 计入总票数，因此会提高通过所需的赞成票门槛。
- 列表或详情请求会触发已到期提案的后台计票；后端启动时也会执行 reconciliation。

投票截止后，自动化可以读取提案列表或详情并轮询终态，但不得新增票、修改数据库状态
或绕过民主结果。

## 治理 API

浏览器和自动化均使用 Cookie 会话。所有写操作都应带
`Content-Type: application/json` 和现有会话 Cookie。

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/logout

GET  /api/v1/patches
POST /api/v1/patches
GET  /api/v1/patches/{patch_id}
POST /api/v1/patches/{patch_id}/submit
POST /api/v1/patches/{patch_id}/vote
GET  /api/v1/patches/{patch_id}/votes
GET  /api/v1/patches/{patch_id}/comments
POST /api/v1/patches/{patch_id}/comments
```

创建提案的请求体：

```json
{
  "title": "Describe the outcome",
  "content": "Markdown summary, risks, tests, and PR link",
  "pr_number": 123
}
```

投票请求体：

```json
{
  "choice": "for"
}
```

`choice` 只能是 `for`、`against` 或 `abstain`。自动化不得输出密码、Cookie、
GitHub Token 或 `.env` 内容；调试日志也不得记录这些值。

## 合并与部署实现

生产环境需要：

- `GITHUB_REPO=snowflake-chan/agora`
- 有合并权限的 `GITHUB_TOKEN`
- 唯一且足够强的 `JWT_SECRET`
- `DEPLOY_ENABLED=true`
- 正确挂载到 `/repo` 的宿主机仓库
- Docker socket `/var/run/docker.sock`

提案通过后，后端调用 GitHub Pull Request Merge API。成功后
`deploy.sh` 启动脱离 Compose 生命周期的部署助手，并使用固定容器名作为部署锁。
助手执行：

```text
git pull --ff-only
docker compose build
docker compose up --detach --remove-orphans
```

部署助手故障不能把已成功合并的提案改成 `failed`；此时提案应保持 `merged`，
并单独排查部署。生产代码更新不是浏览器热更新：必须等待治理合并、镜像构建和容器重建，
然后再刷新页面验证。

## 故障处理

- `rejected`：尊重结果，不直接合并。根据讨论修改 PR，公开说明上次结果后再重新提案。
- `failed`：先检查 PR 是否冲突、是否仍为 Draft/Open、CI 是否通过和 Token 权限。
  修复原分支并重新验证；如果当前 API 没有重试入口，创建一份透明关联旧提案的新提案。
- `passed` 长时间未变化：检查后端 reconciliation 日志和 GitHub Merge API 错误。
- `merged` 但线上未更新：检查部署助手、仓库是否可 fast-forward、Compose 构建和服务日志。
- 首页未实时刷新：检查 Redis、SSE `/api/v1/posts/-/feed/stream`、浏览器连接状态和
  `publish_feed_event` 调用，不要先用页面定时刷新掩盖故障。
- 数据库启动失败：检查 Alembic 版本表、migration 是否可重试和 PostgreSQL 健康状态；
  不要删除生产卷来“修复”迁移。

常用只读诊断：

```powershell
gh pr view <number> --repo snowflake-chan/agora
gh pr checks <number> --repo snowflake-chan/agora
docker compose ps
docker compose logs --tail 200 backend
docker ps -a --filter name=agora-deploy
```

## 治理与安全边界

- 不得使用多个账号为同一提案重复投票，也不得代替真实社区制造多数。
- 不得强制合并、直接 push 到 `main`、修改票数或手工把提案状态改成通过。
- 不得把未通过治理的提交直接部署到生产。
- 不得为同一逻辑改动创建多个并行活动提案。
- 不得把密钥、账号密码、Cookie、生产数据库内容或个人信息提交到仓库。
- 不得声称“已合并”或“已上线”，除非 GitHub 状态、提案状态和生产站验证均支持该结论。
- 遇到社区拒绝、无法合并或部署失败时，保留证据并报告真实状态，不掩盖失败。

## 修改约定

- 保持改动范围与任务一致，复用现有组件、Svelte store、API 客户端和设计 token。
- 前端图标优先使用现有 Lucide 库，不手写重复 SVG。
- 新增界面文案要补齐 `en`、`ja`、`zh-TW`，默认回退英语，并更新 i18n 测试。
- 新增主题必须保持默认主题不变，同时覆盖亮色、暗色和响应式状态。
- 首页布局改动必须同时验证大屏 `split`、大屏 `pages` 和移动端详情页。
- Feed 或通知改动必须验证初次加载、分页、SSE 更新、重连、空状态和错误状态。
- 后端共享行为变更应增加回归测试；API 契约变化必须同步更新前端调用。
- 不要修改或删除与任务无关的用户改动，不要使用破坏性 Git 命令。
