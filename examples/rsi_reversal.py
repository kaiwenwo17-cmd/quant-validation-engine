# -*- coding: utf-8 -*-
"""
examples/rsi_reversal.py — 第一个示例: 看一个策略如何被杀死
=================================================================
这是一个经典的 RSI 反转策略(超卖买入), 看起来"有道理"。
运行四铁律 → REJECT。

为什么? 因为它过不了孪生对照: 在随机打乱的入场序列上,
"超卖反弹"的收益和真实入场几乎一样 —— 说明它的正收益来自
市场本身的波动, 不是来自 RSI 信号的信息。

运行: python -m examples.rsi_reversal
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import four_laws


class RsiReversal:
    """RSI(14) < 30 超卖 → 做多。教科书经典策略。"""

    def __init__(self, closes, hold=12, cost=0.0008):
        self.close = list(closes)
        self.n = len(self.close)
        self.hold = hold
        self.cost = cost
        self.rsi = self._compute_rsi(14)

    def _compute_rsi(self, period=14):
        n = self.n
        rsi = [None] * n
        if n <= period:
            return rsi
        gains, losses = [], []
        for i in range(1, n):
            ch = self.close[i] - self.close[i - 1]
            gains.append(max(ch, 0))
            losses.append(max(-ch, 0))
        for i in range(period, n):
            avg_g = sum(gains[i - period:i]) / period
            avg_l = sum(losses[i - period:i]) / period
            rs = avg_g / avg_l if avg_l > 0 else float("inf")
            rsi[i] = 100 - 100 / (1 + rs)
        return rsi

    def signal_dir_at(self, i):
        r = self.rsi[i] if i < self.n else None
        if r is None:
            return 0
        return 1 if r < 30 else 0   # 超卖 → 做多

    def simulate_trade(self, i, d):
        if d == 0 or i + self.hold >= self.n:
            return None
        return d * (self.close[i + self.hold] - self.close[i]) / \
            self.close[i] - self.cost


def main():
    # 合成数据(纯随机游走——真实市场比这更有结构, 但足够演示)
    import random
    rng = random.Random(42)
    px = [100.0]
    for _ in range(5000):
        px.append(px[-1] * (1 + rng.gauss(0, 0.001)))
    strat = RsiReversal(px, hold=12, cost=0.0008)

    print("═══ RSI 反转策略 · 四铁律审判 ═══")
    print(f"样本: {strat.n} 根 | 持仓: {strat.hold} | 成本: {strat.cost*100:.2f}% 往返")
    print(f"信号: 买入 {sum(1 for i in range(strat.n) if strat.signal_dir_at(i)!=0)} 次\n")

    folds = four_laws.fold_windows(strat.n, 400, 96, 48,
                                   min_tail=strat.hold)
    per = four_laws.run_strategy(strat, folds, n_twin=100)
    v, failures = four_laws.verdict(per)

    print(f"walk-forward 折数: {per['n_folds']} | "
          f"正折占比: {per['pos_fold_ratio']:.2f}")
    print(f"OOS 平均净期望: {per['avg_oos_exp']*100:+.3f}%/笔")
    print(f"孪生对照: 真实 {per['twin']['real_net']*100:+.3f}% "
          f"vs 随机 {per['twin']['twin_mean']*100:+.3f}% "
          f"→ z = {per['z']:.2f}")
    print(f"\n★ 判决: {v}")
    if failures:
        print(f"  失败闸门: {', '.join(failures)}")
    print("\n解读: RSI<30 确实捕捉到了'下跌后买入', 但孪生对照显示")
    print("随机入场在同样的市场里赚得一样多 —— 这不是 RSI 的 edge,")
    print("是市场波动本身。四铁律正确拒绝了它。")


if __name__ == "__main__":
    main()
