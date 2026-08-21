# 真机接入说明（L1 真机 +10 分准备材料）

本队伍未申报 L1 真机证据（评测环境无平台账号），但真机接入层已全部就绪，
拿到账号后按以下步骤即可补齐证据。

## 1. 量旋 SpinQ Cloud（真机）

```python
# backends/runner.py 的 SDK 路径已按官方示例实现；真机只需把后端句柄
# 从 BasicSimulator 换成 SpinQ Cloud 真机后端（见 spinqit 官方文档），
# 并保留 task_id 作为可溯源 job_id。
```

## 2. 本源悟空（originq_wukong）

```python
# pyqpanda 已支持 QASM 导入 + CPUQVM；真机提交使用 OriginService
# (pyqpanda.OriginService) 申请任务，返回可溯源的 taskId。
```

## 3. AWS Braket 云端（braket_cloud）

```python
# 已实现 braket LocalSimulator 路径；云端只需把 LocalSimulator()
# 换成 AwsDevice("arn:aws:braket:...::device/qpu/...")，
# task.result() 的 task_metadata.id 即可溯源 job_id。
```

## 证据要求（对照 evidence/README.md）

每个平台需要：平台 job ID、运行时间（带时区）、shots、实际执行的 QASM
路径、平台返回的原始 result.json 路径、任务页截图。以上文件建议放入
`evidence/files/`。
