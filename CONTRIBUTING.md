# 贡献指南 (CONTRIBUTING)

首先，请确认你理解这个项目是什么：

> **这是一个验证引擎，不是策略工厂。** 它拒绝过 300+ 候选、3 个风险状态假设、45 个多周期组合——0 个 PASS。**这不是缺陷，这是它的工作。**

如果你期望"贡献一个策略然后看到漂亮曲线"——这个项目不是你的目的地。如果你期望"让一个声称有 Alpha 的东西接受审判，并诚实地接受判决"——欢迎。

---

## 一、可以贡献什么

| 贡献类型 | 说明 | 难度 |
|---|---|---|
| **新机制模板** | 机制族 30 个目前只实现了部分。提交新的策略类（挂在 `MicroBase` 接口上） | 中 |
| **新状态变量** | Risk Alpha 实验的输入（如 OI 变化、清算冲击、资金费率） | 低 |
| **验证协议改进** | 你认为某道闸过松/过严，提出可落地的协议修改 | 高 |
| **挑战框架本身** | 你认为四铁律有漏洞，开 issue 论证——**欢迎，这是最有价值的贡献** | 高 |
| **Bug 报告** | 复现步骤 + 期望行为 + 实际行为 | 低 |
| **文档改进** | README/CONTRIBUTING/SECURITY 的勘误与补充 | 极低 |

### 明确不接受

- ❌ "我有赚钱策略，帮我验证并上线" —— 我们只做验证，不做放行
- ❌ 调参美化回测曲线的 PR —— 那是本项目反对的死亡循环
- ❌ 引入第三方依赖（pandas/numpy/ta-lib）—— 本项目**纯 stdlib**
- ❌ 任何包含密钥、API token、交易账户信息的代码 —— 见 SECURITY.md

---

## 二、开发环境

```bash
# 要求: Python 3.10+（推荐 3.13），零第三方依赖
python --version

# 验证引擎自身正确（回归测试: 复跑已知 REJECT 族, 判决必须不变）
python strategy_layer/orchestrator.py --regression

# 跑通一个示例
python -m examples.rsi_reversal
```

**纯 stdlib 是硬约束**——引擎的全部核心代码只用标准库，这保证任何人 clone 下来就能跑，无需安装任何依赖。

---

## 三、提交新机制模板（最常见的贡献）

### 3.1 接口约定

新策略类必须挂在 `MicroBase` 基类上（见 `strategy_layer/strategy_lib.py`）：

```python
class MyStrategy(MS.MicroBase):
    """一句话说清机制假设（为什么这个信号可能有 edge）。"""

    LEGS = ("close",)          # 用到的数据腿: close/oi/funding/basis/volume
    FAMILY = "event"           # 机制族: event/state/trend/arbitrage/alt

    def __init__(self, d, **kw):
        super().__init__(d, name="my_strategy", **kw)
        # 预计算信号序列

    def signal_dir_at(self, i):
        """返回 +1 / -1 / 0（在时间点 i 的信号方向）。"""
        ...
```

### 3.2 提交前自检清单（硬性）

- [ ] `LEGS` 声明的数据腿有真实数据支撑（不是空壳）
- [ ] 策略类能实例化且产生**非零信号**（`sum(signal_dir_at(i) != 0) > 0`）
- [ ] `FAMILY` 属于已注册机制族（event/state/trend/arbitrage/alt）
- [ ] **无前视**：`signal_dir_at(i)` 只能用 `i` 及之前的信息（KLines 完整走完才可下单）
- [ ] **无成本幻觉**：策略在代码注释里写清预期换手率，8bps 往返成本下净期望仍为正才值得提
- [ ] 加入了 `strategy_lib.REGISTRY` 并带固定参数网格（禁止"看结果改参数"）

### 3.3 机制假设要写清楚

每个策略类必须回答三个问题：

1. **信息优势是什么？**（这个信号看到了别人看不到的什么）
2. **为什么公共数据+成本约束下它还没被套利掉？**（答不上来 = 大概率没有 edge）
3. **如果 REJECT，你学到的证伪教训是什么？**（提交到 research ledger）

**答不上第 2 题的贡献，大概率会被 REJECT——这是项目 300+ 候选的统计结论，不是偏见。**

---

## 四、提交流程

### 4.1 小改动（文档/状态变量）

```bash
git checkout -b feat/your-change
# 修改 + 本地自检
git add .
git commit -m "feat: 添加 XX 状态变量"
git push origin feat/your-change
```

### 4.2 新机制模板（完整流程）

```bash
git checkout -b feat/new-mechanism-family
# 1. 在 strategy_layer/strategy_lib.py 添加策略类
# 2. 注册进 REGISTRY（含固定参数网格）
# 3. 本地自检:
python -c "import sys; sys.path.insert(0,'strategy_layer'); from strategy_lib import REGISTRY; print(REGISTRY.keys())"
# 4. 跑回归测试(判决必须与既有结果一致):
python strategy_layer/orchestrator.py --regression
# 5. 提交 + 推送
git add .
git commit -m "feat: 新增 XX 机制族模板"
git push origin feat/new-mechanism-family
```

### 4.3 Pull Request 检查清单

- [ ] PR 描述：机制假设三问（信息优势/为何未被套利/证伪教训）
- [ ] 无敏感信息（用 `git diff --cached | grep -i "api_key\|secret\|testnet"` 自检）
- [ ] 回归测试通过（判决与既有结论一致）
- [ ] 无新增第三方依赖
- [ ] 单一职责：一个 PR 只做一件事

---

## 五、验证纪律（合入红线）

以下情况 **PR 会被拒绝**：

1. **试图降低四铁律门槛**（如"z≥1.5 就够了吧"）——四铁律永不降低
2. **绕过预算闸**（Research Capital / 分层漏斗）——预算耗尽后换机制，不是扩预算
3. **"看结果调参"**——参数网格在实验前固定，禁止事后微调
4. **没有机制假设的纯参数组合**——那是过拟合工厂，不是科学
5. **宣称"稳定盈利"但拒绝接受孪生对照**——等率随机对照是第 2 铁律，无豁免

**记住**：这个项目里 `REJECT` 是**正常输出**，`PASS_CANDIDATE` 是需要警惕的异常信号（历史上第一个 PASS_CANDIDATE 在 verify 阶段被证伪为假阳性 z=1.28）。提交一个"被干净地杀死"的策略，是值得记录的贡献。

---

## 六、Bug 报告模板

```markdown
**描述**: 一句话说明问题
**复现**: 具体命令 + 数据文件（如有）
**期望行为**: 应该发生什么
**实际行为**: 实际发生了什么（含错误输出）
**环境**: Python 版本 / OS
```

---

## 七、行为准则（简版）

- 讨论验证协议时，用证据和数字，不用"我感觉"和"大家都说"
- 挑战框架是被鼓励的，但请先读四铁律再挑战——**多数"挑战"其实是在问"能不能放水"**
- 对"0 PASS"结果，禁止用"说明框架有问题"这种话术——先跑一遍回归测试再说

---

## 八、维护者联系方式

- 通过 GitHub issue 交流（优先）
- 提交前请先开 issue 说明意图，避免重复劳动

---

*贡献的最高境界：不是"让框架通过你的策略"，而是"你的策略让框架变得更难被骗"。*
