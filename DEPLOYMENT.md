# Philosophia RAG Service - 生产环境部署指南

## 目录
- [快速开始](#快速开始)
- [Docker Compose 部署](#docker-compose-部署)
- [手动部署](#手动部署)
- [环境变量配置](#环境变量配置)
- [健康检查](#健康检查)
- [负载测试](#负载测试)
- [故障排除](#故障排除)

---

## 快速开始

### 1. 克隆代码
```bash
git clone https://github.com/zhangpink-eng/philosophy-rag-service.git
cd philosophy-rag-service
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件填入你的 API Key
```

### 3. 启动服务
```bash
docker-compose up -d
```

服务将在 http://localhost:8000 启动

---

## Docker Compose 部署

### 启动所有服务
```bash
docker-compose up -d
```

### 查看服务状态
```bash
docker-compose ps
```

### 查看日志
```bash
docker-compose logs -f rag-service
```

### 停止服务
```bash
docker-compose down
```

### 重新构建
```bash
docker-compose up -d --build
```

---

## 手动部署

### 前置要求
- Python 3.11+
- PostgreSQL 15+
- Qdrant 向量数据库
- Redis 7+ (可选)

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动 PostgreSQL
```bash
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=philosophy_db \
  postgres:15
```

### 3. 启动 Qdrant
```bash
docker run -d -p 6333:6333 \
  -p 6334:6334 \
  qdrant/qdrant:latest
```

### 4. 启动服务
```bash
python main.py
```

---

## 环境变量配置

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 必填 |
| `DATABASE_URL` | PostgreSQL 连接字符串 | postgresql://postgres:postgres@localhost:5432/philosophy_db |
| `QDRANT_HOST` | Qdrant 主机 | localhost |
| `QDRANT_PORT` | Qdrant 端口 | 6333 |
| `POSTGRES_HOST` | PostgreSQL 主机 | localhost |
| `POSTGRES_PORT` | PostgreSQL 端口 | 5432 |
| `POSTGRES_USER` | PostgreSQL 用户 | postgres |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | postgres |
| `POSTGRES_DB` | PostgreSQL 数据库名 | philosophy_db |
| `REDIS_HOST` | Redis 主机 | localhost |
| `REDIS_PORT` | Redis 端口 | 6379 |

---

## 健康检查

### API 健康检查
```bash
curl http://localhost:8000/
```

预期响应:
```json
{
  "service": "Philosophia RAG Service",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/api/health"
}
```

### 数据库连接检查
```bash
curl http://localhost:8000/api/health
```

### Docker 健康检查
```bash
docker inspect --format='{{.State.Health.Status}}' philosophia-rag
```

---

## 负载测试

### 运行负载测试
```bash
# 安装测试依赖
pip install aiohttp

# 运行负载测试
python scripts/load_test.py

# 运行 WebSocket 测试
python scripts/load_test.py --websocket
```

### 测试场景
- RAG 查询: 50 并发请求
- TTS 语音合成: 30 并发请求
- 安全检查: 100 并发请求

### 性能目标
- 平均响应时间 < 2 秒
- P95 响应时间 < 5 秒
- 成功率 > 95%

---

## 故障排除

### 服务无法启动

1. 检查端口占用:
```bash
lsof -i :8000
```

2. 检查日志:
```bash
docker-compose logs rag-service
```

### 数据库连接失败

1. 检查 PostgreSQL 是否运行:
```bash
docker ps | grep postgres
```

2. 测试连接:
```bash
psql -h localhost -U postgres -d philosophy_db
```

### 向量检索失败

1. 检查 Qdrant 是否运行:
```bash
curl http://localhost:6333/health
```

2. 检查集合是否存在:
```bash
curl http://localhost:6333/collections
```

### 常见错误

**502 Bad Gateway**
- 后端服务未启动或崩溃
- 检查 `docker-compose logs rag-service`

**Connection Refused**
- 服务未监听指定端口
- 确认 docker-compose 端口映射正确

**Import Error**
- 依赖未安装
- 运行 `pip install -r requirements.txt`

---

## 生产环境建议

### 1. 安全配置
- 使用 HTTPS 反向代理 (Nginx/Caddy)
- 配置防火墙规则
- 定期更新依赖

### 2. 监控
- 集成 Prometheus 指标
- 配置日志聚合
- 设置告警规则

### 3. 扩展
- 使用 Kubernetes 进行容器编排
- 配置自动扩缩容
- 使用负载均衡器

### 4. 备份
- 定期备份 PostgreSQL 数据
- 备份 Qdrant 索引
- 测试恢复流程

---

## 更新日志

### v1.0.0 (Phase 7)
- 管理后台 API
- Docker 镜像优化
- 负载测试脚本
- 生产环境部署指南
