# Philosophia RAG Service

基于 Oscar Brenifier 哲学实践语料的 RAG 检索增强生成服务。

## 技术架构

- **向量数据库**: Qdrant (支持 dense + sparse 混合检索)
- **Embedding**: BGE-M3 (同时输出 dense 和 sparse 向量)
- **Reranker**: BGE-Reranker-v2-m3 (精排 Top5)
- **LLM**: DeepSeek API

## 跨语言策略

采用文档预翻译方案：
- Dense 检索: 在英文原文上做 (BGE-M3 跨语言能力强)
- Sparse 检索: 在中文译文上做 (确保中文关键词命中)
- Reranker: 用中文 query 精排中文译文
- LLM: 基于双语文本生成中文回答

## 项目结构

```
rag-service/
├── config/settings.py      # 全局配置
├── core/
│   ├── chunker.py          # 文本分块
│   ├── translator.py        # 英→中翻译 (DeepSeek API)
│   ├── embedder.py          # BGE-M3 embedding
│   ├── reranker.py          # BGE-Reranker 精排
│   └── llm_client.py        # DeepSeek API 封装
├── db/qdrant_client.py     # Qdrant 操作封装
├── pipeline/
│   ├── indexing.py          # 离线索引 pipeline
│   └── retrieval.py         # 在线检索 pipeline
├── api/
│   ├── router.py            # FastAPI 路由
│   └── schemas.py           # 请求/响应模型
├── scripts/
│   └── index_documents.py   # 索引入口脚本
├── main.py                  # FastAPI 应用入口
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
```

### 3. 下载模型

```bash
# BGE-M3 (~2.2GB)
huggingface-cli download BAAI/bge-m3 --local-dir ./models/bge-m3

# BGE-Reranker (~600MB)
huggingface-cli download BAAI/bge-reranker-v2-m3 --local-dir ./models/bge-reranker-v2-m3
```

### 4. 启动 Qdrant

```bash
docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

### 5. 索引文档

```bash
# 将 txt 文件放入 data/raw/ 目录
python scripts/index_documents.py
```

### 6. 启动服务

```bash
python main.py
# 或
uvicorn main:app --reload
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `POST /api/query` | 查询 | 返回答案和来源文档 |
| `POST /api/query/stream` | 流式查询 | SSE 流式返回答案 |
| `POST /api/index` | 索引 | 触发文档索引 |
| `GET /api/health` | 健康检查 | 服务状态 |
| `GET /api/stats` | 统计 | 集合统计信息 |

## API 文档

启动服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Docker 部署

```bash
# 启动全部服务 (Qdrant + RAG)
docker-compose up -d
```

## 使用示例

### 查询

```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是苏格拉底式追问？"}'
```

### 流式查询

```bash
curl -X POST "http://localhost:8000/api/query/stream" \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是苏格拉底式追问？"}'
```

### 触发索引

```bash
curl -X POST "http://localhost:8000/api/index" \
  -H "Content-Type: application/json" \
  -d '{"recreate": true}'
```

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `CHUNK_SIZE` | 512 | 文本分块大小 |
| `CHUNK_OVERLAP` | 64 | 分块重叠大小 |
| `RETRIEVAL_TOP_K` | 20 | 检索召回数量 |
| `RERANK_TOP_K` | 5 | 精排返回数量 |
| `LLM_TEMPERATURE` | 0.7 | LLM 生成温度 |
