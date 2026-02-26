<p align="center">
  <img src="docs/opensift-banner.png" alt="OpenSift Banner" width="800" />
</p>

<p align="center">
  <a href="https://github.com/AtomInnoLab/OpenSift/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
  <a href="https://github.com/AtomInnoLab/OpenSift"><img src="https://img.shields.io/badge/version-0.1.0-green.svg" alt="Version"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://github.com/AtomInnoLab/OpenSift"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <a href="https://arxiv.org/abs/2512.06879"><img src="https://img.shields.io/badge/arXiv-2512.06879-b31b1b.svg" alt="arXiv"></a>
  <a href="https://wispaper.ai"><img src="https://img.shields.io/badge/Origin-WisPaper-8A2BE2.svg" alt="WisPaper"></a>
</p>

<p align="center">
  <b><a href="README.md">English</a> | <a href="README_zh.md">中文</a></b>
</p>

**让现有搜索系统快速接入 AI 能力的开源增强层。**

OpenSift 脱胎于 [WisPaper](https://wispaper.ai) —— 由复旦 NLP 实验室和 WisPaper.ai 联合打造的 AI 学术搜索平台。其核心的「搜索-验证」范式（AI 查询规划 + LLM 结果验证）已在论文 [*WisPaper: Your AI Scholar Search Engine*](https://arxiv.org/abs/2512.06879) 中详细阐述。OpenSift 将这一经过验证的范式提取为**通用的开源中间件**，可以接入任何搜索后端，让每一个搜索引擎都能获得同样的 AI 能力。

OpenSift 不是一个搜索引擎，也不是问答系统。它是一个轻量级的 AI 中间层，接入你现有的搜索后端（Elasticsearch、OpenSearch、Solr、MeiliSearch、Wikipedia、AtomWalker 学术搜索、或任何自定义 API），为其注入两项核心 AI 能力：

1. **智能查询规划（Query Planning）** — 将用户的自然语言问题分解为精准的搜索问句和量化的筛选条件
2. **结果智能验证（Result Verification）** — 用 LLM 逐条验证搜索结果是否真正符合筛选条件，给出判定依据

---

## 它解决什么问题？

传统搜索系统返回的是**关键词匹配**的结果，用户必须自己逐条阅读、筛选。OpenSift 在搜索结果返回后自动完成 AI 筛选，将结果分为：

- **完全匹配（Perfect）** — 所有条件全部满足
- **部分匹配（Partial）** — 满足部分条件，供人工复核
- **不相关（Rejected）** — 自动过滤，不展示

<p align="center">
  <img src="docs/architecture.jpg" alt="OpenSift 架构图" width="700" />
</p>

## 快速开始

### 环境要求

- Python 3.11+
- [Poetry](https://python-poetry.org/) 2.0+

### 安装

```bash
git clone https://github.com/AtomInnoLab/OpenSift.git
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

# 配置 WisModel API Key（唯一支持的模型）
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
  "perfect_results": [
    {
      "result": {
        "source_adapter": "wikipedia",
        "title": "基于CNN的太阳能即时预报",
        "content": "...",
        "source_url": "https://..."
      },
      "validation": { "criteria_assessment": [...], "summary": "..." },
      "classification": "perfect",
      "weighted_score": 0.95
    }
  ],
  "partial_results": [ ... ],
  "rejected_results": [ ... ],
  "rejected_count": 5,
  "total_scanned": 20
}
```

### 流式模式（SSE）

添加 `"stream": true` 即可开启流式输出。管线各阶段以独立的 SSE 事件推送，客户端可实时渲染进度：

```
管线：  criteria → search_complete → result × N → done
                                                  (或 error)
```

**请求：**

```bash
curl -N -X POST http://localhost:8080/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "有哪些关于太阳能即时预报的深度学习论文？",
    "options": {
      "max_results": 10,
      "verify": true,
      "stream": true,
      "adapters": ["wikipedia"]
    }
  }'
```

**SSE 事件流（完整示例）：**

```
event: criteria
data: {"request_id":"req_a1b2c3d4e5f6","query":"有哪些关于太阳能即时预报的深度学习论文？","criteria_result":{"search_queries":["\"solar nowcasting\" deep learning","太阳能 即时预报 深度学习"],"criteria":[{"criterion_id":"c1","type":"task","name":"太阳能即时预报","description":"论文必须涉及太阳辐照度即时预报","weight":0.6},{"criterion_id":"c2","type":"method","name":"深度学习方法","description":"论文必须采用深度学习或神经网络方法","weight":0.4}]}}

event: search_complete
data: {"total_results":15,"search_queries_count":2,"results":[{"source_adapter":"wikipedia","title":"Solar nowcasting","content":"Solar nowcasting refers to...","source_url":"https://en.wikipedia.org/wiki/Solar_nowcasting"},{"source_adapter":"wikipedia","title":"Deep learning for weather prediction","content":"...","source_url":"https://..."}]}

event: result
data: {"index":1,"total":15,"scored_result":{"result":{"source_adapter":"wikipedia","title":"Solar nowcasting","content":"...","source_url":"https://..."},"validation":{"criteria_assessment":[{"criterion_id":"c1","assessment":"support","explanation":"直接涉及太阳能即时预报"},{"criterion_id":"c2","assessment":"support","explanation":"讨论了基于 CNN 的方法"}],"summary":"高度相关的太阳能即时预报深度学习论文"},"classification":"perfect","weighted_score":0.95}}

event: result
data: {"index":2,"total":15,"scored_result":{"result":{"source_adapter":"wikipedia","title":"天气预报","content":"...","source_url":"https://..."},"validation":{"criteria_assessment":[{"criterion_id":"c1","assessment":"somewhat_support","explanation":"提及太阳能但侧重一般气象"},{"criterion_id":"c2","assessment":"support","explanation":"使用了神经网络方法"}],"summary":"部分相关 — 通用天气预报"},"classification":"partial","weighted_score":0.5}}

...

event: done
data: {"request_id":"req_a1b2c3d4e5f6","status":"completed","total_scanned":15,"perfect_count":3,"partial_count":4,"rejected_count":8,"processing_time_ms":5200}
```

**事件类型说明：**

| 事件 | 发送次数 | 载荷字段 | 说明 |
|------|---------|---------|------|
| `criteria` | 1 次 | `request_id`, `query`, `criteria_result` | 规划完成 — 包含生成的搜索子查询和筛选条件 |
| `search_complete` | 1 次 | `total_results`, `search_queries_count`, `results` | 搜索完成 — `results` 包含所有原始搜索结果（验证前），每条带 `source_adapter` |
| `result` | N 次 | `index`, `total`, `scored_result` 或 `raw_result` | 单条结果验证完成 — classify=true 时为 `scored_result`（含 `classification` + `weighted_score`），classify=false 时为 `raw_result` |
| `done` | 1 次 | `request_id`, `status`, `total_scanned`, `perfect_count`, `partial_count`, `rejected_count`, `processing_time_ms` | 全部完成 — 最终统计汇总 |
| `error` | 0–1 次 | `request_id`, `error`, `processing_time_ms` | 不可恢复错误 — 包含错误信息 |

**客户端处理（JavaScript）：**

```javascript
const resp = await fetch("/v1/search", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "太阳能即时预报的深度学习方法",
    options: { stream: true, max_results: 10 }
  })
});

const reader = resp.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const parts = buffer.split("\n\n");
  buffer = parts.pop();

  for (const part of parts) {
    let eventType = "", dataStr = "";
    for (const line of part.split("\n")) {
      if (line.startsWith("event:")) eventType = line.slice(6).trim();
      else if (line.startsWith("data:")) dataStr = line.slice(5).trim();
    }
    if (!eventType || !dataStr) continue;
    const data = JSON.parse(dataStr);

    switch (eventType) {
      case "criteria":
        console.log("筛选条件:", data.criteria_result);
        break;
      case "search_complete":
        console.log(`找到 ${data.total_results} 条结果，开始验证...`);
        break;
      case "result":
        const r = data.scored_result;
        console.log(`[${r.result.source_adapter}] [${r.classification}] ${r.result.title}`);
        break;
      case "done":
        console.log(`完成: ${data.perfect_count} 完美, ${data.partial_count} 部分匹配, 耗时 ${data.processing_time_ms}ms`);
        break;
      case "error":
        console.error("错误:", data.error);
        break;
    }
  }
}
```

**Python SDK（同步）：**

```python
from opensift.client import OpenSiftClient

client = OpenSiftClient("http://localhost:8080")
for event in client.search_stream("太阳能即时预报的深度学习方法"):
    evt = event["event"]
    data = event["data"]

    if evt == "criteria":
        print(f"搜索子查询: {data['criteria_result']['search_queries']}")
    elif evt == "search_complete":
        print(f"搜索完成: 共 {data['total_results']} 条结果")
    elif evt == "result":
        r = data["scored_result"]
        print(f"  [{r['result']['source_adapter']}] [{r['classification']}] {r['result']['title']}")
    elif evt == "done":
        print(f"完成: {data['perfect_count']}完美 / {data['partial_count']}部分 / {data['rejected_count']}拒绝, 耗时 {data['processing_time_ms']}ms")
```

**Python SDK（异步）：**

```python
from opensift.client import AsyncOpenSiftClient

async with AsyncOpenSiftClient("http://localhost:8080") as client:
    async for event in client.search_stream("太阳能即时预报"):
        if event["event"] == "result":
            r = event["data"]["scored_result"]
            print(f"[{r['result']['source_adapter']}] {r['result']['title']}")
```

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
      "result": { "source_adapter": "wikipedia", "title": "...", "content": "..." },
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
  "rejected_results": [],
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
│   │   ├── meilisearch/          # MeiliSearch 适配器
│   │   └── wikipedia/            # Wikipedia 适配器
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
| **Wikipedia** | Wikipedia（全语种） | `wikipedia-api` | 多语言百科全书文章搜索 |

实现 `SearchAdapter` 接口即可接入自定义搜索后端。

**配置示例（`opensift-config.yaml`）：**

```yaml
search:
  default_adapter: meilisearch    # 或: wikipedia
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

### 结果字段

每条搜索结果中包含 `source_adapter` 字段，标识该结果来自哪个 adapter：

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_adapter` | `string` | 返回该结果的搜索适配器名称（如 `"wikipedia"`, `"atomwalker"`） |
| `result_type` | `string` | 结果类型，用于选择验证 prompt 模板（`"paper"`, `"generic"`） |
| `title` | `string` | 标题 |
| `content` | `string` | 正文内容（摘要、描述等） |
| `source_url` | `string` | 来源链接 |
| `fields` | `object` | 其他领域特定的元数据 |

`source_adapter` 字段出现在 `perfect_results`、`partial_results`、`rejected_results`、`raw_results` 和流式 `result` 事件中。当多个 adapter 同时激活时，可用此字段区分结果来源。

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
    print(f"[{r['result']['source_adapter']}] {r['result']['title']} — {r['classification']}")

# 流式模式 — 验证完一条返回一条
for event in client.search_stream("solar nowcasting deep learning"):
    if event["event"] == "result":
        scored = event["data"]["scored_result"]
        print(f"[{scored['result']['source_adapter']}] [{scored['classification']}] {scored['result']['title']}")

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

## WisModel — 专为搜索验证训练的 AI 模型

OpenSift 仅支持 [WisModel](https://arxiv.org/abs/2512.06879)，一个专门为搜索验证范式的两大核心任务训练的模型：**问题理解与验证条件生成**和**论文-条件匹配验证**。WisModel 在专家标注的 10 个学术领域数据（2,777 条查询、5,879 条验证条件）上，经过监督微调（SFT）+ 群组相对策略优化（GRPO）训练而成。

### 问题理解与验证条件生成

WisModel 在从自然语言查询生成搜索问句和筛选条件方面，显著超越所有基线模型（包括 GPT-5、GPT-4o、DeepSeek-V3.2）：

| 模型 | 语义相似度 | ROUGE-1 | ROUGE-2 | ROUGE-L | BLEU | 长度比 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| Qwen-Max | 78.1 | 43.2 | 23.1 | 35.8 | 11.8 | 168.9 |
| GPT-4o | 91.3 | 64.0 | 39.4 | 52.6 | 21.5 | 142.2 |
| GPT-5 | 87.0 | 53.8 | 27.6 | 41.8 | 13.2 | 163.3 |
| GLM-4-Flash | 82.2 | 50.0 | 25.8 | 42.1 | 9.9 | 167.1 |
| GLM-4.6 | 84.8 | 55.5 | 30.2 | 44.5 | 14.4 | 168.1 |
| DeepSeek-V3.2-Exp | 90.2 | 59.3 | 32.4 | 48.0 | 14.4 | 153.5 |
| **WisModel** | **94.8** | **74.9** | **54.4** | **67.7** | **39.8** | **98.2** |

### 论文-条件匹配验证

WisModel 以 93.70% 的总体准确率遥遥领先，超出第二名（Gemini3-Pro，73.23%）20 个百分点以上。其优势在最难的「部分支持（somewhat support）」类别上尤为突出 —— 基线模型仅 15.9%–45.0%，WisModel 达到 91.82%：

| 模型 | 信息不足 | 拒绝 | 部分支持 | 支持 | 总体准确率 |
|------|:---:|:---:|:---:|:---:|:---:|
| GPT-5.1 | 64.30 | 63.10 | 31.40 | 85.40 | 70.81 |
| Claude-Sonnet-4.5 | 46.00 | 66.50 | 33.30 | 87.00 | 70.62 |
| Qwen3-Max | 40.80 | 72.00 | 44.20 | 87.20 | 72.82 |
| DeepSeek-V3.2 | 57.90 | 49.20 | 45.00 | 87.00 | 66.82 |
| Gemini3-Pro | 67.40 | 66.80 | 15.90 | 91.10 | 73.23 |
| **WisModel** | **90.64** | **94.54** | **91.82** | **94.38** | **93.70** |

> WisModel 通过 [WisPaper API Hub](https://wispaper.ai) 提供服务。请联系团队获取 API Key。

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
make test          # 运行全部测试
make test-unit     # 仅运行单元测试
make lint          # 代码检查 (ruff)
make lint-fix      # 自动修复
make format        # 代码格式化
make check         # 完整 CI 检查 (lint + format + typecheck + test)
make clean         # 清理构建产物
```

### 集成测试

集成测试通过 Docker 启动真实的搜索后端来测试每个适配器。支持按需测试单个适配器，无需启动全部容器。

**测试单个适配器**（仅启动对应的 Docker 容器）：

```bash
make test-es          # Elasticsearch
make test-opensearch  # OpenSearch
make test-solr        # Solr
make test-meili       # MeiliSearch
make test-wikipedia   # Wikipedia（无需 Docker）

# 通用写法：
make test-adapter ADAPTER=elasticsearch
```

**测试全部适配器：**

```bash
make test-backends-up    # 启动全部 4 个 Docker 后端
make test-integration    # 运行全部集成测试
make test-backends-down  # 停止并移除容器
```

也可以直接使用 pytest marker：

```bash
# 单个适配器
pytest tests/integration/ -m elasticsearch

# 多个适配器
pytest tests/integration/ -m "solr or meilisearch"
```

| 适配器 | Docker 镜像 | 端口 | Marker |
|--------|------------|------|--------|
| Elasticsearch | `elasticsearch:8.17.0` | 9200 | `elasticsearch` |
| OpenSearch | `opensearch:2.18.0` | 9201 | `opensearch` |
| Solr | `solr:9.7` | 8983 | `solr` |
| MeiliSearch | `meilisearch:v1.12` | 7700 | `meilisearch` |
| Wikipedia | *（公共 API）* | — | `wikipedia` |

## 配置说明

OpenSift 支持三层配置（优先级从高到低）：

1. **环境变量** — `OPENSIFT_` 前缀，嵌套用双下划线
2. **YAML 文件** — `opensift-config.yaml`
3. **默认值**

### 关键环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENSIFT_AI__API_KEY` | WisModel API Key | — |
| `OPENSIFT_AI__BASE_URL` | WisModel API 地址 | WisPaper API Hub |
| `OPENSIFT_AI__MODEL_PLANNER` | WisModel 规划版本 | `WisModel-20251110` |
| `OPENSIFT_AI__MODEL_VERIFIER` | WisModel 验证版本 | `WisModel-20251110` |
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
- [x] Web UI 调试面板
- [x] 更多搜索后端适配器 (OpenSearch, Solr, MeiliSearch, Wikipedia)
- [x] 全适配器 Docker 集成测试

## 引用

如果你在研究中使用了 OpenSift 或搜索验证范式，请引用 WisPaper 论文：

```bibtex
@article{ju2025wispaper,
  title={WisPaper: Your AI Scholar Search Engine},
  author={Li Ju and Jun Zhao and Mingxu Chai and Ziyu Shen and Xiangyang Wang and Yage Geng and Chunchun Ma and Hao Peng and Guangbin Li and Tao Li and Chengyong Liao and Fu Wang and Xiaolong Wang and Junshen Chen and Rui Gong and Shijia Liang and Feiyan Li and Ming Zhang and Kexin Tan and Jujie Ye and Zhiheng Xi and Shihan Dou and Tao Gui and Yuankai Ying and Yang Shi and Yue Zhang and Qi Zhang},
  journal={arXiv preprint arXiv:2512.06879},
  year={2025}
}
```

## License

[Apache License 2.0](LICENSE)

---

**OpenSift** — 脱胎于 [WisPaper](https://wispaper.ai)，为每一个搜索引擎而生。为现有搜索系统注入 AI 智能。
