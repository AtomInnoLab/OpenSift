<p align="center">
  <img src="docs/opensift-banner.png" alt="OpenSift Banner" width="800" />
</p>

<p align="center">
  <a href="https://github.com/opensift/opensift/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
  <a href="https://github.com/opensift/opensift"><img src="https://img.shields.io/badge/version-0.1.0-green.svg" alt="Version"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://github.com/opensift/opensift"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
</p>

<p align="center">
  <b><a href="README.md">English</a> | <a href="README_zh.md">中文</a></b>
</p>

**让现有搜索系统快速接入 AI 能力的开源增强层。**

OpenSift 不是一个搜索引擎，也不是问答系统。它是一个轻量级的 AI 中间层，接入你现有的搜索后端（Elasticsearch、OpenSearch、Solr、MeiliSearch、AtomWalker 学术搜索、或任何自定义 API），为其注入两项核心 AI 能力：

1. **智能查询规划（Query Planning）** — 将用户的自然语言问题分解为精准的搜索问句和量化的筛选条件
2. **结果智能验证（Result Verification）** — 用 LLM 逐条验证搜索结果是否真正符合筛选条件，给出判定依据

---

## 它解决什么问题？

传统搜索系统返回的是**关键词匹配**的结果，用户必须自己逐条阅读、筛选。OpenSift 在搜索结果返回后自动完成 AI 筛选，将结果分为：

- **完全匹配（Perfect）** — 所有条件全部满足
- **部分匹配（Partial）** — 满足部分条件，供人工复核
- **不相关（Rejected）** — 自动过滤，不展示

<p align="center">
  <img src="docs/architecture.png" alt="OpenSift 架构图" width="700" />
</p>

## 快速开始

### 环境要求

- Python 3.11+
- [Poetry](https://python-poetry.org/) 2.0+

### 安装

```bash
git clone https://github.com/opensift/opensift.git
cd opensift

# 开发环境
make dev-setup

# 或直接用 Poetry
poetry install
```

### 配置

```bash
cp opensift-config.example.yaml opensift-config.yaml
cp .env.example .env

# 配置 WisModel API Key（默认模型，专门训练了 Planning 和 Verification 能力）
# 编辑 .env 文件设置: OPENSIFT_AI__API_KEY=your-wismodel-key

# 配置搜索后端 (默认 AtomWalker 学术搜索)
# 编辑 .env 文件设置: OPENSIFT_SEARCH__ADAPTERS__ATOMWALKER__API_KEY=wsk_xxxxx
```

### 启动

```bash
# 开发模式 (自动重载)
make run

# 生产模式
make run-prod
```

- API 地址: `http://localhost:8080`
- 接口文档: `http://localhost:8080/docs`
- 调试面板: `http://localhost:8080/debug`

## API 使用

同一个 `/v1/search` 端点支持两种输出模式：

| 模式 | 参数 | Content-Type | 说明 |
|------|------|-------------|------|
| **完整模式**（默认） | `stream: false` | `application/json` | 所有结果验证完毕后一次性返回 |
| **流式模式** | `stream: true` | `text/event-stream` (SSE) | 验证完一条立即推送一条 |

### 完整模式（默认）

```bash
curl -X POST http://localhost:8080/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "有哪些关于太阳能即时预报的深度学习论文？",
    "options": {
      "max_results": 10,
      "verify": true
    }
  }'
```

**响应示例（简化）：**

```json
{
  "request_id": "req_a1b2c3d4e5f6",
  "status": "completed",
  "processing_time_ms": 3200,
  "criteria_result": {
    "search_queries": [
      "\"solar nowcasting\" deep learning",
      "solar irradiance forecasting neural network"
    ],
    "criteria": [
      {
        "criterion_id": "c1",
        "type": "task",
        "name": "太阳能即时预报研究",
        "description": "论文需要研究太阳能辐照度的即时预报",
        "weight": 0.6
      },
      {
        "criterion_id": "c2",
        "type": "method",
        "name": "使用深度学习方法",
        "description": "论文需要使用深度学习或神经网络方法",
        "weight": 0.4
      }
    ]
  },
  "perfect_results": [ ... ],
  "partial_results": [ ... ],
  "rejected_count": 5,
  "total_scanned": 20
}
```

### 流式模式（SSE）

添加 `"stream": true` 即可开启流式输出。验证完一条结果立即推送，无需等待全部完成：

```bash
curl -N -X POST http://localhost:8080/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "有哪些关于太阳能即时预报的深度学习论文？",
    "options": {
      "max_results": 10,
      "verify": true,
      "stream": true
    }
  }'
```

**SSE 事件流示例：**

```
event: criteria
data: {"request_id":"req_a1b2c3d4e5f6","query":"...","criteria_result":{...}}

event: result
data: {"index":1,"total":10,"scored_result":{"result":{...},"validation":{...},"classification":"perfect","weighted_score":0.95}}

event: result
data: {"index":2,"total":10,"scored_result":{"result":{...},"validation":{...},"classification":"partial","weighted_score":0.5}}

...

event: done
data: {"request_id":"req_a1b2c3d4e5f6","status":"completed","total_scanned":10,"perfect_count":3,"partial_count":4,"rejected_count":3,"processing_time_ms":5200}
```

**事件类型说明：**

| 事件 | 触发时机 | 载荷 |
|------|---------|------|
| `criteria` | 查询规划完成 | `request_id`, `query`, `criteria_result` |
| `result` | 每条结果验证 + 分类完成 | `index`, `total`, `scored_result` |
| `done` | 全部完成 | 统计汇总（各分类计数、耗时） |
| `error` | 发生错误 | `error` 错误信息 |

### 独立查询规划（Standalone Plan）

`/v1/plan` 端点将 Planner 作为独立能力输出 — 仅生成搜索子查询和筛选条件，不执行搜索和验证：

```bash
curl -X POST http://localhost:8080/v1/plan \
  -H "Content-Type: application/json" \
  -d '{
    "query": "太阳能即时预报的深度学习论文"
  }'
```

**响应：**

```json
{
  "request_id": "plan_a1b2c3d4e5f6",
  "query": "太阳能即时预报的深度学习论文",
  "criteria_result": {
    "search_queries": [
      "\"solar nowcasting\" deep learning",
      "太阳能辐照预测 神经网络"
    ],
    "criteria": [
      {
        "criterion_id": "c1",
        "type": "task",
        "name": "太阳能即时预报研究",
        "description": "论文必须涉及太阳能辐照即时预报",
        "weight": 0.6
      },
      {
        "criterion_id": "c2",
        "type": "method",
        "name": "深度学习方法",
        "description": "论文必须使用深度学习或神经网络方法",
        "weight": 0.4
      }
    ]
  },
  "processing_time_ms": 850
}
```

适用场景：
- 调试和检查 Planner 输出
- 将生成的搜索查询接入自有搜索流水线
- 为批量或增量工作流预先计算筛选条件

### 跳过分类器（输出原始验证结果）

设置 `"classify": false` 可跳过最终的分类器，直接返回原始的验证结果。每条结果包含 LLM 评估，但不含 perfect/partial/reject 分类标签：

```bash
curl -X POST http://localhost:8080/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "太阳能即时预报的深度学习论文",
    "options": { "classify": false, "max_results": 10 }
  }'
```

**响应（简化）：**

```json
{
  "request_id": "req_abc123",
  "status": "completed",
  "criteria_result": { ... },
  "raw_results": [
    {
      "result": { "title": "...", "content": "..." },
      "validation": {
        "criteria_assessment": [
          { "criterion_id": "c1", "assessment": "support", "explanation": "..." }
        ],
        "summary": "..."
      }
    }
  ],
  "perfect_results": [],
  "partial_results": [],
  "total_scanned": 10
}
```

### 跳过验证（搜索但不做 LLM 验证）

```bash
curl -X POST http://localhost:8080/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "RAG retrieval augmented generation survey",
    "options": { "verify": false, "max_results": 20 }
  }'
```

### 健康检查

```bash
curl http://localhost:8080/v1/health
curl http://localhost:8080/v1/health/adapters
```

## 项目结构

```
opensift/
├── src/opensift/
│   ├── core/                     # 核心 AI 流水线
│   │   ├── engine.py             # 引擎编排器 (Plan → Search → Verify → Classify)
│   │   ├── planner/planner.py    # 查询规划: 生成搜索问句 + 筛选条件
│   │   ├── verifier/verifier.py  # 结果验证: LLM 逐条验证是否符合条件
│   │   ├── classifier.py         # 结果分类: Perfect / Partial / Reject
│   │   └── llm/                  # LLM 客户端 + 提示词模板
│   │       ├── client.py
│   │       └── prompts.py
│   ├── adapters/                 # 搜索后端适配器 (可插拔)
│   │   ├── base/                 # 抽象接口 + 注册机制
│   │   ├── atomwalker/           # AtomWalker 学术搜索适配器
│   │   ├── elasticsearch/        # Elasticsearch 适配器
│   │   ├── opensearch/           # OpenSearch 适配器
│   │   ├── solr/                 # Apache Solr 适配器
│   │   └── meilisearch/          # MeiliSearch 适配器
│   ├── models/                   # 数据模型 (Pydantic)
│   │   ├── criteria.py           # 搜索条件模型 (Criterion, CriteriaResult)
│   │   ├── assessment.py         # 验证结果模型 (ValidationResult, ScoredResult)
│   │   ├── result.py             # 通用搜索结果模型 (ResultItem)
│   │   ├── paper.py              # 论文元数据模型 (PaperInfo → ResultItem)
│   │   ├── query.py              # 请求模型
│   │   └── response.py           # 响应模型
│   ├── client/                   # Python SDK (同步/异步客户端)
│   │   └── client.py
│   ├── api/                      # REST API (FastAPI)
│   │   ├── static/debug.html     # Web UI 调试面板
│   │   └── v1/endpoints/
│   │       ├── search.py         # 搜索 (完整 + 流式)
│   │       └── batch.py          # 批量搜索 + 导出
│   ├── config/                   # 配置管理 (YAML + 环境变量)
│   └── observability/            # 日志
├── tests/                        # 测试
├── deployments/docker/           # Docker 部署
├── pyproject.toml
└── opensift-config.example.yaml
```

## 核心概念

### Query Planner

接收用户的自然语言问题，通过 LLM 生成：

- **搜索问句** (`search_queries`) — 2-4 条精准的搜索关键词/短语，用于从搜索后端检索
- **筛选条件** (`criteria`) — 1-4 条量化的验证规则，每条包含类型、描述和权重

### Result Verifier

对搜索返回的每条结果，逐条比对筛选条件（适用于任何搜索对象：论文、产品、新闻等）：

- **Support** — 条件明确满足，附带证据引用
- **Somewhat Support** — 部分相关但不完全满足
- **Reject** — 明确不满足
- **Insufficient Information** — 信息不足以判断

### Classifier

根据验证结果自动分类：

| 分类 | 规则 |
|------|------|
| Perfect | 所有条件均为 Support |
| Partial | 至少一个非时间类条件为 Support 或 Somewhat Support |
| Reject | 所有条件均为 Reject，或仅时间条件通过 |

### 适配器

通过适配器模式接入任意搜索后端。内置 5 个适配器：

| 适配器 | 搜索后端 | 额外依赖 | 说明 |
|--------|---------|---------|------|
| **AtomWalker** | AtomWalker ScholarSearch | — | 学术论文搜索，保留 JCR/CCF/中科院分区等完整元数据 |
| **Elasticsearch** | Elasticsearch v8+ | `pip install opensift[elasticsearch]` | BM25 全文搜索 + 高亮 |
| **OpenSearch** | OpenSearch v2+ | `pip install opensift[opensearch]` | AWS 兼容的 Elasticsearch 分支 |
| **Solr** | Apache Solr v8+ | — (使用 httpx) | edismax 全文搜索 + JSON Request API |
| **MeiliSearch** | MeiliSearch | — (使用 httpx) | 即时搜索、自动纠错 |

实现 `SearchAdapter` 接口即可接入自定义搜索后端。

**配置示例（`opensift-config.yaml`）：**

```yaml
search:
  default_adapter: meilisearch
  adapters:
    meilisearch:
      enabled: true
      hosts: ["http://localhost:7700"]
      index_pattern: "documents"
      api_key: "your-master-key"
    solr:
      enabled: true
      hosts: ["http://localhost:8983/solr"]
      index_pattern: "my_collection"
```

## Python SDK

OpenSift 自带 Python 客户端库，支持同步和异步两种模式：

```python
from opensift.client import OpenSiftClient

client = OpenSiftClient("http://localhost:8080")

# 独立查询规划 — 仅获取搜索子查询和筛选条件
plan = client.plan("太阳能即时预报的深度学习方法")
print(plan["criteria_result"]["search_queries"])
print(plan["criteria_result"]["criteria"])

# 完整模式 — 搜索 + 验证全流程
response = client.search("太阳能即时预报的深度学习方法")
for r in response["perfect_results"]:
    print(r["result"]["title"], r["classification"])

# 流式模式 — 验证完一条返回一条
for event in client.search_stream("solar nowcasting deep learning"):
    if event["event"] == "result":
        scored = event["data"]["scored_result"]
        print(f"[{scored['classification']}] {scored['result']['title']}")

# 批量搜索 + 导出 CSV
batch = client.batch_search(
    ["solar nowcasting", "wind power forecasting", "battery degradation"],
    max_results=5,
    export_format="csv",
)
print(batch["export_data"])  # CSV 文本
```

异步版本：

```python
from opensift.client import AsyncOpenSiftClient

async with AsyncOpenSiftClient("http://localhost:8080") as client:
    # 独立查询规划
    plan = await client.plan("solar nowcasting")
    print(plan["criteria_result"])

    # 完整搜索
    response = await client.search("solar nowcasting")

    # 流式
    async for event in client.search_stream("solar nowcasting"):
        print(event)
```

## 本地 LLM 支持

OpenSift 的 LLM 客户端兼容所有 OpenAI API 格式的服务，因此可以直接使用 Ollama、vLLM 等本地部署的模型：

**Ollama:**

```bash
# 启动 Ollama
ollama serve
ollama pull qwen2.5:14b

# 配置 OpenSift
OPENSIFT_AI__PROVIDER=local
OPENSIFT_AI__API_KEY=ollama
OPENSIFT_AI__BASE_URL=http://localhost:11434/v1
OPENSIFT_AI__MODEL_PLANNER=qwen2.5:14b
OPENSIFT_AI__MODEL_VERIFIER=qwen2.5:14b
```

**vLLM:**

```bash
# 启动 vLLM
vllm serve Qwen/Qwen2.5-14B-Instruct --port 8000

# 配置 OpenSift
OPENSIFT_AI__PROVIDER=local
OPENSIFT_AI__API_KEY=token-abc123
OPENSIFT_AI__BASE_URL=http://localhost:8000/v1
OPENSIFT_AI__MODEL_PLANNER=Qwen/Qwen2.5-14B-Instruct
OPENSIFT_AI__MODEL_VERIFIER=Qwen/Qwen2.5-14B-Instruct
```

## Web UI 调试面板

OpenSift 内置了一个开箱即用的 Web 调试面板，启动服务后访问：

```
http://localhost:8080/debug
```

| 标签页 | 功能 |
|--------|------|
| **Search** | 单次查询（完整模式），可视化展示 Pipeline 各阶段、生成的搜索条件、结果分类和评估详情 |
| **Stream** | 流式查询（SSE），实时逐条展示验证结果 |
| **Batch** | 批量查询，支持导出 CSV/JSON |
| **Event Log** | 所有 API 交互的实时日志，便于调试 |

特点：

- 零依赖 — 纯 HTML/CSS/JS，无需 Node.js 或任何前端构建工具
- Pipeline 可视化 — 直观展示 Planning → Searching → Verifying → Classifying 各阶段状态和耗时
- 健康检查 — 右上角实时显示服务状态和版本
- 暗色主题 — 开发者友好的深色界面

## 开发

```bash
make test          # 运行测试
make lint          # 代码检查 (ruff)
make lint-fix      # 自动修复
make format        # 代码格式化
make check         # 完整 CI 检查 (lint + format + typecheck + test)
make clean         # 清理构建产物
```

## 配置说明

OpenSift 支持三层配置（优先级从高到低）：

1. **环境变量** — `OPENSIFT_` 前缀，嵌套用双下划线
2. **YAML 文件** — `opensift-config.yaml`
3. **默认值**

### 关键环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENSIFT_AI__API_KEY` | WisModel / LLM API Key | — |
| `OPENSIFT_AI__BASE_URL` | LLM API 地址 (OpenAI 兼容) | WisModel endpoint |
| `OPENSIFT_AI__MODEL_PLANNER` | 查询规划模型 | `WisModel-20251110` |
| `OPENSIFT_AI__MODEL_VERIFIER` | 结果验证模型 | `WisModel-20251110` |
| `OPENSIFT_SEARCH__DEFAULT_ADAPTER` | 默认搜索后端 | `atomwalker` |

## Docker

```bash
# 最小部署
docker-compose -f deployments/docker/docker-compose.minimal.yml up

# 开发环境 (OpenSift + Elasticsearch)
docker-compose -f deployments/docker/docker-compose.dev.yml up
```

## 路线图

- [x] LLM 查询规划 (搜索问句 + 筛选条件生成)
- [x] LLM 结果验证 (逐条结果 × 逐条条件)
- [x] 结果分类器 (Perfect / Partial / Reject)
- [x] AtomWalker 学术搜索适配器
- [x] Elasticsearch 适配器
- [x] REST API (FastAPI)
- [x] 流式输出 (SSE)
- [x] Python SDK (同步 + 异步)
- [x] 批量搜索与导出 (CSV / JSON)
- [x] 本地 LLM 支持 (Ollama, vLLM)
- [x] Web UI 调试面板
- [x] 更多搜索后端适配器 (OpenSearch, Solr, MeiliSearch)

## License

[Apache License 2.0](LICENSE)

---

**OpenSift** — 为现有搜索系统注入 AI 智能。
