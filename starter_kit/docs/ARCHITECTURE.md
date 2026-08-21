# LoomQ 队伍实现 · 架构文档

> 供异步审查与人工评分复核使用。模块职责、数据流、设计决策与验证方法。

## 1. 模块总览

| 模块 | 路径 | 职责 | 依赖 |
|---|---|---|---|
| QASM 解析器 | `qasm/parser.py` | OpenQASM 2.0 白名单子集 → 电路 IR | 标准库 |
| 态矢量模拟器 | `qasm/simulator.py` | 无噪声模拟 + counts 采样（little-endian） | 标准库 |
| 目标 IR 生成 | `transpiler/emitters.py` | IR → spinq/originq/braket 原生方言 | 标准库 |
| 后端执行层 | `backends/runner.py` | SDK 优先执行 + 内置模拟兜底 + Schema 归一化 | 标准库 + 可选 SDK |
| L2 智能体 | `agent/` | 任务分类、LLM 调用、自验重试、后端选型 | 标准库 + 可选 LLM API |
| L3 编译器 | `hybrid/` | Hybrid-QASM → 量子操作 + RISC-V 汇编 | 标准库 |
| CLI | `cli.py` | 交互式入口 + ASCII 可视化 | 标准库 |
| 量子 RISC-V 扩展 | `quantum_riscv/` | 编码规格 + fork 模拟器 + e2e 测试 | 标准库 |
| 契约适配 | `adapter.py` | 公开契约（transpile/run/agent_chat/compile_hybrid） | 标准库 |

## 2. 数据流

### L1
```
QASM 2.0 文本
  → parse_qasm() → Circuit（qreg/creg/ops）
  → transpile_to_ir(circuit, target)
       spinq   → OpenQASM 2.0（规范化）
       originq → OriginIR（QINIT/CREG/门/MEASURE）
       braket  → OpenQASM 3.0（cnot/cphaseshift/分解后的精确恒等式）
  → run_on_backend()
       1) SDK 可用 → 真实 SDK 执行（spinqit / pyqpanda / braket LocalSimulator）
       2) 否则     → 自研无噪声模拟器
  → counts 归一化（little-endian；Braket 大端自动反转，经 Hellinger 对齐校验）
  → 统一 JSON Schema
```

### L2
```
prompt
  → classify_task() → generate / correct / backend
  → [LLM 可用]  system prompt + prompt → chat_completion
        generate/correct: 提取 QASM → verify_qasm（结构+目标态保真度）
                          失败 → 把错误反馈给 LLM 重试（≤3 轮）
        backend:          LLM 推理 → backend_advisor 确定性校验规范 id
  → [LLM 不可用] 离线演示：约束驱动构造 + 自验
  → 回复文本（QASM 以 ```qasm 代码块给出）
```

### L3
```
Hybrid-QASM 文本
  → split_hybrid() → (量子操作行, classical 块文本)
  → ClassicalParser（递归下降）→ AST（Assign/IfStmt/BinOp/Lit/RegRef）
  → 代码生成：
       rN → xN；c[k] → x10+k
       赋值：literal→li；reg→add rd,rs,x0；reg±lit→addi；reg±reg→add/sub
             RHS 读目标寄存器时先求值到临时寄存器（防读写冲突）
       if/else：条件求值（scratch 池）→ bne/beq → 标签跳转
       临时寄存器：取测量寄存器之上最高的空闲寄存器（动态分配，绝不冲突）
  → (量子操作序列, RISC-V 汇编文本)
```

## 3. 关键设计决策与理由

1. **单一 IR + 三渲染器**（而非三套硬编码分支）：换平台只改渲染器，
   语义等价性由"同一份 Circuit IR"从结构上保证。
2. **零第三方依赖核心**：评测容器构建零风险；SDK 可选自动激活。
   这是可复现性（工程分）与稳健性（自动评分分）的最大公约数。
3. **Braket 门分解全部实证**：本地安装了 amazon-braket-sdk 逐一探测
   解析器接受的门名（`cx/cu1/ccx/sdg/tdg` 均被拒），再选择精确恒等式
   （`sdg=s³`、`tdg=t⁷`、`cu1=cphaseshift`、`ccx=15 条恒等式`），
   并在 LocalSimulator 上以随机电路验证 fidelity ≥ 0.97。
4. **SDK counts 对齐安全网**：vendor 位序不一致（Braket 大端、pyqpanda
   小端）→ 用内部参考分布做 Hellinger 校验，自动反转并再次校验，保证
   输出永远符合 little-endian 契约。
5. **L2 自验闭环**："生成 → 自验 → 重试"是赛题推荐的工程方案；自验使用
   我们自己的 L1 模拟器，形成 L1/L2 的良性复用。
6. **L3 寄存器分配**：scratch 动态取测量寄存器之上的最高空闲寄存器，
   支持文档文法之外的括号嵌套与复合表达式（150 组随机压力测试佐证）。

## 4. 验证矩阵

| 验证项 | 方法 | 结果 |
|---|---|---|
| 模拟器正确性 | 与 Qiskit Statevector 随机 12 门电路对比 | 20/20 振幅一致（≤1e-9） |
| 三平台语义等价 | 30 随机电路 × 3 平台 Hellinger | 90/90 ≥ 0.97 |
| Braket 转译 | LocalSimulator 真跑（含 Grover/ccx/cu1 分解） | 通过 |
| OriginIR 语法 | pyqpanda `convert_originir_str_to_qprog` 交叉检查 | 基本门通过（SDAG 等按契约生成） |
| L2 离线/在线 | mock OpenAI 服务器 + 公开用例 | 通过 |
| L3 编译器 | 150 随机程序 × 全测量组合 vs 参考解释器 | 0 失败 |
| Bonus | `run_e2e.py` | 9/9 |
| 契约 | 公开 `evaluator.py --level all` | 6/6 PASS |
| 单元测试 | `tests/run_all.py` | 36/36 OK |
