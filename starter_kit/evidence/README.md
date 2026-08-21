# LoomQ 人工评分证据

> 本队伍申报项：**L2 交互体验、工程与产品化、自定义量子 RISC-V Bonus、
> 新手引导与视觉叙事 Bonus**。L1 真机未申报（评测环境无平台账号，接入层已
> 就绪，见 `docs/REAL_MACHINE.md`）。

## 申报项目

- [ ] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L2 交互体验

```text
启动界面或 CLI 的命令：python3 starter_kit/cli.py --guide
测试入口或页面地址：无（CLI）
用于交互体验评测的 3 个用户任务：
1. 零基础首跑：输入 "生成一个 3 比特 GHZ 态并进行全测量"，应看到 ```qasm 电路、
   自验通过标记、以及三平台（spinq/originq/braket）的 ASCII 柱状图结果。
2. 错误恢复：输入 "我想制备一个贝尔态，但这段代码报错了，帮我修好：H q[0]; CX q[0] q[1]"，
   应得到修复后的完整电路并自验通过（保真度 ≥ 0.97）。
3. 智能选后端：输入 "我需要运行一个 15 比特电路，且零排队等待，选哪个平台？"，
   回复应包含规范后端标识（如 braket_local_simulator / spinq_taurus_simulator 等）。
截图或演示视频：无（工作人员可按上一条命令在评测环境直接运行最终代码）
```

## 工程与产品化

```text
干净环境中的构建和启动命令：
  零依赖：python3 starter_kit/evaluator.py --level all
  容器基线：docker build -t loomq-submission starter_kit/ && docker run --rm loomq-submission
  全量测试：python3 starter_kit/tests/run_all.py
  交互入口：python3 starter_kit/cli.py --guide
架构说明：starter_kit/docs/ARCHITECTURE.md（模块职责、数据流、设计决策、验证矩阵）；
  主 README：starter_kit/README.md
目标用户和使用场景：没有任何量子/编程背景的跨界创作者（视觉、教育、科普等），
  用自然语言让三家量子云平台执行并理解第一个量子实验。
完整使用流程：starter_kit/docs/NEWBIE_GUIDE.md + CLI 内建 guide 引导。
```

## 自定义量子 RISC-V Bonus

```text
指令编码规格：starter_kit/quantum_riscv/encoding_spec.md
模拟器扩展实现：starter_kit/quantum_riscv/riscv_quantum_emulator.py
             （fork 官方 riscv_emulator.py，官方指令语义原样保留）
端到端测试命令：python3 starter_kit/quantum_riscv/run_e2e.py   （9/9 PASS）
```

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行指南：starter_kit/docs/NEWBIE_GUIDE.md（§1 首次运行引导）
量子概念解释：starter_kit/docs/NEWBIE_GUIDE.md（§2 概念大白话表）
结果可视化：starter_kit/cli.py（ASCII 柱状图）+ NEWBIE_GUIDE §3
错误恢复或无障碍引导：NEWBIE_GUIDE §4（容错提示、help/guide 命令、自验失败透明化）
```

## 提交规则确认

- 全部材料已进入最终提交 commit（见仓库归档）。
- 归档体积远小于 100 MiB；无 API Key/Token/个人隐私。
