# Quant Validation Engine

**量化策略科学验证引擎** —— 一个拒绝了一切声称有 Alpha 的策略的框架。

> ⚠️ 这不是"AI 交易机器人"，也不是"自动赚钱工具"。
> 这是一个**验证引擎**：它把策略放在四道铁律下审判，输出 PASS / REJECT。
> 我们用它在 300+ 候选上只得到过 0 个 PASS——这就是它工作的方式。

## 为什么存在

大多数量化项目的死法不是"不会赚钱"，而是：

```
策略亏损 → 改参数 → 加Agent → 加过滤器 → 再回测 → 得到漂亮曲线 → 上实盘 → 亏钱
```

这个循环的每一环都在制造"看起来能赚钱"的假象。本引擎提供的是相反的路径：

```
提出假设 → 四铁律验证 → REJECT/PASS → 归档 → 换机制
```

## 四铁律（验证标准，永不降低）

1. **分布相交 + OOS 净期望 > 0**：信号分布与价格分布在样本外须可区分，且扣除成本后期望为正
2. **等率随机对照（孪生）**：block-shuffle 置换零检验，\|z\|≥2 才过；唯一差异 = 信号-价格时间对齐
3. **前视控制**：walk-forward 多折，而非单一固定切分
4. **功效反向**：加折 z 应升，反降回 50% = 无效应

## 快速开始

```bash
# 回归测试: 验证引擎自身正确(复跑已知 REJECT 族, 判决必须不变)
python strategy_layer/orchestrator.py --regression

# 探索一批候选(生成→预算→验证→记账)
python strategy_layer/run_explore.py --n 10 --n-twin 24

# 多周期扩展(回答"这个周期没信号是周期问题还是机制问题")
python strategy_layer/multi_tf_explore.py --n-twin 100
```

## 架构

```
生成层 strategy_layer/generator.py
  机制模板库(6类×30族) × 固定参数网格 × jitter → 候选批次

预算层 strategy_layer/budget_ledger.py
  Research Capital: 每机制族 ≤50 次尝试
  分层漏斗: explore 100 → verify 50 → confirm 10 → final 3
  Research Ledger: append-only 全量记账(不只成功者)

验证层 core/four_laws.py (四铁律, 零重写复用)
  ① OOS净期望 → ② 孪生z≥2 → ③ walk-forward → ④ 功效反向

放行闸 strategy_layer/blind_test.py
  Temporal Lock: 尾部锁定段, 调参不得触碰
  Blind Final Test: 锁定段跑一次, 结果一经读取即"开封"禁止重跑
```

## 第一个示例: 看一个策略如何被杀死

```python
# examples/rsi_reversal.py
# 一个经典的"看起来有效"的 RSI 反转策略
# 运行四铁律 → REJECT
# 你会看到: 为什么它过不了孪生对照(随机也会"赚")
```

**我们刻意用"失败策略"做第一个示例**——不是展示"赚钱曲线"，而是展示"验证引擎如何诚实地拒绝一个策略"。这建立了可信度：**框架不骗你**。

## 数据

- 自带 CSV 适配器(`adapters/csv.py`)
- Binance Vision 官方归档适配器(`adapters/binance_vision.py`)
- **不含任何私有密钥/交易账户信息**(见 SECURITY.md)

## 贡献

- 提交新机制模板(机制族 30 个只实现了部分)
- 提交新状态变量(风险实验的输入)
- 挑战框架本身: 如果你认为某道闸过松/过严, 欢迎 issue

## License

MIT

---

*本引擎由 Research Platform 项目产出。它拒绝过 300+ 候选、3 个风险状态假设、45 个多周期组合——0 个 PASS。这不是缺陷, 这是它的工作。*
作者的邮箱是wbb12258@qq.com
