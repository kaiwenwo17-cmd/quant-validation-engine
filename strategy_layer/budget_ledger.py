# -*- coding: utf-8 -*-
"""
budget_ledger.py — Research Capital 会计 + Research Ledger 全量记账
=================================================================
策略层改造 S1（吸收 GPT Q8 建议）：

1. **Research Capital**：每个机制族有独立预算（默认 50 次尝试），
   防一族烧光全部预算。申请候选前必须检查余额，超预算拦截。
2. **分层预算**：总搜索按漏斗 100(探索) → 50(验证) → 10(确认) → 3(最终)，
   每阶段配额独立，从探索到最终逐步收窄。
3. **Research Ledger**：append-only JSONL，逐候选记录
   (编号/假设/数据/结果/是否调整)，不只留成功者 —— 多重检验透明审计链。

纯 stdlib，零第三方依赖。与 wf_harness 解耦（本模块只做会计，不跑策略）。
"""
import os
import json
import time
import datetime

# ── 默认预算参数 ──
FAMILY_CAP = 50              # 每机制族尝试上限
STAGE_BUDGETS = [            # 分层漏斗(阶段, 配额)
    ("explore", 100),        # 一级探索
    ("verify", 50),          # 二级验证
    ("confirm", 10),         # 三级确认
    ("final", 3),            # 最终
]

# 机制族分类(6 类 × 5 族, GPT Q6 模板)
FAMILY_GROUPS = {
    "arbitrage": ["funding_spread", "cross_exchange", "basis_carry",
                  "funding_futures", "perp_spot"],
    "event": ["liquidation_spike", "oi_surge", "funding_extreme",
              "vol_breakout", "macro_surprise"],
    "state": ["liquidity_state", "regime_switch", "volatility_state",
              "spread_state", "depth_state"],
    "trend": ["momentum", "breakout", "moving_avg_cross",
              "channel", "trend_strength"],
    "execution": ["maker_rebate", "spread_capture", "limit_vs_market",
                  "slippage_aware", "latency_arb"],
    "alt": ["order_flow", "whale_track", "stablecoin_flow",
            "gas_price", "social_sentiment"],
}

LEDGER_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data", "research", "research_ledger.jsonl")


class BudgetLedger:
    """Research Capital 会计。线程不安全，单进程使用。"""

    def __init__(self, family_cap=FAMILY_CAP, stage_budgets=None,
                 ledger_path=LEDGER_PATH):
        self.family_cap = family_cap
        self.stage_budgets = dict(stage_budgets or STAGE_BUDGETS)
        self.ledger_path = ledger_path
        self.spent = {}          # family -> 已用次数
        self.stage_spent = {}    # stage -> 已用次数
        self.entries = []        # 本次会话内存副本
        self._load_existing()

    # ── 持久化 ──
    def _load_existing(self):
        """启动时载入已有 ledger(跨会话续计预算)。"""
        if not os.path.exists(self.ledger_path):
            return
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    self.entries.append(e)
                    fam = e.get("family", "?")
                    self.spent[fam] = self.spent.get(fam, 0) + 1
                    st = e.get("stage", "?")
                    self.stage_spent[st] = self.stage_spent.get(st, 0) + 1
        except Exception:
            pass

    def _append(self, entry):
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        try:
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # 记账失败不阻断主流程(研究层纪律: 失败不致死)

    # ── 预算查询 ──
    def family_remaining(self, family):
        return max(0, self.family_cap - self.spent.get(family, 0))

    def stage_remaining(self, stage):
        cap = self.stage_budgets.get(stage, 0)
        return max(0, cap - self.stage_spent.get(stage, 0))

    def can_attempt(self, family, stage):
        """候选可否投入: 族预算 + 阶段预算双闸。"""
        if self.family_remaining(family) <= 0:
            return False, f"族预算耗尽(family={family}, cap={self.family_cap})"
        if self.stage_remaining(stage) <= 0:
            return False, f"阶段预算耗尽(stage={stage})"
        return True, "ok"

    # ── 记账 ──
    def record(self, family, stage, hypothesis, data_src, result,
               adjusted=False, note=""):
        """记录一次尝试(Research Ledger)。返回 entry_id。"""
        ok, why = self.can_attempt(family, stage)
        if not ok:
            return {"ok": False, "reason": why}
        eid = f"{int(time.time() * 1000):x}-{len(self.entries)}"
        entry = {
            "id": eid,
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "family": family,
            "stage": stage,
            "hypothesis": hypothesis,
            "data": data_src,
            "result": result,          # "REJECT" / "PASS_CANDIDATE" / "PASS_CONFIRMED"
            "z": None,
            "adjusted": adjusted,      # 是否基于前次结果调整过(应尽量避免)
            "note": note,
        }
        self.entries.append(entry)
        self.spent[family] = self.spent.get(family, 0) + 1
        self.stage_spent[stage] = self.stage_spent.get(stage, 0) + 1
        self._append(entry)
        return {"ok": True, "id": eid, "entry": entry}

    def record_with_z(self, family, stage, hypothesis, data_src, result,
                      z, adjusted=False, note=""):
        e = self.record(family, stage, hypothesis, data_src, result,
                        adjusted=adjusted, note=note)
        if e["ok"]:
            e["entry"]["z"] = z
            # 重写最后一行带 z(简化: 追加一个 update 标记)
            self._append({"update_of": e["id"], "z": z,
                          "family": family, "stage": stage,
                          "result": result})
        return e

    # ── 统计 ──
    def summary(self):
        return {
            "total": len(self.entries),
            "by_family": dict(self.spent),
            "by_stage": dict(self.stage_spent),
            "family_cap": self.family_cap,
            "stage_budgets": self.stage_budgets,
            "results": {r: sum(1 for e in self.entries
                               if e.get("result") == r)
                        for r in ("REJECT", "PASS_CANDIDATE",
                                  "PASS_CONFIRMED")},
        }

    def all_entries(self):
        return list(self.entries)


def main():
    """自检: 预算拦截 + 记账 + 持久化。"""
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "research_ledger_test.jsonl")
    if os.path.exists(tmp):
        os.remove(tmp)
    bl = BudgetLedger(family_cap=3, ledger_path=tmp)
    # 族预算耗尽测试
    for i in range(3):
        r = bl.record("event", "explore", f"H{i}: liq spike → reversal",
                      "gate_liq", "REJECT")
        assert r["ok"], f"第{i+1}次应成功"
    r = bl.record("event", "explore", "H4: 第4次应被拦", "gate_liq", "REJECT")
    assert not r["ok"] and "族预算耗尽" in r["reason"]
    # 阶段预算测试(独立路径, 避免读到上面 event 的记账)
    bl2 = BudgetLedger(family_cap=5, stage_budgets=[("explore", 2)],
                       ledger_path=tmp + "2")
    if os.path.exists(tmp + "2"):
        os.remove(tmp + "2")
    bl2 = BudgetLedger(family_cap=5, stage_budgets=[("explore", 2)],
                       ledger_path=tmp + "2")
    for i in range(2):
        assert bl2.record("trend", "explore", f"T{i}", "vision",
                          "REJECT")["ok"]
    r = bl2.record("trend", "explore", "T2 应被阶段拦", "vision", "REJECT")
    assert not r["ok"] and "阶段预算耗尽" in r["reason"]
    # 持久化: 新实例读到旧计数
    bl3 = BudgetLedger(family_cap=3, ledger_path=tmp)
    assert bl3.family_remaining("event") == 0
    s = bl3.summary()
    print("自检通过:", json.dumps(s, ensure_ascii=False))
    print(f"族列表: {list(FAMILY_GROUPS.keys())}")
    print(f"族预算: {FAMILY_CAP}/族 | 阶段漏斗: {STAGE_BUDGETS}")


if __name__ == "__main__":
    main()
