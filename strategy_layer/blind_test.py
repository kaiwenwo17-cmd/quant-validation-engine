# -*- coding: utf-8 -*-
"""
blind_test.py — Temporal Lock + Blind Final Test（策略层改造 S2，吸收 GPT Q8）
=================================================================
两道硬闸，防止"看结果再微调"污染最终判决：

1. **Temporal Lock（时间锁）**：训练/调参段与最终验证段完全分离——
   lock_start 之后的时间窗口，任何调参/探索过程不得触碰。
   只有"最终确认"阶段允许在锁内跑一次（blind run）。

2. **Blind Final Test（隐藏卷）**：最终确认跑在 locked 窗口上，
   调用方在跑之前不知道结果（"考试隐藏卷"）——一旦打开结果，
   本次 final 尝试即"开封"，不允许再改任何参数重跑。

纯 stdlib。与 wf_harness 的 fold_windows 解耦（本模块负责"锁"的
划分与守卫，fold_windows 的调用由策略层编排者负责）。
"""
import os
import json
import time
import datetime

DEFAULT_LOCK_FRAC = 0.15     # 尾部 15% 作为锁定验证段


class TemporalLock:
    """时间锁: 划分 训练段 / 调参段 / 锁定段。"""

    def __init__(self, n, lock_frac=DEFAULT_LOCK_FRAC, min_lock=200):
        """
        n        : 样本总数
        lock_frac: 尾部锁定比例
        min_lock : 锁定段最小样本数(防锁太短)
        """
        self.n = n
        lock_len = max(int(n * lock_frac), min_lock)
        lock_len = min(lock_len, n // 3)     # 锁最多占 1/3
        self.lock_start = n - lock_len
        self.lock_end = n
        self.train_end = self.lock_start

    def is_locked(self, i):
        return self.lock_start <= i < self.lock_end

    def locked_span(self):
        return (self.lock_start, self.lock_end)

    def unlocked_span(self):
        return (0, self.lock_start)

    def split(self):
        """→ (train_span, lock_span): (0, lock_start), (lock_start, n)"""
        return (0, self.lock_start), (self.lock_start, self.n)


class BlindTest:
    """盲测: 在锁定段跑最终确认, 结果一经读取即"开封"。"""

    def __init__(self, lock, result_store=None):
        self.lock = lock
        self.opened = False
        self.run_count = 0
        self._result_store = result_store or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "research", "blind_test_results.jsonl")

    def final_span(self):
        """最终确认可用的窗口(锁定段)。"""
        return self.lock.locked_span()

    def run(self, runner, strategy_factory, *args, **kwargs):
        """在锁定段跑一次最终确认。

        runner           : callable, 接收 (strategy, i0, i1) 返回判决 dict
        strategy_factory : callable, 返回策略实例(锁定段跑时, 参数已冻结)
        返回判决 dict(未开封前调用方不得据此改参)。
        """
        if self.opened:
            raise RuntimeError(
                "Blind test already opened: 结果已读取, 禁止再改参重跑")
        if self.run_count >= 1:
            raise RuntimeError("Blind final test 只允许跑一次")
        i0, i1 = self.lock.locked_span()
        strat = strategy_factory()
        verdict = runner(strat, i0, i1, *args, **kwargs)
        self.run_count += 1
        rec = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "span": [i0, i1],
            "verdict": verdict.get("verdict", "?"),
            "z": verdict.get("z"),
            "note": "blind final test (locked window)",
        }
        try:
            os.makedirs(os.path.dirname(self._result_store), exist_ok=True)
            with open(self._result_store, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return verdict

    def open_result(self, verdict):
        """开封: 标记结果已读。之后任何"再跑一次看会不会好一点"都被禁止。"""
        self.opened = True
        return verdict


def main():
    """自检: 时间锁划分 + 盲测单次限制。"""
    lock = TemporalLock(1000, lock_frac=0.15, min_lock=100)
    train, locked = lock.split()
    print(f"n=1000 → 训练段 {train} | 锁定段 {locked}")
    assert lock.is_locked(900)
    assert not lock.is_locked(500)

    # 盲测: 跑一次 → 成功; 再跑 → 拒绝
    bt = BlindTest(lock)
    calls = {"n": 0}

    def runner(strat, i0, i1):
        calls["n"] += 1
        return {"verdict": "REJECT", "z": 0.1, "span": [i0, i1]}

    v = bt.run(runner, lambda: object())
    assert v["verdict"] == "REJECT"
    try:
        bt.run(runner, lambda: object())
        assert False, "第二次应被拒"
    except RuntimeError as e:
        print(f"盲测第二次拦截: {e}")

    # 开封后再跑 → 拒绝
    bt2 = BlindTest(lock)
    bt2.run(runner, lambda: object())
    bt2.open_result({})
    try:
        bt2.run(runner, lambda: object())
        assert False, "开封后应被拒"
    except RuntimeError as e:
        print(f"开封后拦截: {e}")

    print("自检通过")


if __name__ == "__main__":
    main()
