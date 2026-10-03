# SailCloth-01 · 帆布浸渍防水台

帆布间布卷与浸渍固化台账基线项目（Django 5 + DRF + Vue 3 SPA）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Django 5 · DRF · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端反代 `/api`） |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01`
- **前端**：http://localhost:3740
- **API**：http://localhost:8740
- **PostgreSQL**：localhost:6140

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。后端 entrypoint 执行 migrate + seed。

## 业务规则

布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。

- **已固化卷拨回原布**：必须持有该卷当前**未作废**的客户画押编号（6 位数字）；无有效编号一律中文挡住，作废编号不放行。画押不参与固化判断。
- **客户画押（CustomerMark）**：操作工可落编号（必须正好 6 位数字）；作废仅管理员；同一卷未作废编号最多一条（应用层 + 数据库部分唯一约束双重兜底，并发交叉只留一条）。

规则实现：`backend/core/rules.py`（`can_mark_roll_cured` / `can_revert_to_raw`）

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

- **登录** → 进入主工作面
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`）；点击打开右侧面板登记 `DipRun`、切换固化状态；架下为浸渍流水次要信息流
- **`/marks` 客户画押专页**：筛选有效/已作废、落下 6 位编号、管理员作废
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD
- 侧栏已收成完整顶栏（晾晒架 / 客户画押 / 台账入口）

API（JWT）：`/api/lofts|rolls|dips|marks|dashboard/`，作废 `POST /api/marks/{id}/revoke/`（仅管理员）。

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
