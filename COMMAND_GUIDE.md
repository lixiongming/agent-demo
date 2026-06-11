# 命令使用指南

## 📍 命令执行位置说明

### 1️⃣ 项目根目录命令（推荐）

**位置：** `/Users/lxm/Desktop/workspace/agent/agent-demo`

```bash
# 启动所有 Docker 服务（包括自动备份）
./docker/start.sh start

# 停止所有服务
./docker/start.sh stop

# 备份 MySQL
./docker/start.sh backup

# 恢复 MySQL
./docker/start.sh restore

# 查看日志
./docker/start.sh logs

# 其他命令
./docker/start.sh rebuild
./docker/start.sh import
./docker/start.sh help
```

---

### 2️⃣ Ops 目录命令（运维脚本）

**位置：** `/Users/lxm/Desktop/workspace/agent/agent-demo/ops`

```bash
cd ops

# 备份 MySQL
./backup_mysql.sh

# 恢复 MySQL
./restore_mysql.sh [备份文件]
```

---

## 🕐 自动定时备份

**配置文件：** `docker/Dockerfile.backup`

- **执行时间：** 每天凌晨 2:00
- **执行方式：** Docker 容器内 cron 自动执行
- **日志位置：** `logs/backup.log`

**启动自动备份：**
```bash
./docker/start.sh start  # 会自动启动备份容器
```

---

## 📁 备份文件位置

**存储目录：** `data/backups/mysql/`

**文件格式：** `agent_db_YYYYMMDD_HHMMSS.sql.gz`

**查看备份：**
```bash
ls -lh data/backups/mysql/
```

---

## 💡 推荐使用方式

### 最简单的方式（推荐）
```bash
# 在项目根目录执行
./backup.sh  # 一键备份
./restore.sh  # 一键恢复
```

### Docker 部署方式
```bash
# 启动所有服务（包括自动备份）
./docker/start.sh start

# 手动备份
./docker/start.sh backup

# 手动恢复
./docker/start.sh restore
```

---

## 🎯 快速参考

| 命令 | 执行位置 | 说明 |
|------|---------|------|
| `./docker/start.sh backup` | 项目根目录 | ⭐ 一键备份（最简单） |
| `./docker/start.sh restore` | 项目根目录 | ⭐ 一键恢复（最简单） |
| `cd ops && ./backup_mysql.sh` | ops 目录 | 备份（详细版） |
| `cd ops && ./restore_mysql.sh` | ops 目录 | 恢复（详细版） |
| `./docker/start.sh start` | 项目根目录 | 启动所有服务+自动备份 |

---

## ✅ 最佳实践

1. **日常使用：** 在项目根目录执行 `./docker/start.sh backup` 或 `./docker/start.sh restore`
2. **生产部署：** 使用 `./docker/start.sh start` 启动服务，自动定时备份
3. **查看备份：** 备份文件自动保存在 `data/backups/` 目录