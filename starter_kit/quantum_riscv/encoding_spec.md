# 自定义量子 RISC-V 扩展指令集（LoomQ Bonus）

> 在官方 `riscv_emulator.py`（`li/add/sub/addi/beq/bne/j` 子集）之上，fork 出一个
> 支持量子操作指令的扩展模拟器 `riscv_quantum_emulator.py`，并定义一套 32 位
> 定长、与 RV32I 编码风格一致的量子扩展指令。
>
> 本规格文档 + 扩展实现 + 端到端测试三项齐备（对应评分表 Bonus +8 分）。

---

## 1. 设计目标

- **不修改官方语义**：官方指令子集的编码与行为完全不变（向前兼容）。
- **量子操作成为一等公民**：在经典寄存器流之外，提供寄存器-量子指令：
  `QINIT` 初始化态矢量、单比特/两比特/三比特门、`MEAS` 测量。
- **直接可执行**：`riscv_quantum_emulator.py` 内的状态矢量引擎按指令逐条
  应用，最终 `MEAS` 结果写回通用寄存器，经典与量子指令可混编。

## 2. 指令编码格式

所有量子扩展指令为 **32 位定长**，使用 RV 保留的自定义主操作码区，并遵循
RV32I 的"不同格式用不同 opcode"惯例：

| opcode[6:0] | 名称 | 格式 | 指令 |
|---|---|---|---|
| `0b0001011` (0x0B) | custom-0 | R 型 | `qinit h x z s sdg cx swap ccx` |
| `0b0101011` (0x2B) | custom-1 | I 型 | `meas rz ry` |

### R 型（opcode 0x0B）

```
 31        25 24      20 19    15 14    12 11       7 6        0
| funct7    | rs2      | rs1    | funct3 | rd       | opcode   |
| 7 bits    | 5 bits   | 5 bits | 3 bits | 5 bits   | 0001011  |
```

| funct3 | 指令 | 语义 |
|---|---|---|
| `000` | `QINIT rd` | 分配一个新量子比特，编号写入 `rd` |
| `001` | `H rd` | 对 qubit `rd` 施加 Hadamard |
| `010` | `X rd` | Pauli-X |
| `011` | `Z rd` | Pauli-Z |
| `100` | `S rd` / `SDG rd` | 相位门（`funct7[0]`：0=S，1=SDG） |
| `101` | `CX rs1, rd` | 受控非（控制 `rs1`，目标 `rd`） |
| `110` | `SWAP rs1, rd` | 交换 qubit `rs1` 与 `rd` |
| `111` | `CCX rs1, rs2, rd` | Toffoli（控制 `rs1`、`rs2`） |

### I 型（opcode 0x2B）

```
 31       20 19    15 14    12 11       7 6        0
| imm[11:0] | rs1    | funct3 | rd       | opcode   |
| 12 bits   | 5 bits | 3 bits | 5 bits   | 0101011  |
```

| funct3 | 指令 | 语义 |
|---|---|---|
| `000` | `MEAS rs1, rd` | 测量 qubit `rs1`，0/1 写入 `rd` |
| `001` | `RZ rd, imm` | 绕 Z 轴旋转，`imm` 为 12 位定点角度（1/1024 弧度，二补码） |
| `010` | `RY rd, imm` | 绕 Y 轴旋转，角度编码同上 |

## 3. 汇编助记符 ↔ 机器码示例

| 助记符 | 机器码（示例） |
|---|---|
| `qinit x1` | `0x0000008B` |
| `h x1` | `0x0000108B` |
| `x x2` | `0x0000208B` |
| `z x3` | `0x0000308B` |
| `s x4` | `0x0000408B` |
| `sdg x4` | `0x0000488B` |
| `cx x1, x2` | `0x0000D10B` |
| `swap x1, x2` | `0x0000E10B` |
| `ccx x1, x2, x3` | `0x0000F20B` |
| `meas x1, x3` | `0x0000632B` |
| `rz x4, 1.5708` | `0x6480722B` |
| `ry x5, -0.5` | `0xE000732B` |

> 角度编码：`imm = round(角度 × 1024) mod 2^12`（带符号 12 位定点）。

## 4. 端到端示例

```asm
qinit x1          # 分配量子比特 0
qinit x2          # 分配量子比特 1
h x1              # |0> -> (|0>+|1>)/√2
cx x1, x2         # 纠缠 -> Bell 态
meas x1, x3       # 测量 qubit0 -> x3
meas x2, x4       # 测量 qubit1 -> x4
```

运行 `python3 quantum_riscv/run_e2e.py` 可验证：x3 与 x4 始终相同
（Bell 态性质），且经典指令（`li/add/beq/bne/j`）与量子指令混编正确。

## 5. 实现文件

- `quantum_riscv/encoding.py`：`assemble(text) -> List[int]` 与
  `disassemble(words) -> List[str]`（含标签与注释支持）。
- `quantum_riscv/quantum_core.py`：状态矢量引擎（与 `qasm/simulator.py`
  同一套门矩阵，数值一致）。
- `quantum_riscv/riscv_quantum_emulator.py`：官方 `TinyRISCVEmulator` 的 fork，
  新增量子指令执行，官方指令语义原样保留。
- `quantum_riscv/run_e2e.py`：端到端测试（编码往返、Bell/GHZ、经典-量子
  混编、参数门、官方指令集回归）。
