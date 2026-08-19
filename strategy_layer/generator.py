# -*- coding: utf-8 -*-
"""
generator.py — 机制候选生成器（策略层改造 S3）
=================================================================
从机制模板库生成候选批次。机制模板 = 现有策略类(micro_strategies)
× 固定参数网格 × 随机扰动。约束：

1. 只从预定义机制族生成（6 类，见 budget_ledger.FAMILY_GROUPS）
2. 参数网格固定（禁止"看结果改参数"——生成层不读验证层输出）
3. 每批生成 B 个候选，先过 BudgetLedger 预算闸再投入验证

纯 stdlib + 已存在的 micro_strategies。零重写：直接 import 现有策略类。
"""
import os
import sys
import json
import random
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))

from budget_ledger import BudgetLedger, FAMILY_GROUPS  # noqa: E402

# 现有策略类 → 机制族映射(先挂已存在的, 后续可扩)
STRATEGY_REGISTRY = {
    "liquidation_reversal": {
        "family": "event",
        "class_path": "micro_strategies.LiquidationReversal",
        "params": [
            {"thr": 1.0, "hold": 4},
            {"thr": 1.5, "hold": 4},
            {"thr": 2.0, "hold": 8},
            {"thr": 1.0, "hold": 12},
        ],
    },
    "liquidation_continuation": {
        "family": "event",
        "class_path": "micro_strategies.LiquidationContinuation",
        "params": [
            {"thr": 1.0, "hold": 4},
            {"thr": 1.5, "hold": 4},
            {"thr": 2.0, "hold": 8},
        ],
    },
    "orderbook_imbalance": {
        "family": "state",
        "class_path": "micro_strategies.OrderbookImbalance",
        "params": [
            {"thr": 1.0, "hold": 4},
            {"thr": 1.5, "hold": 8},
        ],
    },
    "oi_price_divergence": {
        "family": "state",
        "class_path": "micro_strategies.OiPriceDivergence",
        "params": [
            {"thr": 1.0, "hold": 4},
            {"thr": 1.5, "hold": 8},
        ],
    },
}


class CandidateFactory:
    """生成候选批次。"""

    def __init__(self, ledger=None, registry=None, seed=42):
        self.ledger = ledger or BudgetLedger()
        self.registry = registry or STRATEGY_REGISTRY
        self.rng = random.Random(seed)
        self._classes = {}

    def _load_class(self, path):
        if path in self._classes:
            return self._classes[path]
        mod_name, cls_name = path.split(".")
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name)
        self._classes[path] = cls
        return cls

    def generate_batch(self, data, stage="explore", batch_size=5,
                       jitter=0.1):
        """生成一批候选。

        data     : 数据 dict（micro_strategies 的 load_micro 输出）
        stage    : 探索阶段（explore/verify/confirm/final）
        batch_size: 本批候选数
        jitter   : 参数随机扰动比例（固定网格 → 微扰，扩多样性）
        返回 [(family, name, strategy_instance, params), ...]
        """
        out = []
        # 打乱族顺序，避免同一族连续耗尽预算
        keys = list(self.registry.keys())
        self.rng.shuffle(keys)
        for name in keys:
            if len(out) >= batch_size:
                break
            spec = self.registry[name]
            family = spec["family"]
            ok, why = self.ledger.can_attempt(family, stage)
            if not ok:
                continue
            cls = self._load_class(spec["class_path"])
            params = self.rng.choice(spec["params"])
            # 微扰（可选）：jitter 比例内随机偏移 thr/hold
            p = dict(params)
            if jitter > 0 and "thr" in p:
                p["thr"] = round(p["thr"] * (1 + self.rng.uniform(
                    -jitter, jitter)), 3)
            try:
                inst = cls(data, **p)
            except Exception as e:
                self.ledger.record(family, stage, f"{name}({p})",
                                   data.get("_src", "?"),
                                   "REJECT", note=f"instantiate_err:{e}")
                continue
            out.append((family, name, inst, p))
        return out

    def family_coverage(self):
        """已覆盖的机制族（按 ledger 记账）。"""
        return {f for f, _ in self.ledger.spent.items()}


def main():
    """冒烟：无数据时只验证生成器结构（数据由验证流程注入）。"""
    print("候选工厂注册表:", list(STRATEGY_REGISTRY.keys()))
    print("族映射:")
    for name, spec in STRATEGY_REGISTRY.items():
        print(f"  {name} → {spec['family']} | 参数网格 {len(spec['params'])} 组")
    print("\n自检通过（生成需真实数据 dict，见 README 编排示例）")


if __name__ == "__main__":
    main()
