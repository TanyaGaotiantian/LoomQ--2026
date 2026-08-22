# LoomQ 量子接入平权计划 · 队伍实现说明（Team: TanyaGaotiantian）

> 本目录是正式提交的构建与评测根目录（`starter_kit/`），也是本次比赛全部
> 实现、测试、证据与文档的入口。所有 Level（L1/L2/L3）与 Bonus 均已实现，
> 公开自测全部通过（`python3 evaluator.py --level all` → 6/6 PASS）。

---

## 目录

0. [🧑‍🏫 大白话学习笔记（从零到提交，初中生也能懂）](docs/LEARNING_JOURNEY.md)
0a. [🔬 知识深讲（每个知识点讲透）](docs/QUANTUM_DEEP_DIVE.md)
0b. [🐣 小白复现完全指南（照做即可）](docs/REPRODUCE_GUIDE.md)
1. [我们做了什么（一句话）](#1-我们做了什么)
2. [评分目标与达成情况](#2-评分目标与达成情况)
3. [系统架构](#3-系统架构)
4. [L1 通用中间层：三平台统一转译与执行（45 分）](#4-l1-通用中间层)
5. [L2 说人话的智能体（30 分）](#5-l2-说人话的智能体)
6. [L3 Hybrid-QASM × RISC-V 混合编译（15 分）](#6-l3-混合编译)
7. [Bonus：自定义量子 RISC-V 扩展（+8 分）](#7-bonus-自定义量子-risc-v-扩展)
8. [工程与产品化叙事（10 分）](#8-工程与产品化叙事)
9. [如何复现：一条命令跑通](#9-如何复现)
10. [实现步骤回顾（逐步做了什么）](#10-实现步骤回顾)
11. [反作弊合规说明](#11-反作弊合规说明)

---

## 1. 我们做了什么

**为"不懂黑话的人"造一台会翻译的量子计算机入口。** 我们实现了：

- **L1**：一个真正抽象的量子"通用中间层"——把标准 OpenQASM 2.0 解析为统一
  中间表示（IR），再渲染成 **量旋 SpinQit / 本源 OriginIR / AWS Braket OQ3**
  三种原生方言，并在三家后端上执行、把结果归一化为大赛统一 Schema。
- **L2**：一个"说人话"的智能体 `agent_chat`——自然语言 → QASM → **用自己的
  L1 无噪声模拟器自验 → 不对就重试**；还能修代码、按官方《后端能力表》推荐
  平台。附带一个零基础友好的交互式 CLI（含可视化）。
- **L3**：一个真正的 Hybrid-QASM 编译器——解析 `classical {}` 经典控制块，
  生成可在官方 `riscv_emulator.py` 上运行、对**任意测量注入组合**都 100%
  正确的 RISC-V 汇编。
- **Bonus**：一套自定义量子 RISC-V 扩展指令集（编码规格 + fork 模拟器 +
  端到端测试三件套）。

## 2. 评分目标与达成情况

| 评分项 | 分值 | 本队伍状态 |
|---|---:|---|
| L1 语义等价（三平台 × 8 电路保真度） | 35 | ✅ 三平台统一适配；公开电路 6/6 通过，随机电路 90/90 保真度 ≥ 0.97 |
| L1 真机证据 | 10 | ⏳ 未申报（无平台账号；SDK 真机接入层已就绪，见 `docs/REAL_MACHINE.md`） |
| L2 客观评测（12 个私有变体） | 20 | ✅ `agent_chat` 已实现，LLM + 自验重试闭环，正式评测注入 `LOOMQ_LLM_*` 即启用 |
| L2 交互体验 | 10 | ✅ CLI 交互入口 + 3 个用户体验任务（见 `evidence/README.md`） |
| L3 混合编译 | 15 | ✅ 150 组随机程序 × 全部测量组合 0 失败 |
| 工程与产品化 | 10 | ✅ 零第三方依赖、一键可复现、架构文档完整（本文档 + `docs/ARCHITECTURE.md`） |
| Bonus 量子 RISC-V | +8 | ✅ 三件套齐备，端到端测试 9/9 |
| Bonus 新手引导与视觉叙事 | +4 | ✅ `docs/NEWBIE_GUIDE.md` + CLI 引导 + ASCII 可视化 |

## 3. 系统架构

```text
用户自然语言 ──► L2 agent_chat ──► 标准 OpenQASM 2.0
                                      │
                    ┌─────────────────┴──────────────────┐
                    │        L1 统一中间层（本队伍）        │
                    │  qasm/parser.py   OpenQASM 2.0 → IR │
                    │  qasm/simulator.py  无噪声态矢量模拟  │
                    │  transpiler/       IR → 三平台原生方言 │
                    │  backends/         执行 + Schema 归一化 │
                    └──────┬────────────┬──────────┬───────┘
                           │            │          │
                     spinq(SpinQit)  originq(OriginIR)  braket(OQ3)
                           │            │          │
                      Taurus 模拟器  pyqpanda CPUQVM  Braket LocalSimulator
                           └────────────┴──────────┴────────┘
                                    统一 JSON Schema 结果

Hybrid-QASM ──► L3 hybrid/compiler.py ──► (量子操作序列, RISC-V 汇编)
                                               │
                                        官方 riscv_emulator.py 执行
```

关键设计决策（评委审查点）：

1. **不是三套硬编码**：单一解析器 + 单一 IR，`transpiler/` 只是三个"渲染后端"。
   换平台不改逻辑，只改渲染器——这就是"通用"。
2. **零第三方依赖的可复现性**：核心（解析/模拟/转译/L2/L3）只用 Python
   标准库。评测容器**任何情况下都能构建成功**；若容器里恰好有官方 SDK
   （spinqit/pyqpanda/braket），`backends/runner.py` 会自动优先用真实 SDK 执行，
   没有则回退到我们自己的无噪声模拟器——两条路径语义一致、Schema 相同。
3. **SDK 位序坑的实证**：AWS Braket 返回 big-endian counts，pyqpanda 返回
   little-endian——`backends/runner.py` 用内部参考模拟器做 Hellinger 对齐校验，
   自动纠偏，把"跨平台位序归一化"做成了一道带安全网的工序。

## 4. L1 通用中间层

### 4.1 解析器 `qasm/parser.py`

- 严格实现大赛 12 门白名单子集：`h x s sdg t tdg rz ry cx cu1 swap ccx`。
- 支持 `measure q -> c;` 与 `measure q[i] -> c[j];`、`barrier`（忽略）、注释、
  `pi` 表达式参数（`pi/2`、`-0.5*pi`）。白名单外的门直接报错（隐藏电路不会出现）。

### 4.2 无噪声态矢量模拟器 `qasm/simulator.py`

- 纯 Python 状态矢量引擎，采样 count 遵循大赛 little-endian 位序约定。
- **交叉验证**：与 Qiskit `Statevector` 在 20 组随机 12 门电路上逐振幅一致
  （`≤1e-9`）；期间修复了一个 Toffoli 原地交换的经典 bug（双交换）。

### 4.3 三平台转译 `transpiler/emitters.py`

| 目标 | 输出 | 要点 |
|---|---|---|
| `spinq` | OpenQASM 2.0（规范化） | 白名单门直接通过，含寄存器声明与测量 |
| `originq` | OriginIR（`QINIT/CREG/门/MEASURE`） | 门名映射 `SDAG/TDAG/CU1/TOFFOLI`，参数双语法兼容 |
| `braket` | OpenQASM 3.0（免 include） | 仅用 Braket 解析器确认支持的门，其余**精确分解** |

**Braket 分解（全部经 AWS Braket LocalSimulator 与 Qiskit 实证）**：

- `cx` → `cnot`；`cu1(θ)` → `cphaseshift(θ)`（语义完全相等）
- `sdg` → `s s s`；`tdg` → `t t t t t t t`（精确，无近似）
- `ccx` → qelib1 Toffoli 恒等式（15 条指令，`tdg→t⁷`），与官方 `gate_identities.md` 一致

### 4.4 执行与统一 Schema `backends/runner.py`

```json
{
  "backend": "braket_local_simulator",
  "job_id": "loomq-braket-<sha1>",
  "shots": 8192,
  "counts": {"00": 4134, "11": 4058},
  "bit_order": "little",
  "timestamp": "2026-08-21T...Z",
  "meta": {"transpiled_gates": 2, "depth": 2, "engine": "sdk|internal", "native_ir": [...]}
}
```

- `meta.engine` 透明标注执行引擎；`meta.is_mock` 永远不存在（无 Mock 路径）。
- 本地验证：**30 组随机电路 × 3 平台 = 90 次运行全部 Hellinger ≥ 0.97**。

## 5. L2 说人话的智能体

### 5.1 交付形态

- 客观部分：`adapter.agent_chat(prompt) -> str`，读取 `LOOMQ_LLM_*` 环境变量，
  通过 OpenAI-compatible API 调用正式 DeepSeek 模型（`deepseek-v4-flash`）。
- 交互部分：`python3 cli.py`（交互式 CLI，含新手引导与结果可视化）。

### 5.2 任务分类与处理（`agent/core.py`）

三类任务自动分类：`generate` / `correct` / `backend`。

1. **意图生成**：LLM 生成 QASM → `agent/verifier.py` 用**我们自己的 L1 模拟器**
   自验（结构 + 目标态保真度，如 GHZ/Bell/QFT/Grover）→ 不通过则把错误反馈
   给 LLM 重试（最多 3 轮）。
2. **代码纠错**：从 prompt 中抽取损坏代码（`H q[0]; CX q[0] q[1]` 这类），
   LLM 修复后同样自验目标态。
3. **智能选后端**：LLM 先按官方《后端能力表》推理，`agent/backend_advisor.py`
   再对回复做**确定性校验**（约束解析 → 表过滤 → 规范标识核对），保证回复
   中一定出现正确规范 id（如 `braket_local_simulator`），无解时如实说明——
   这正是赛题文档推荐的 "function calling / RAG" 模式。

**离线演示模式**：未配置 `LOOMQ_LLM_*` 时（公开自测、无 Key 演示），
`agent/verifier.py` 会从 prompt 解析约束（比特数、目标态）**构造并自验**
电路——不是对公开样例的字符串匹配表，而是真正的约束驱动生成器。

**隐藏变体加固**（针对官方"改写措辞"的评测变体，均有单元测试）：
分类器按"修复意图 → 显式选平台 → 目标态意图"排序，`帮我跑一个 4 比特
GHZ 电路`不会被误判为选后端；后端约束支持中文数字比特数（"十五比特"）；
验证器目标态族覆盖 GHZ/Bell/QFT/Grover/均匀叠加/W/全 1/全 0，其中 W3
由白名单门精确制备（ry + cx + ccx 受控构造，数值验证三种单激发态各 1/3）。

### 5.3 CLI 用户体验（`cli.py`）

```
你 > 生成一个 3 比特 GHZ 态并进行全测量
（离线演示模式）已根据需求生成电路。
```qasm ...```

✅ 该电路已通过本地无噪声模拟器自验（保真度 ≥ 0.97）。

⚛️  正在三平台模拟运行（spinq / originq / braket）...
【braket_local_simulator】engine=sdk
总采样 8192 次
  |000⟩ ████████████████████████  4134 ( 50.5%)
  |111⟩ ████████████████████████  4058 ( 49.5%)
```

## 6. L3 混合编译

`hybrid/parser.py`（递归下降解析器）+ `hybrid/compiler.py`（RISC-V 代码生成）：

- 支持文法：顺序赋值、`if/else`（可嵌套）、`== !=`、`+ -`、括号、负数、
  寄存器 `r1..r9` 与测量位 `c[k]`（映射 `x10+k`）。
- 支持在文档文法之上的超集（括号嵌套、二元运算组合），解析更鲁棒。
- 输出只使用官方模拟器指令子集：`li add sub addi beq bne j`。
- 寄存器分配：`r1..r9 → x1..x9`；临时寄存器动态取"测量寄存器之上"的最高
  空闲寄存器，绝不与测量注入寄存器冲突。
- **验证**：150 组随机程序 × 全部测量组合与参考解释器逐一比对，**0 失败**。

## 7. Bonus 自定义量子 RISC-V 扩展

`quantum_riscv/`（详见 `quantum_riscv/encoding_spec.md`）：

- **① 编码规格**：32 位定长，custom-0 (0x0B) R 型 + custom-1 (0x2B) I 型，
  `qinit/h/x/z/s/sdg/cx/swap/ccx/meas/rz/ry` 共 12 条指令，12 位定点角度。
- **② 模拟器扩展**：`riscv_quantum_emulator.py` fork 官方 `riscv_emulator.py`
  （官方指令语义原样保留），新增量子指令 + 状态矢量引擎
  （与 L1 模拟器同一套门矩阵）。
- **③ 端到端测试**：`python3 quantum_riscv/run_e2e.py` → 9/9 PASS
  （编码往返、Bell/GHZ、经典-量子混编、参数门、官方指令集回归）。

## 8. 工程与产品化叙事

**必答题：你的工具让哪一类原本进不来的人，第一次能用上量子计算？**

> **让"会写 PPT 但没写过一行代码的跨界创作者"——比如做视觉艺术、教育内容、
> 科普写作的人——第一次真正"指挥"一台量子计算机。** 她们不需要知道
> OpenQASM 是什么：输入"生成一个 3 比特最大纠缠态"，CLI 就给出电路、
> 在三家平台跑出结果、画成直方图，并且每一条都经过本地模拟器自验后才交付。
> 题目问"你的工具让哪一类人第一次能进来"——我们选的是**最远的那个群体**：
> 不是"会 Python 但没学过量子"的人，而是"连 Python 都不需要"的人。

- **一键复现**：`docker build -t loomq-submission . && docker run --rm loomq-submission`
  或直接 `python3 evaluator.py --level all`。
- **架构清晰**：`docs/ARCHITECTURE.md`；模块单一职责、类型标注、中文注释。
- **质量保障**：43 个单元测试（`python3 tests/run_all.py`）+ 公开自测 6/6。

## 9. 如何复现

```bash
# 1. 公开契约自测（零依赖，任何 Python 3.9+ 环境）
cd starter_kit && python3 evaluator.py --level all

# 2. 全量单元测试（43 项）
python3 tests/run_all.py

# 3. 三平台跑通公开电路（含 fidelity 报告）
python3 evaluator.py --level l1 --target spinq,originq,braket --json-out report.json

# 4. L2 交互 CLI（无 Key 走离线演示；有 Key 配置 LOOMQ_LLM_* 后走模型）
python3 cli.py --guide

# 5. L3 随机压力测试（在 tests/test_l3.py 内，150 组 × 全组合）
python3 -m unittest tests.test_l3 -v

# 6. Bonus 端到端
python3 quantum_riscv/run_e2e.py

# 7. 容器基线
docker build -t loomq-submission . && docker run --rm loomq-submission
```

L2 使用自有 Key 调试：

```bash
export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
export LOOMQ_LLM_API_KEY=<YOUR_OWN_KEY>
export LOOMQ_LLM_MODEL=deepseek-v4-flash
export LOOMQ_LLM_TIMEOUT_SECONDS=120
python3 evaluator.py --level l2
```

## 10. 实现步骤回顾（逐步做了什么）

| 步骤 | 内容 | 产出 |
|---|---|---|
| 1 | 通读题面 `problem_statement.md`、`starter_kit/` 全部文档、提交流程图 | 评分表、提交契约、12 门白名单、IR 契约 |
| 2 | 安装参考 SDK 并**实证探测**：Braket 接受的 OQ3 门集、pyqpanda 的 OriginIR/QASM 行为、两家 SDK 的 counts 位序 | 转译器与归一化的关键依据 |
| 3 | 实现 QASM 2.0 解析器 + 无噪声态矢量模拟器，与 Qiskit 交叉验证 | `qasm/`（20/20 一致） |
| 4 | 实现三平台目标 IR 生成（含 Braket 精确分解） | `transpiler/`（90/90 保真度） |
| 5 | 实现统一执行层：SDK 优先 + 内置模拟器兜底 + 位序对齐安全网 | `backends/`（Schema 合规） |
| 6 | 实现 L2：任务分类、LLM 提示、自验重试循环、后端选型工具、离线构造器 | `agent/`（mock 服务器验证 LLM 路径） |
| 7 | 实现 L3：Hybrid-QASM 递归下降解析 + RISC-V 代码生成 | `hybrid/`（150 随机程序 0 失败） |
| 8 | 实现 Bonus：编码规格、fork 模拟器、端到端测试 | `quantum_riscv/`（9/9） |
| 9 | 实现交互 CLI 与可视化 | `cli.py` |
| 10 | 接入 `adapter.py` 契约、更新 `submission.yaml`、`requirements.txt` | 公开自测 6/6 |
| 11 | 编写 43 个单元测试、架构文档、新手引导、证据包 | `tests/` `docs/` `evidence/` |
| 12 | 运行 `prepare_submission.py` 预检并提交推送 | 本次提交 |

## 11. 反作弊合规说明

- 无 Mock 得分路径：`meta` 不含 `is_mock`；`run()` 全部为真实模拟
  （SDK 或自研无噪声模拟器）。
- L2 不是关键词匹配伪 Agent：正式评测注入 `LOOMQ_LLM_*` 时**每个 case 都会
  真实调用模型**；确定性校验仅作为 tool-use 验证层（赛题文档推荐做法）。
- L3 是真正的解析 + 编译，无打表；评测的随机用例由编译器的通用文法处理。
- 无硬编码 API Key/Token；错误信息不泄露密钥（`llm_client.py` 已保证）。
- 允许并鼓励 AI 辅助编程：本实现由 AI 辅助完成，各部分工作原理已在
  `docs/ARCHITECTURE.md` 与本文档说明，供异步审查。
