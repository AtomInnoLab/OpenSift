# WisModel

OpenSift is powered exclusively by **WisModel**, a model specifically trained for the two core tasks of the search-verification paradigm.

## Overview

WisModel is developed by the [Fudan NLP Lab](https://nlp.fudan.edu.cn/) and [WisPaper.ai](https://wispaper.ai), as described in the paper [*WisPaper: Your AI Scholar Search Engine*](https://arxiv.org/abs/2512.06879).

**Training approach:**

- Supervised fine-tuning (SFT) on expert-annotated data
- Group Relative Policy Optimization (GRPO)
- 10 academic disciplines, 2,777 queries, 5,879 criteria

## Benchmark: Query Understanding & Criteria Generation

WisModel significantly outperforms all baseline models in generating search queries and screening criteria:

| Model | Semantic Similarity | ROUGE-1 | ROUGE-2 | ROUGE-L | BLEU | Length Ratio |
|-------|:---:|:---:|:---:|:---:|:---:|:---:|
| Qwen-Max | 78.1 | 43.2 | 23.1 | 35.8 | 11.8 | 168.9 |
| GPT-4o | 91.3 | 64.0 | 39.4 | 52.6 | 21.5 | 142.2 |
| GPT-5 | 87.0 | 53.8 | 27.6 | 41.8 | 13.2 | 163.3 |
| GLM-4-Flash | 82.2 | 50.0 | 25.8 | 42.1 | 9.9 | 167.1 |
| GLM-4.6 | 84.8 | 55.5 | 30.2 | 44.5 | 14.4 | 168.1 |
| DeepSeek-V3.2-Exp | 90.2 | 59.3 | 32.4 | 48.0 | 14.4 | 153.5 |
| **WisModel** | **94.8** | **74.9** | **54.4** | **67.7** | **39.8** | **98.2** |

## Benchmark: Paper-Criteria Matching

WisModel achieves **93.70%** overall accuracy, surpassing the next best model (Gemini3-Pro, 73.23%) by over 20 percentage points:

| Model | Insufficient Info | Reject | Somewhat Support | Support | Overall |
|-------|:---:|:---:|:---:|:---:|:---:|
| GPT-5.1 | 64.30 | 63.10 | 31.40 | 85.40 | 70.81 |
| Claude-Sonnet-4.5 | 46.00 | 66.50 | 33.30 | 87.00 | 70.62 |
| Qwen3-Max | 40.80 | 72.00 | 44.20 | 87.20 | 72.82 |
| DeepSeek-V3.2 | 57.90 | 49.20 | 45.00 | 87.00 | 66.82 |
| Gemini3-Pro | 67.40 | 66.80 | 15.90 | 91.10 | 73.23 |
| **WisModel** | **90.64** | **94.54** | **91.82** | **94.38** | **93.70** |

!!! info "WisModel's biggest advantage"
    On the hardest category — *somewhat support* — baseline models struggle at 15.9%–45.0%, while WisModel reaches **91.82%**.

## Getting Access

WisModel is available via the [WisPaper API Hub](https://wispaper.ai). Contact the team to obtain your API key.

## Citation

```bibtex
@article{ju2025wispaper,
  title={WisPaper: Your AI Scholar Search Engine},
  author={Li Ju and Jun Zhao and Mingxu Chai and Ziyu Shen and ...},
  journal={arXiv preprint arXiv:2512.06879},
  year={2025}
}
```
