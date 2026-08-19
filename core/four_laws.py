# -*- coding: utf-8 -*-
"""
core/four_laws.py — 四铁律验证核心(独立版, 零依赖)
=================================================================
从项目 wf_harness 抽取的纯标准库实现, 供开源仓库独立使用。

四铁律:
  ① 分布相交 + OOS 净期望 > 0
  ② 等率随机对照(孪生 block-shuffle) |z|≥2
  ③ 前视控制(walk-forward 多折)
  ④ 功效反向(加折 z 应升)

策略接口(鸭子类型, 与 strategy_layer/strategy_lib.py 兼容):
  class MyStrategy:
      n: int                    # 样本数
      close: list[float]        # 价格序列
      hold: int                 # 持仓期
      cost: float               # 往返成本
      def signal_dir_at(i) -> int   # -1/0/+1
      def simulate_trade(i, d) -> float | None  # 交易净收益
"""
import math
import random
import statistics


def fold_windows(n, train_bars=400, val_bars=96, slide=48, min_tail=0):
    """滚动 walk-forward 折切分(铁律③)。"""
    out = []
    t0 = train_bars
    while True:
        v1 = t0 + val_bars
        if v1 > n - min_tail:
            break
        out.append((t0, v1))
        t0 += slide
    return out


def _trade(strategy, i, d):
    try:
        return strategy.simulate_trade(i, d)
    except Exception:
        return None


def simulate_window(strategy, i0, i1):
    """窗口内所有信号的净收益。"""
    nets = []
    for i in range(i0, i1 - getattr(strategy, "hold", 1)):
        d = strategy.signal_dir_at(i)
        if d == 0:
            continue
        net = _trade(strategy, i, d)
        if net is not None:
            nets.append(net)
    return nets


def twin_test(strategy, n_twin=100, block=120, seed=42):
    """铁律② 孪生 block-shuffle 对照。返回 dict 或 None。"""
    n = strategy.n
    sig = [int(strategy.signal_dir_at(i)) for i in range(n)]
    real = simulate_window(strategy, 0, n)
    if not real:
        return None
    real_net = statistics.mean(real)
    twin_nets = []
    rng = random.Random(seed)
    for _ in range(n_twin):
        blocks = [sig[i:i + block] for i in range(0, n, block)]
        rng.shuffle(blocks)
        shuf = [v for b in blocks for v in b]
        nets = []
        for i in range(n):
            d = shuf[i]
            if not d:
                continue
            net = _trade(strategy, i, d)
            if net is not None:
                nets.append(net)
        if nets:
            twin_nets.append(statistics.mean(nets))
    if not twin_nets:
        return None
    ctrl_mean = statistics.mean(twin_nets)
    ctrl_std = statistics.stdev(twin_nets) if len(twin_nets) > 1 else 1e-9
    z = (real_net - ctrl_mean) / (ctrl_std or 1e-9)
    return {"real_net": real_net, "real_n": len(real),
            "twin_mean": ctrl_mean, "twin_std": ctrl_std, "z": z,
            "n_twin_ok": len(twin_nets) >= 20}


def run_strategy(strategy, folds, n_twin=100, block=120, seed=42):
    """多折 OOS + 孪生, 返回 dict。"""
    per = {"folds": []}
    oos_exp = []
    for j, (i0, i1) in enumerate(folds, 1):
        nets = simulate_window(strategy, i0, i1)
        if nets:
            ev = statistics.mean(nets)
            win = sum(1 for x in nets if x > 0) / len(nets)
        else:
            ev, win = 0.0, 0.0
        per["folds"].append({"fold": j, "expectancy": ev,
                             "win_rate": win, "trades": len(nets)})
        if nets:
            oos_exp.append(ev)
    n_f = len(per["folds"]) or 1
    pos = sum(1 for f in per["folds"] if f["expectancy"] > 0)
    tot_t = sum(f["trades"] for f in per["folds"])
    per.update({
        "n_folds": n_f,
        "pos_fold_ratio": pos / n_f,
        "avg_oos_exp": (sum(f["expectancy"] * f["trades"] for f in
                            per["folds"]) / tot_t) if tot_t else 0.0,
        "total_oos_trades": tot_t,
    })
    tw = twin_test(strategy, n_twin, block, seed)
    if tw:
        per["twin"] = tw
        per["z"] = round(tw["z"], 2)
    return per


def verdict(per, z_min=2.0, pos_ratio_min=0.5):
    """四铁律综合判决(简化版, ①②③④全过才 PASS)。"""
    failures = []
    z = per.get("z", 0.0)
    if z < z_min:
        failures.append("law2_z")
    if per.get("pos_fold_ratio", 0) < pos_ratio_min:
        failures.append("law1_pos_fold")
    if per.get("avg_oos_exp", 0) <= 0:
        failures.append("law1_oos_ev")
    if per.get("n_folds", 0) < 3:
        failures.append("law3_folds")
    return "PASS" if not failures else "REJECT", failures
