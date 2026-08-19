# -*- coding: utf-8 -*-
"""
strategy_lib.py — 机制族扩展策略类库（S5 冲 500 用）
=================================================================
新增机制族（挂 MicroBase 接口，零重写 wf_harness）：

trend 族（纯价格）:
  MomentumSignal      20 日动量 z 极端 → 顺势
  EmaCrossSignal       EMA20/EMA50 交叉 → 顺势
  BreakoutSignal       N 日通道突破 → 顺势
state 族（盘口/波动率）:
  SpreadStateSignal    spread z 极端 → 逆势(流动性差时反转)
  VolStateSignal       波动率 z 极端 → 低波做均值回归
event 族（OI/量）:
  OiSurgeSignal        OI 突变 z 极端 → 跟随(杠杆堆积方向)

全部实现 signal_dir_at(i) → -1/0/+1。依赖数据缺失时返回 0（无信号）。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))

import micro_strategies as MS  # noqa: E402


# ───────────────────── trend 族 ─────────────────────

class MomentumSignal(MS.MicroBase):
    """20 日动量 z 极端 → 顺势（动量延续）。"""

    LEGS = ("price",)

    def __init__(self, d, mom_n=20, **kw):
        super().__init__(d, name="momentum", **kw)
        self.mom_n = int(mom_n)
        self.mom = [None] * len(self.close)
        for i in range(self.mom_n, len(self.close)):
            c0 = self.close[i - self.mom_n]
            if c0 > 0:
                self.mom[i] = self.close[i] / c0 - 1.0
        self.z = MS._z_series(self.mom)

    def signal_dir_at(self, i):
        z = self.z[i] if i < len(self.z) else None
        if z is None or abs(z) < self.thr:
            return 0
        return 1 if z > 0 else -1


class EmaCrossSignal(MS.MicroBase):
    """EMA20/EMA50 交叉 → 顺势。快线上穿慢线 → 多。"""

    LEGS = ("price",)

    def __init__(self, d, fast=20, slow=50, **kw):
        super().__init__(d, name="ema_cross", **kw)
        f, s = int(fast), int(slow)
        closes = self.close
        def ema(n):
            k = 2.0 / (n + 1)
            out = [closes[0]] * len(closes)
            for i in range(1, len(closes)):
                out[i] = closes[i] * k + out[i - 1] * (1 - k)
            return out
        ef, es = ema(f), ema(s)
        self.cross = [None] * len(closes)
        for i in range(1, len(closes)):
            if es[i - 1] > 0 and es[i] > 0:
                prev = ef[i - 1] - es[i - 1]
                cur = ef[i] - es[i]
                if prev <= 0 < cur:
                    self.cross[i] = 1.0
                elif prev >= 0 > cur:
                    self.cross[i] = -1.0
                else:
                    self.cross[i] = 0.0
        self.z = MS._z_series([None if v == 0 else v for v in self.cross])

    def signal_dir_at(self, i):
        c = self.cross[i] if i < len(self.cross) else 0
        return int(c) if c else 0


class BreakoutSignal(MS.MicroBase):
    """N 日通道突破 → 顺势（突破上轨多/下轨空）。"""

    LEGS = ("price",)

    def __init__(self, d, chan_n=48, **kw):
        super().__init__(d, name="breakout", **kw)
        self.chan_n = int(chan_n)
        self.breakout = [None] * len(self.close)
        for i in range(self.chan_n, len(self.close)):
            win = self.close[i - self.chan_n:i]
            hi, lo = max(win), min(win)
            c = self.close[i]
            if c > hi:
                self.breakout[i] = 1.0
            elif c < lo:
                self.breakout[i] = -1.0
            else:
                self.breakout[i] = 0.0

    def signal_dir_at(self, i):
        b = self.breakout[i] if i < len(self.breakout) else 0
        return int(b) if b else 0


# ───────────────────── state 族 ─────────────────────

class SpreadStateSignal(MS.MicroBase):
    """盘口 spread z 极端 → 逆势（流动性差时做反转，高风险环境）。"""

    LEGS = ("spr",)

    def __init__(self, d, **kw):
        super().__init__(d, name="spread_state", **kw)
        # d 里可能没有 spr（ob csv 的 spr_p50_bps 需单独注入）
        self.spr = d.get("spr") if isinstance(d, dict) else None
        if not self.spr:
            self.spr = [None] * len(self.close)
        self.z = MS._z_series(self.spr)

    def signal_dir_at(self, i):
        z = self.z[i] if i < len(self.z) else None
        if z is None or abs(z) < self.thr:
            return 0
        # spread 极端高 = 流动性差 → 均值回归（逆势）
        return -1 if z > 0 else 1


class VolStateSignal(MS.MicroBase):
    """波动率 z 极端 → 低波做反转（波动率均值回归）。"""

    LEGS = ("price",)

    def __init__(self, d, vol_n=24, **kw):
        super().__init__(d, name="vol_state", **kw)
        self.vol_n = int(vol_n)
        self.vol = [None] * len(self.close)
        for i in range(self.vol_n, len(self.close)):
            rets = [abs(self.close[j] / self.close[j - 1] - 1)
                    for j in range(i - self.vol_n + 1, i + 1)
                    if self.close[j - 1] > 0]
            if rets:
                self.vol[i] = sum(rets) / len(rets)
        self.z = MS._z_series(self.vol)

    def signal_dir_at(self, i):
        z = self.z[i] if i < len(self.z) else None
        if z is None or abs(z) < self.thr:
            return 0
        return 1  # 高波动后倾向反转(简化: 波动率回归, 方向用下一根动量)


# ───────────────────── event 族 ─────────────────────

class OiSurgeSignal(MS.MicroBase):
    """OI 突变 z 极端 → 跟随（杠杆堆积方向：OI 暴增+价格涨 → 顺势）。"""

    LEGS = ("oi",)

    def __init__(self, d, **kw):
        super().__init__(d, name="oi_surge", **kw)
        self.oi = d.get("oi") if isinstance(d, dict) else None
        if not self.oi:
            self.oi = [None] * len(self.close)
        # OI 变化率
        self.oi_chg = [None] * len(self.close)
        for i in range(1, len(self.close)):
            a, b = self.oi[i - 1], self.oi[i]
            if a and b and a > 0:
                self.oi_chg[i] = b / a - 1.0
        self.z = MS._z_series(self.oi_chg)

    def signal_dir_at(self, i):
        z = self.z[i] if i < len(self.z) else None
        if z is None or abs(z) < self.thr:
            return 0
        # OI 突变 + 价格同向 → 顺势（杠杆堆积确认）
        mom = 0.0
        if i >= 5 and self.close[i - 5] > 0:
            mom = self.close[i] / self.close[i - 5] - 1.0
        if abs(mom) < 0.002:
            return 0
        return 1 if (z > 0) == (mom > 0) else -1


# ───────────────────── arbitrage 族 ─────────────────────

class BasisCarrySignal(MS.MicroBase):
    """基差(premiumIndex) z 极端 → 基差回归（高基差→做空, 低基差→做多）。
    基差 = mark - index, 永续 vs 现货价差, 有均值回归机制。"""

    LEGS = ("basis",)

    def __init__(self, d, **kw):
        super().__init__(d, name="basis_carry", **kw)
        self.basis = d.get("basis") if isinstance(d, dict) else None
        if not self.basis:
            self.basis = [None] * len(self.close)
        self.z = MS._z_series(self.basis)

    def signal_dir_at(self, i):
        z = self.z[i] if i < len(self.z) else None
        if z is None or abs(z) < self.thr:
            return 0
        return -1 if z > 0 else 1   # 高基差→回归做空; 低基差→回归做多


# ───────────────────── event 族（funding） ─────────────────────

class FundingExtremeSignal(MS.MicroBase):
    """funding 率 z 极端 → 反向（funding 极端=拥挤交易, 均值回归）。"""

    LEGS = ("funding",)

    def __init__(self, d, **kw):
        super().__init__(d, name="funding_extreme", **kw)
        self.funding = d.get("funding") if isinstance(d, dict) else None
        if not self.funding:
            self.funding = [None] * len(self.close)
        self.z = MS._z_series(self.funding)

    def signal_dir_at(self, i):
        z = self.z[i] if i < len(self.z) else None
        if z is None or abs(z) < self.thr:
            return 0
        return -1 if z > 0 else 1   # funding 极端正(多头拥挤)→做空


# ───────────────────── alt 族（volume） ─────────────────────

class VolumeSurgeSignal(MS.MicroBase):
    """成交量 z 极端 → 顺势（放量突破确认方向）。"""

    LEGS = ("volume",)

    def __init__(self, d, **kw):
        super().__init__(d, name="volume_surge", **kw)
        self.vol = d.get("volume") if isinstance(d, dict) else None
        if not self.vol:
            self.vol = [None] * len(self.close)
        self.z = MS._z_series(self.vol)

    def signal_dir_at(self, i):
        z = self.z[i] if i < len(self.z) else None
        if z is None or abs(z) < self.thr:
            return 0
        # 放量 + 价格方向 → 顺势
        mom = 0.0
        if i >= 5 and self.close[i - 5] > 0:
            mom = self.close[i] / self.close[i - 5] - 1.0
        if abs(mom) < 0.001:
            return 0
        return 1 if mom > 0 else -1


# 注册表（生成器 import 用）
REGISTRY = {
    "momentum": {"family": "trend", "class": MomentumSignal,
                 "params": [{"thr": 1.0, "hold": 12}, {"thr": 1.5, "hold": 24},
                            {"thr": 2.0, "hold": 48}, {"thr": 0.8, "hold": 6},
                            {"thr": 1.2, "hold": 24}]},
    "ema_cross": {"family": "trend", "class": EmaCrossSignal,
                  "params": [{"thr": 0.5, "hold": 12}, {"thr": 1.0, "hold": 24},
                             {"thr": 1.5, "hold": 48}]},
    "breakout": {"family": "trend", "class": BreakoutSignal,
                 "params": [{"thr": 1.0, "hold": 12}, {"thr": 1.5, "hold": 24},
                            {"thr": 2.0, "hold": 48}, {"thr": 1.0, "hold": 6}]},
    "spread_state": {"family": "state", "class": SpreadStateSignal,
                     "params": [{"thr": 1.0, "hold": 6}, {"thr": 1.5, "hold": 12},
                                {"thr": 2.0, "hold": 24}]},
    "vol_state": {"family": "state", "class": VolStateSignal,
                  "params": [{"thr": 1.0, "hold": 6}, {"thr": 1.5, "hold": 12},
                             {"thr": 2.0, "hold": 24}, {"thr": 0.8, "hold": 48}]},
    "oi_surge": {"family": "event", "class": OiSurgeSignal,
                 "params": [{"thr": 1.0, "hold": 6}, {"thr": 1.5, "hold": 12},
                            {"thr": 2.0, "hold": 24}]},
    "basis_carry": {"family": "arbitrage", "class": BasisCarrySignal,
                    "params": [{"thr": 1.0, "hold": 12}, {"thr": 1.5, "hold": 24},
                               {"thr": 2.0, "hold": 48}, {"thr": 0.8, "hold": 6}]},
    "funding_extreme": {"family": "event", "class": FundingExtremeSignal,
                        "params": [{"thr": 1.0, "hold": 12}, {"thr": 1.5, "hold": 24},
                                   {"thr": 2.0, "hold": 48}]},
    "volume_surge": {"family": "alt", "class": VolumeSurgeSignal,
                     "params": [{"thr": 1.0, "hold": 6}, {"thr": 1.5, "hold": 12},
                                {"thr": 2.0, "hold": 24}, {"thr": 0.8, "hold": 48}]},
}
