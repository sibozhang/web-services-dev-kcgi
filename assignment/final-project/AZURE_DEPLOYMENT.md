# Azure 正式部署清单

本项目在 Azure 上继续保持严格 C/S 分离：两个独立的 Linux App Service 分别运行 Client 与 Flask REST API，数据存入 Azure Database for PostgreSQL Flexible Server，镜像存入 Azure Container Registry。浏览器只访问两个 HTTPS 域名；App Service 负责 TLS 终止，容器内部使用 HTTP `2027`。

> 下文 `<...>` 都是占位符。生产 Secret 不得写入 Git、Dockerfile、镜像 tag 或命令历史；建议在 Azure Portal 的 App Service「环境变量」中录入，正式环境可进一步改为 Key Vault 引用。

## 0. 发布前门槛

在项目根目录完成：

```bash
docker compose build api client
docker compose run --rm api pytest -q
docker compose up -d
curl -k https://localhost:2028/api/health
curl -k https://localhost:2027/healthz
```

必须确认：测试全绿、两个健康检查为 `200`、`.env` 被 Git 忽略、镜像 tag 不是 `latest`。推荐使用 `v1.0.0` 或 Git commit SHA。

## 1. 资源命名与登录

安装 Azure CLI 后：

```bash
az login
az account set --subscription "<subscription-id-or-name>"

export RG=mlb-dugout-rg
export LOCATION=japaneast
export ACR=<globally-unique-acr-name>
export PLAN=mlb-dugout-plan
export API_APP=<globally-unique-api-app-name>
export CLIENT_APP=<globally-unique-client-app-name>
export PG_SERVER=<globally-unique-postgres-name>
export TAG=v1.0.0

az group create --name "$RG" --location "$LOCATION"
az acr create --resource-group "$RG" --name "$ACR" --sku Basic
```

正式发布若要使用 staging slot 和一键回滚，App Service Plan 选 `S1` 或更高；只做课程演示且可接受直接部署时可选 `B1`。

```bash
az appservice plan create \
  --resource-group "$RG" \
  --name "$PLAN" \
  --is-linux \
  --sku S1
```

## 2. 创建 PostgreSQL

在 Azure Portal 创建 **Azure Database for PostgreSQL Flexible Server**：

1. Region 选择与 App Service 相同的 `Japan East`。
2. PostgreSQL 版本选择 16；为管理员设置独立强密码。
3. 创建数据库 `mlb`。
4. 生产推荐 Private access/VNet；课程部署可用 Public access，但只加入实际客户端 IP与 API 的出站 IP，不要长期使用允许所有 Azure 服务的宽泛规则。
5. 记下主机名 `<server>.postgres.database.azure.com`。

CLI 创建数据库（服务器已在 Portal 创建后）：

```bash
az postgres flexible-server db create \
  --resource-group "$RG" \
  --server-name "$PG_SERVER" \
  --database-name mlb
```

连接字符串格式：

```text
postgresql+psycopg://<admin-user>:<url-encoded-password>@<server>.postgres.database.azure.com:5432/mlb?sslmode=require
```

密码中的 `@`、`:`、`/`、`#` 等必须 URL encode。`sslmode=require` 保证传输加密；若配置了受信任根证书，生产可提升为 `verify-full`。

## 3. 构建不可变镜像

使用 ACR 云端构建，不需要先在本机 `docker push`：

```bash
az acr build \
  --registry "$ACR" \
  --image "mlb-dugout-api:$TAG" \
  --file Dockerfile .

az acr build \
  --registry "$ACR" \
  --image "mlb-dugout-client:$TAG" \
  --file client/Dockerfile client
```

确认两个 repository 与 tag 都存在：

```bash
az acr repository list --name "$ACR" --output table
az acr repository show-tags --name "$ACR" --repository mlb-dugout-api --output table
az acr repository show-tags --name "$ACR" --repository mlb-dugout-client --output table
```

## 4. 创建两个独立 App Service

```bash
ACR_HOST=$(az acr show --name "$ACR" --query loginServer --output tsv)

az webapp create \
  --resource-group "$RG" \
  --plan "$PLAN" \
  --name "$API_APP" \
  --container-image-name "$ACR_HOST/mlb-dugout-api:$TAG"

az webapp create \
  --resource-group "$RG" \
  --plan "$PLAN" \
  --name "$CLIENT_APP" \
  --container-image-name "$ACR_HOST/mlb-dugout-client:$TAG"
```

分别为两个 Web App 启用 system-assigned managed identity，并授予 ACR Pull：

```bash
ACR_ID=$(az acr show --name "$ACR" --query id --output tsv)
API_PRINCIPAL=$(az webapp identity assign --resource-group "$RG" --name "$API_APP" --query principalId --output tsv)
CLIENT_PRINCIPAL=$(az webapp identity assign --resource-group "$RG" --name "$CLIENT_APP" --query principalId --output tsv)

az role assignment create --assignee-object-id "$API_PRINCIPAL" --assignee-principal-type ServicePrincipal --scope "$ACR_ID" --role AcrPull
az role assignment create --assignee-object-id "$CLIENT_PRINCIPAL" --assignee-principal-type ServicePrincipal --scope "$ACR_ID" --role AcrPull

az webapp config set --resource-group "$RG" --name "$API_APP" --generic-configurations '{"acrUseManagedIdentityCreds": true}'
az webapp config set --resource-group "$RG" --name "$CLIENT_APP" --generic-configurations '{"acrUseManagedIdentityCreds": true}'
```

强制 HTTPS、TLS 1.2、Always On，并告诉 App Service 容器监听 `2027`：

```bash
for APP in "$API_APP" "$CLIENT_APP"; do
  az webapp update --resource-group "$RG" --name "$APP" --https-only true
  az webapp config set --resource-group "$RG" --name "$APP" \
    --always-on true --min-tls-version 1.2 --http20-enabled true
  az webapp config appsettings set --resource-group "$RG" --name "$APP" \
    --settings WEBSITES_PORT=2027 TLS_MODE=proxy
done
```

外部地址为：

```text
https://<API_APP>.azurewebsites.net
https://<CLIENT_APP>.azurewebsites.net
```

## 5. PostgreSQL 网络规则

若选择 Public access，先读取 API 可能使用的全部出站 IP：

```bash
az webapp show \
  --resource-group "$RG" \
  --name "$API_APP" \
  --query possibleOutboundIpAddresses \
  --output tsv
```

把返回的每个 IP 作为单 IP firewall rule 加入 PostgreSQL。部署初始化时若从本机 Docker 直连 Azure PostgreSQL，还要临时加入本机公网 IP；初始化完成后删除该临时规则。若使用 Private access，则为 API App 配置 VNet Integration，并让 PostgreSQL 与 API 可通过私网互通。

## 6. API App Settings

在 Portal：API App Service → Settings → Environment variables 中设置：

```text
FLASK_ENV=production
WEBSITES_PORT=2027
TLS_MODE=proxy
DATABASE_URL=<Azure PostgreSQL SQLAlchemy URL>
MLB_SEASON=2026
APP_TIMEZONE=Asia/Tokyo
JWT_COOKIE_SAMESITE=None
SESSION_COOKIE_SAMESITE=None
BASE_URL=https://<API_APP>.azurewebsites.net
CLIENT_URL=https://<CLIENT_APP>.azurewebsites.net
CORS_ORIGINS=https://<CLIENT_APP>.azurewebsites.net
GOOGLE_LOGIN_REDIRECT_URI=https://<API_APP>.azurewebsites.net/api/auth/google/callback
GOOGLE_CALENDAR_REDIRECT_URI=https://<API_APP>.azurewebsites.net/api/calendar/callback
GEMINI_MODEL=gemini-flash-latest
```

以下 Secret 只填值，不写入文档或仓库：

```text
SECRET_KEY=<至少 32 bytes 随机值>
JWT_SECRET_KEY=<另一份至少 32 bytes 随机值>
GEMINI_API_KEY=<Gemini key>
GOOGLE_CLIENT_ID=<Google OAuth client id>
GOOGLE_CLIENT_SECRET=<Google OAuth client secret>
TOKEN_ENCRYPTION_KEY=<Fernet key>
```

生成随机值：

```bash
openssl rand -hex 32
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

不要修改 `TOKEN_ENCRYPTION_KEY`，否则数据库中已有 Google Calendar token 将无法解密。

## 7. Client App Settings

Client 只需要：

```text
WEBSITES_PORT=2027
TLS_MODE=proxy
API_BASE_URL=https://<API_APP>.azurewebsites.net
```

保存配置后重启两个 App Service：

```bash
az webapp restart --resource-group "$RG" --name "$API_APP"
az webapp restart --resource-group "$RG" --name "$CLIENT_APP"
```

验证 runtime config 没有误指向 localhost：

```bash
curl "https://<CLIENT_APP>.azurewebsites.net/runtime-config.js"
```

## 8. Google Cloud Console 生产配置

在同一个 Web OAuth Client 中设置：

- Authorized JavaScript origin：`https://<CLIENT_APP>.azurewebsites.net`
- Authorized redirect URI：`https://<API_APP>.azurewebsites.net/api/auth/google/callback`
- Authorized redirect URI：`https://<API_APP>.azurewebsites.net/api/calendar/callback`

必须完全匹配 scheme、host、path，末尾不要额外添加 `/`。开发用 localhost URI 可以保留。若 OAuth Consent Screen 仍为 Testing，把演示账号加入 Test users；正式公开前再完成 Google 要求的发布/验证流程。

## 9. 数据迁移与首次同步

API 入口启动时会执行 `flask db upgrade`。首次发布保持单实例，待迁移完成再扩容，避免多个实例同时跑 Alembic。

最稳妥的首次数据同步方式，是在允许访问 PostgreSQL 的管理机上使用同一 API 镜像。先创建一个**不提交 Git**的 `.env.azure`，包含 API App 的生产变量，然后：

```bash
az acr login --name "$ACR"
docker pull "$ACR_HOST/mlb-dugout-api:$TAG"

docker run --rm --env-file .env.azure "$ACR_HOST/mlb-dugout-api:$TAG" \
  flask --app wsgi:app db upgrade
docker run --rm --env-file .env.azure "$ACR_HOST/mlb-dugout-api:$TAG" \
  flask --app wsgi:app sync-teams
docker run --rm --env-file .env.azure "$ACR_HOST/mlb-dugout-api:$TAG" \
  flask --app wsgi:app sync-schedule --start 2026-03-25 --end 2026-09-27
docker run --rm --env-file .env.azure "$ACR_HOST/mlb-dugout-api:$TAG" \
  flask --app wsgi:app sync-standings --season 2026
docker run --rm --env-file .env.azure "$ACR_HOST/mlb-dugout-api:$TAG" \
  flask --app wsgi:app sync-rosters --season 2026
docker run --rm --env-file .env.azure "$ACR_HOST/mlb-dugout-api:$TAG" \
  flask --app wsgi:app sync-team-stats --season 2026
docker run --rm --env-file .env.azure "$ACR_HOST/mlb-dugout-api:$TAG" \
  flask --app wsgi:app sync-player-stats --season 2026
```

如果 MLB schedule 单次范围过大，继续使用项目已验证的 7 天窗口重复执行 `sync-schedule`，最后一段截止 `2026-09-27`。所有同步均为 upsert，可安全重跑。

## 10. Azure 定时同步

应用内部没有调度器。推荐用 **Azure Container Apps Jobs** 运行同一个 API 镜像及 Flask CLI，并向 Job 注入与 API 相同的 `DATABASE_URL`、时区和必要 Secret。

关键命令是：

```bash
flask --app wsgi:app sync-current-games --lookback-days 1
```

它先刷新 JST 昨日至今日的 schedule，使 Scheduled 能推进为 Live/Final，再同步所有 live feed、局分和比赛数据。推荐安排：

| Job | 命令 | UTC cron | 说明 |
|---|---|---|---|
| current games | `sync-current-games --lookback-days 1` | `*/1 * * * *` | 每分钟；Container Apps Job 的标准 cron 最小粒度是 1 分钟 |
| standings | `sync-standings --season 2026` | `*/15 * * * *` | 每 15 分钟 |
| team/player stats | 对应两个 stats 命令 | `*/30 * * * *` | 每 30 分钟，可拆成两个 Job |
| rosters | `sync-rosters --season 2026` | `0 */6 * * *` | 每 6 小时 |

Container Apps Jobs 的 cron 按 UTC 解释。每个 Job 设 `parallelism=1`、`replica completion count=1`，并避免同时部署第二套调度器。若严格要求 20–30 秒级 live 更新，标准 scheduled job 无法满足，需要连续运行的 worker/Container App；本课程版本采用 1 分钟刷新，避免在 Web 进程内加入循环调度器。

部署 Job 后先手动 Start 一次，确认执行历史为 Succeeded，并在数据库确认 `games.last_synced_at`/快照时间更新。

## 11. 健康检查、日志与告警

在 Portal 为两个 App Service 配置 Health check：

- API：`/api/health`
- Client：`/healthz`

两个路径必须返回 `200`，不能跳转。启用 Application Logging、Log stream 和 Application Insights。命令行查看：

```bash
az webapp log config --resource-group "$RG" --name "$API_APP" --docker-container-logging filesystem
az webapp log tail --resource-group "$RG" --name "$API_APP"
az webapp log tail --resource-group "$RG" --name "$CLIENT_APP"
```

至少为以下情况设置告警：API 5xx、Health check 失败、PostgreSQL 连接/存储异常、Container Apps Job 失败、MLB 429/5xx、Gemini 429/5xx、Google OAuth/Calendar 401/403。

## 12. 上线 Smoke Test

按顺序完成：

1. Client `/healthz` 和 API `/api/health` 返回 200。
2. Client `runtime-config.js` 指向生产 API。
3. 未登录：主页、日程、排名、球队、球员选择正常；受保护资源返回 JSON 401 并跳登录页。
4. 邮箱注册、登录、退出可用，浏览器 Network 中 Cookie 为 HttpOnly + Secure。
5. 首页手动同步按钮可恢复原色，API Log 出现同步完成。
6. Scheduled、Live、Final 各抽查一场；局分、boxscore、Active Roster 与链接正常。
7. 中/日文切换覆盖指定文案，AI 输出语言与界面一致。
8. Google 登录与 Calendar 独立授权；重复添加同一比赛不会创建重复事件。
9. Gemini 球员分析与赛前/赛中/赛后分析可生成；429 时页面仍可浏览。
10. Container Apps Job 手动执行成功，随后确认 cron 自动产生下一次运行。

## 13. Staging、切换与回滚

使用 S1+ 时，为 Client 与 API 都创建 `staging` slot。先把新 tag 部署到 staging，复制非 slot setting；生产 Secret 与域名相关设置标记为 Deployment slot setting。验证完健康检查和 smoke test 后先切 API，再切 Client。

回滚顺序：

1. 保留上一版不可变镜像 tag。
2. 应用代码问题：swap 回上一 slot，或把两个 App Service 镜像 tag 一起切回上一版。
3. 数据库迁移优先向前修复；只有 downgrade 已在备份副本验证时才执行。
4. PostgreSQL 严重数据问题使用 Point-in-Time Restore 到新服务器，核验后切换 `DATABASE_URL`。
5. 回滚后重新执行两项 health check、登录、主页和一场比赛详情 smoke test。

不要删除当前生产镜像或数据库，直到新版本至少稳定运行一个完整比赛日。
