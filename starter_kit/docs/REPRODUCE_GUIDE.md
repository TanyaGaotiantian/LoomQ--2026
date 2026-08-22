# 🐣 小白复现完全指南（手把手，照做就行）

> 这份指南假设你**完全没用过终端**。你只需要：① 跟着敲命令；
> ② 看输出长什么样；③ 对照"输出代表什么"来确认自己没走错。
> 全部命令都有 macOS / Windows 两个版本。**看到 $ 或 > 开头的是命令，
> 看到别的开头的是输出**（你不需要敲输出）。

- 配合阅读：[大白话学习笔记](LEARNING_JOURNEY.md) · [知识深讲](QUANTUM_DEEP_DIVE.md)

---

## 📚 目录

- [第 0 课 认识终端（Terminal）](#第-0-课-认识终端terminal)
- [第 1 课 确认电脑里有 Python](#第-1-课-确认电脑里有-python)
- [第 2 课 把代码拿到电脑上](#第-2-课-把代码拿到电脑上)
- [第 3 课 第一次运行：公开自测（6 项全过）](#第-3-课-第一次运行公开自测6-项全过)
- [第 4 课 跑全量单元测试（43 项）](#第-4-课-跑全量单元测试43-项)
- [第 5 课 跑 Bonus 端到端测试（9 项）](#第-5-课-跑-bonus-端到端测试9-项)
- [第 6 课 玩 L2 智能体 CLI（不用 API Key）](#第-6-课-玩-l2-智能体-cli不用-api-key)
- [第 7 课 亲手改代码做实验（最有趣的部分）](#第-7-课-亲手改代码做实验最有趣的部分)
- [第 8 课（可选）安装官方 SDK 体验"真实平台"](#第-8-课可选安装官方-sdk-体验真实平台)
- [第 9 课（可选）用自己的 API Key 让智能体真调模型](#第-9-课可选用自己的-api-key-让智能体真调模型)
- [第 10 课（可选）用 Docker 一键复现](#第-10-课可选用-docker-一键复现)
- [第 11 课（可选）把改动提交回 GitHub](#第-11-课可选把改动提交回-github)
- [❓ 常见问题（FAQ）](#常见问题faq)

---

## 第 0 课 认识终端（Terminal）

### 0.1 终端是什么

终端（Terminal / 命令行）是一个"用文字和电脑对话"的窗口。
平时我们用鼠标点图标，终端里则是**敲一行字、按回车、电脑执行**。
这个仓库的所有操作都在终端里完成。

### 0.2 怎么打开终端

**macOS（苹果电脑）**：

1. 按键盘 `Command + 空格`（打开搜索框，叫 Spotlight）。
2. 输入 `Terminal`（或中文"终端"）。
3. 回车，出现一个黑/白窗口，里面有类似 `你的电脑名:~ 用户名$` 的文字。
   **`$` 前面的部分叫"提示符"，`$` 之后才是你输入命令的地方。**

**Windows**：

1. 点开始菜单，搜索 `PowerShell`（推荐）或 `cmd`。
2. 回车，出现窗口，里面有 `C:\Users\你的用户名>`。
   **`>` 是提示符。**

### 0.3 三个最常用的命令（先热身）

| 命令 | 意思 | 例子输出（macOS） |
|---|---|---|
| `pwd` | Print Working Directory：我在哪个文件夹 | `/Users/小明` |
| `ls` | List：这个文件夹里有什么 | `Documents Downloads Desktop` |
| `cd 文件夹名` | Change Directory：进入某个文件夹 | （无输出 = 成功） |

```bash
pwd          # 看看自己在哪
ls           # 看看这里有什么
cd Desktop   # 进入桌面文件夹（如果存在）
pwd          # 再确认：现在应该在 .../Desktop
```

> 💡 提示：
> - `cd ..` = 回到上一层文件夹。
> - 按 **Tab 键**可以自动补全文件夹名（敲 `cd Des` 再按 Tab）。
> - 按 **↑ 方向键**可以调出上一条命令，不用重复敲。
> - 在终端里 **Ctrl+C** = 取消当前正在跑的程序（很常用）。

---

## 第 1 课 确认电脑里有 Python

在终端里输入（然后回车）：

```bash
python3 --version
```

**看输出**：

| 输出 | 代表什么 | 下一步 |
|---|---|---|
| `Python 3.9.x` 或 `3.10.x` 或 `3.11.x` 等 | ✅ 有 Python，版本够用 | 去第 2 课 |
| `command not found: python3`（macOS/Linux） | ❌ 没装或没找到 | 见下方"怎么装" |
| `'python3' 不是内部或外部命令`（Windows） | ❌ 没装或没找到 | 先试 `python --version`，还不行见下方 |

**Windows 用户先试**：

```bash
python --version
```

（Windows 上有时命令叫 `python` 而不是 `python3`，下面所有 `python3`
在 Windows 上都换成 `python` 或 `py`。）

**怎么装 Python（如果没装）**：

- macOS/Linux：去官网 https://www.python.org/downloads/ 下载安装包，
  一路"下一步"。装完**重新打开终端**再试。
- Windows：同上；安装时**务必勾选 "Add Python to PATH"**（把 Python
  加入系统路径，否则终端找不到它）。

---

## 第 2 课 把代码拿到电脑上

### 2.1 方法 A：用 Git 下载（推荐，之后可以更新）

先确认有没有 git：

```bash
git --version
```

- 有输出（如 `git version 2.39.0`）→ 继续。
- 没有 → macOS 装 Xcode Command Line Tools（终端输入 `xcode-select --install`）；
  Windows 装 https://git-scm.com/downloads。

然后克隆（下载）仓库：

```bash
cd ~/Desktop                 # 先到桌面（Windows 用 cd %USERPROFILE%\Desktop）
git clone https://github.com/TanyaGaotiantian/LoomQ--2026.git
cd LoomQ--2026               # 进入项目文件夹
pwd                          # 确认：应该显示 .../LoomQ--2026
ls                           # 应该能看到 README.md、starter_kit、tests 等
```

**输出代表什么**：`ls` 列出项目文件。`starter_kit` 是我们所有代码所在目录，
`README.md` 是项目说明，`tests/` 是比赛官方测试。

### 2.2 方法 B：不用 Git，网页下载压缩包

1. 浏览器打开 https://github.com/TanyaGaotiantian/LoomQ--2026
2. 绿色按钮 **Code ▾** → **Download ZIP**
3. 解压到桌面，会得到一个文件夹 `LoomQ--2026-main`
4. 终端进入它：
   ```bash
   cd ~/Desktop/LoomQ--2026-main
   pwd
   ```

> ⚠️ 方法 B 之后没法用 `git pull` 更新，但对"只跑一遍"完全够用。

---

## 第 3 课 第一次运行：公开自测（6 项全过）

这是最重要的一步：**证明代码能跑、而且跑得对**。

### 3.1 输入命令

```bash
python3 starter_kit/evaluator.py --level all
```

（从项目根目录 `LoomQ--2026` 运行。macOS 会弹出"允许网络"提示就点允许；
这一步其实不需要网络。）

### 3.2 期望输出（逐行解释）

```text
[PASS] l1:bell.qasm:spinq: fidelity threshold met
[PASS] l1:bell.qasm:originq: fidelity threshold met
[PASS] l1:ghz3.qasm:spinq: fidelity threshold met
[PASS] l1:ghz3.qasm:originq: fidelity threshold met
[PASS] l2:public-ghz: response contains parseable QASM
[PASS] l3:public-branch: public branch semantics passed
{"passed": 6, "failed": 0, "total": 6}
```

**每行代表什么**：

| 输出片段 | 含义 |
|---|---|
| `[PASS]` | 这项测试通过了（`[FAIL]` 就是没通过） |
| `l1:bell.qasm:spinq` | L1 级、电路是 bell、平台是量旋 spinq |
| `fidelity threshold met` | 保真度 ≥ 0.97（翻译正确） |
| `l2:public-ghz` | L2 智能体：让它生成 3 比特 GHZ 态 |
| `l3:public-branch` | L3 混合编译：if/else 分支语义正确 |
| `{"passed": 6, "failed": 0, "total": 6}` | 总结：6 过 0 挂 |

**看到 6 项 PASS = 成功！** 恭喜，你已经复现了这个项目的核心功能。

### 3.3 如果出现 [FAIL] 怎么办

- 先看报错最后一行，通常写着 `Error: ...` 或 `...error`。
- 90% 的情况是：当前目录不对（必须从项目根目录运行）或 Python 版本太旧。
- 把完整报错贴给 AI 或队友看。

### 3.4 顺便生成一份机器可读的报告（可选）

```bash
python3 starter_kit/evaluator.py --level all --json-out report.json
ls report.json     # 生成了报告文件
```

`report.json` 是给机器看的 JSON 格式结果，内容和我们刚才看到的一样。

---

## 第 4 课 跑全量单元测试（43 项）

单元测试 = 给每个小功能做的自动体检。运行：

```bash
python3 starter_kit/tests/run_all.py
```

**期望输出（最后几行）**：

```text
...
----------------------------------------------------------------------
Ran 43 tests in 0.9s

OK
```

**每行代表什么**：

- 前面一大串 `test_xxx ... ok` = 每个小测试逐个通过。
- `Ran 43 tests` = 一共跑了 43 个测试。
- `OK` = 全部通过（如果失败会显示 `FAILED (failures=...)`）。

如果显示 FAILED，告诉我你看到的报错，我们逐个解决。

---

## 第 5 课 跑 Bonus 端到端测试（9 项）

Bonus 是我们给迷你 CPU 加的"量子指令"。运行：

```bash
python3 starter_kit/quantum_riscv/run_e2e.py
```

**期望输出**：

```text
== 1. 编码规格：汇编/反汇编往返 ==
  [PASS] assemble/disassemble roundtrip
  [PASS] all words use custom opcodes 0x0B/0x2B
== 2. Bell 态 ==
  [PASS] Bell 态两测量结果恒相等
  ...
结果: 9 通过, 0 失败
```

**每行代表什么**：`9 通过, 0 失败` = 量子扩展指令全部工作正常。
第 2 节"Bell 态两测量结果恒相等"在验证量子力学的纠缠性质：
两枚"硬币"永远同面。

---

## 第 6 课 玩 L2 智能体 CLI（不用 API Key）

CLI = Command Line Interface，一个可以用大白话对话的程序。

### 6.1 启动（带新手引导）

```bash
python3 starter_kit/cli.py --guide
```

你会先看到一大段带 🧭 的引导文字（教你怎么玩），然后出现：

```text
提示：当前为离线演示模式。输入 help / exit。

你 >
```

`你 >` 后面就是输入框。**现在你可以打字回车跟它聊天了**。

### 6.2 依次试这三句话

**第 1 句**（生成电路）：

```text
你 > 生成一个 3 比特 GHZ 态并进行全测量
```

**期望输出**（节选）：

```text
（离线演示模式）已根据需求生成电路。

```qasm
OPENQASM 2.0;
...
measure q -> c;
```

✅ 该电路已通过本地无噪声模拟器自验（保真度 ≥ 0.97）。

⚛️  正在三平台模拟运行（spinq / originq / braket）...
【braket_local_simulator】engine=internal
总采样 8192 次
  |000⟩ ████████████████████████  4134 ( 50.5%)
  |111⟩ ████████████████████████  4058 ( 49.5%)
```

**输出代表什么**：
- ```` ```qasm ```` 代码块 = 它生成的量子电路（电脑的"菜谱"）。
- `✅ 自验通过` = 它用模拟器自己检查过，电路确实造出了 GHZ 态。
- 柱状图 = 跑 8192 次的结果：000 和 111 各约 50% —— 三枚"硬币"永远同面，
  这正是 3 比特 GHZ 态该有的样子。三家平台结果一致 = 翻译器没翻错。

**第 2 句**（纠错）：

```text
你 > 我想制备一个贝尔态，但这段代码报错了，帮我修好：H q[0]; CX q[0] q[1]
```

**期望**：输出修复后的完整电路（`h q[0]; cx q[0], q[1]; measure ...`），
并显示自验通过。

**第 3 句**（选后端）：

```text
你 > 我需要运行一个 15 比特电路，且零排队等待，选哪个平台？
```

**期望**：回复中包含 `spinq_taurus_simulator` 或 `originq_local_simulator`
或 `braket_local_simulator` 这类规范平台名（它们都满足"≥15 比特且不排队"）。

### 6.3 退出

```text
你 > exit
```

或直接按 `Ctrl+C`。

---

## 第 7 课 亲手改代码做实验（最有趣的部分）

> 目标：让你知道**代码在哪、怎么改、改完怎么看出效果**。
> 我们只改"教学用"的地方，绝不会改坏比赛功能（改坏了也能用 git 还原）。

### 7.1 用什么打开代码文件

- 推荐免费编辑器 **VS Code**（https://code.visualstudio.com/）。
  装好后在项目文件夹里右键 → "用 Code 打开"。
- 或者用系统自带：macOS 双击 `.py` 文件会用文本编辑打开；
  Windows 用记事本（右键 → 打开方式 → 记事本）。
- 我们主要会编辑两个文件：
  - `starter_kit/circuits/bell.qasm` —— 一个 2 比特 Bell 态电路（纯文本菜谱）
  - `starter_kit/examples/run_loomq_demo.py` —— 一个演示脚本

### 7.2 实验 1：看懂一个电路文件

用编辑器打开 `starter_kit/circuits/bell.qasm`，内容应该是：

```text
OPENQASM 2.0;           ← 第 1 行：声明版本（必须）
include "qelib1.inc";   ← 第 2 行：引入标准门库
qreg q[2];              ← 第 3 行：我要 2 个量子比特，起名叫 q
creg c[2];              ← 第 4 行：我要 2 个经典比特，起名叫 c
h q[0];                 ← 第 5 行：对 q[0] 做 H 门（造 50/50 叠加）
cx q[0], q[1];          ← 第 6 行：q[0] 是 1 就翻转 q[1]（制造纠缠）
measure q -> c;         ← 第 7 行：全部测量，结果存进 c
```

**现在动手改**：把第 5 行 `h q[0];` 改成 `h q[1];`（对另一个比特做 H），
保存（Cmd+S / Ctrl+S）。

**跑它**：

```bash
python3 starter_kit/examples/run_loomq_demo.py
```

看输出里的 counts——还是 00/11 各约 50%？对，因为 Bell 态对哪个比特做
H 是对称的。**这本身就是知识点**：纠缠不挑比特。

再把第 6 行 `cx q[0], q[1];` 删掉（或注释掉，前面加 `//`），保存再跑：

```bash
python3 starter_kit/examples/run_loomq_demo.py
```

**看变化**：这次只剩 H 了，没有纠缠 → 你会看到 **00、01、10、11 四个结果
各约 25%**（只有 q[1] 在 50/50，q[0] 恒为 0）。这就直观地证明了：
**没有 CX 就没有纠缠**。

改完记得恢复原样（或者用 git 还原：`git checkout starter_kit/circuits/bell.qasm`）。

### 7.3 实验 2：新建自己的电路文件

在 `starter_kit/circuits/` 里新建一个文件 `my_first.qasm`，内容：

```text
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
h q[1];
measure q -> c;
```

这就是"两个独立的 50/50 硬币"（无纠缠）。跑它：

```bash
python3 -c "
import sys; sys.path.insert(0, 'starter_kit')
from starter_kit import adapter
r = adapter.run(open('starter_kit/circuits/my_first.qasm').read(), 'braket', 8192)
print(r['counts'])
"
```

（这段是"临时小脚本"：读你的文件 → 用 braket 后端跑 → 打印 counts。）
**期望**：四个结果各约 2048 次。因为两个比特各自 50/50，互不相干。

### 7.4 实验 3：看"一种电路 → 三种方言"

运行演示脚本（它内部调用了 `adapter.transpile`）：

```bash
python3 starter_kit/examples/run_loomq_demo.py
```

看开头部分——同一个 Bell 电路被打印成三种样子：

- `--- spinq ---` 后面是 OpenQASM 2.0（几乎原样）
- `--- originq ---` 后面是 `QINIT 2 / CREG 2 / H q[0] / CNOT ...`（本源方言）
- `--- braket ---` 后面是 `OPENQASM 3.0; qubit[2] q; ... cnot ...`（AWS 方言）

**这就是"翻译器"的成品**。想单独看某一种，可以临时改 `run_loomq_demo.py`
第 28 行附近的循环，比如把 `("spinq", "originq", "braket")` 改成
`("originq",)`（只留本源），保存再跑。

### 7.5 实验 4：改采样次数 shots，看统计涨落

打开 `starter_kit/examples/run_loomq_demo.py`，找到
`adapter.run(bell, target, 8192)` 这一行，把 `8192` 改成 `100`，保存再跑。

**看变化**：次数变少后，50% 的概率会晃得更厉害（比如 46% / 54%）。
再改成 `20000` 跑一次——会更接近 50/50。这演示了**大数定律**：
测的次数越多，频率越接近真实概率。改完恢复 8192。

### 7.6 实验 5：改 CLI 的新手引导文案

打开 `starter_kit/cli.py`，找到 `GUIDE = """..."""` 那一大段文字，
随便改一句（比如把"硬币"改成"骰子"），保存，再运行：

```bash
python3 starter_kit/cli.py --guide
```

你会看到引导文字变了。这告诉你：**界面上所有的字都是代码里的字符串**，
想改文案就改这里。

### 7.7 实验 6：看模拟器的门矩阵（代码里的数学）

打开 `starter_kit/qasm/simulator.py`，找到 `_gate_matrix` 函数。
你会看到每个门对应的矩阵（和《知识深讲》第 3 章的表格一模一样）：

```python
if name == "h":
    return [[1 / SQRT2, 1 / SQRT2],
            [1 / SQRT2, -1 / SQRT2]]
```

想验证 H 门确实把 |0⟩ 变成 50/50？临时在终端跑：

```bash
python3 -c "
import sys, math; sys.path.insert(0, 'starter_kit')
H = [[1/math.sqrt(2), 1/math.sqrt(2)], [1/math.sqrt(2), -1/math.sqrt(2)]]
v = [1, 0]   # |0⟩
w = [H[0][0]*v[0]+H[0][1]*v[1], H[1][0]*v[0]+H[1][1]*v[1]]
print('H|0⟩ =', w)
print('概率:', abs(w[0])**2, abs(w[1])**2)   # 应该各 0.5
"
```

**期望**：`H|0⟩ = [0.7071067811865476, 0.7071067811865476]`，
`概率: 0.5 0.5`。你刚刚亲手验证了量子力学里最经典的公式！

### 7.8 实验 7：改 L3 的输入程序

打开 `starter_kit/examples/run_loomq_demo.py` 末尾的 `hybrid` 变量，
把 `if (c[0] == 1) { r1 = 100; } else { r1 = 10; }` 改成
`if (c[0] == 1) { r1 = 7; } else { r1 = 3; }`，保存再跑。

看输出的 RISC-V 汇编——数字跟着变了（`li x1, 100` 变成 `li x1, 7`）。
这说明：**改程序 → 编译器生成不同汇编**，编译是"真编译"，不是写死的。

---

## 第 8 课（可选）安装官方 SDK 体验"真实平台"

默认我们用自己的模拟器跑（结果和真实无噪声模拟一致）。如果你想体验
"让官方 SDK 真跑"，可以装两个纯 Python 的 SDK：

```bash
python3 -m venv venv                       # 建虚拟环境（隔离小房间）
./venv/bin/pip install amazon-braket-sdk pyqpanda
```

然后**用虚拟环境里的 Python** 再跑一次自测：

```bash
./venv/bin/python starter_kit/evaluator.py --level l1 --target spinq,originq,braket
```

**看输出变化**：还是 6 项 PASS，但如果你打开 JSON 报告
（`--json-out r.json` 后查看 `meta.engine` 字段），会发现
originq 和 braket 的 `engine` 从 `internal` 变成了 `sdk`——
说明这次是官方 SDK 在跑，而不是我们的模拟器。**结果一致 = 两条路都正确**。

（量旋的 spinqit 只支持 Python 3.10，如果你恰好是 3.10 可以
`pip install spinqit`；不是的话程序自动用内置模拟器，不影响结果。）

---

## 第 9 课（可选）用自己的 API Key 让智能体真调模型

没有 Key 时智能体走"离线演示模式"（自研生成+自验）。想让它真调大模型：

1. 去 https://platform.deepseek.com 注册并充值（很便宜），拿到 API Key。
2. 在终端设置环境变量（每次新开终端都要重新设）：

   ```bash
   export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
   export LOOMQ_LLM_API_KEY=sk-你的真实Key
   export LOOMQ_LLM_MODEL=deepseek-v4-flash
   export LOOMQ_LLM_TIMEOUT_SECONDS=120
   ```

3. 再跑 CLI，注意提示变成了"LLM 在线"模式：

   ```bash
   python3 starter_kit/cli.py "生成一个 5 比特 GHZ 态并进行全测量"
   ```

**输出代表什么**：回复里 ```` ```qasm ```` 代码块是模型生成的电路，
然后我们的模拟器会**再验证一遍**（自验），保真度合格才标注 ✅。

> 🔐 安全提醒：API Key 只在自己的电脑上用，**不要**写进任何代码文件、
> 不要提交到 GitHub。比赛正式评测会由组委会注入 Key，我们代码里
> 只读环境变量，所以很安全。

---

## 第 10 课（可选）用 Docker 一键复现

如果电脑装了 Docker（https://www.docker.com/），可以体验"把环境打包"：

```bash
docker build -t loomq-submission starter_kit/
docker run --rm loomq-submission
```

**输出代表什么**：容器内自动运行 `evaluator.py`，你会看到和
第 3 课一模一样的 6 项 PASS——这就是"评委在干净环境里跑"的效果。

---

## 第 11 课（可选）把改动提交回 GitHub

如果你改出了新东西想保存（前提是你用的是 `git clone` 的方式）：

```bash
git status                     # 看看改了哪些文件
git add 文件名                 # 把某个文件放进"待提交区"
git commit -m "我的修改说明"    # 拍一张快照
git push origin main           # 传到 GitHub（需要你的账号权限）
```

**输出代表什么**：`git status` 列出"红色 = 改过没提交，绿色 = 已暂存"。
`git push` 成功会显示 `main -> main`。

> 想看历史：`git log --oneline`（每行一次提交）。
> 想撤销：`git checkout -- 文件名`（把某个文件还原成上次提交的样子）。

---

## 常见问题（FAQ）

**Q1：运行时报 `ModuleNotFoundError: No module named 'qasm'`？**
A：目录不对。必须在项目根目录 `LoomQ--2026` 下运行（先 `pwd` 确认）。
不要在 `starter_kit` 里面运行 `python3 evaluator.py`（那样也能跑，
但用 `python3 starter_kit/evaluator.py` 更稳）。

**Q2：`python3` 找不到？**
A：见第 1 课。Windows 试试 `python` 或 `py`。

**Q3：跑得很慢？**
A：`--shots 8192` 对每平台每电路采样 8192 次，几秒钟是正常的。
想快一点可以加 `--shots 1024`（但保真度波动会大一些）。

**Q4：输出有 `[FAIL]`？**
A：先看 FAIL 那行后面的原因文字。常见原因：Python 版本过旧、
目录不对、文件被改坏（用 `git checkout -- 文件` 还原）。

**Q5：CLI 里输入中文没反应？**
A：先确认光标在 `你 > ` 后面；输入完按回车。如果卡住按 Ctrl+C 退出重开。

**Q6：没有网络能跑吗？**
A：能。公开自测、单元测试、CLI 离线模式都不需要网络。
只有第 9 课（调模型）和第一次装 SDK 需要网络。

**Q7：这些测试是"正式成绩"吗？**
A：不是。`evaluator.py` 是官方给的**公开自测**（只测 2 个公开电路）。
正式评分用组织方自己的评测器 + 隐藏电路。我们的自测全过只说明
"契约层面正确"，隐藏电路的正确性由实现质量保证（我们另外做了
30 电路 × 3 平台的验证矩阵，见 `docs/ARCHITECTURE.md`）。

**Q8：我想看每个模块都干了什么？**
A：读 `starter_kit/docs/ARCHITECTURE.md`（模块表 + 数据流图），
或直接看 `starter_kit/README.md` 的目录。

**Q9：改坏了怎么办？**
A：`git checkout -- 文件名` 还原单个文件；`git stash` 可以暂时收起改动。
什么都不懂就先 `git clone` 一份新的到别处。

---

> 到这里你已经完整跑通并亲手改过了这个项目。剩下的就是好奇心了：
> 试试让 CLI 生成 QFT、Grover、或者让你自己写的电路在三个平台跑起来。
> 玩得开心！🎉
