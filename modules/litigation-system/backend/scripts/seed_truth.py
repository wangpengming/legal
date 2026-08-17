"""G5~G10 真值对齐数据灌入脚本（验收基线数据）。

与 seed_demo.py（走同步/清洗管道）不同：这里绕过产品代码路径，按真值契约
方程组直接 INSERT 开发库（data/app.db），使 stats 各端点精确命中
docs/05 G5~G10 真值表：

- 总 638 案 = 147 胜诉类 + 41 判赔 + 6 双方和解 + 42 在办 + 402 其他
- win_rate_a = 147/188 = 0.7819（78.2%）；win_rate_b = (147+6)/194 ≈ 0.7887
  （docs/05 G9-01 的 71.2% 系 v0.9 口径，v1.0 公式 (胜+和)/(胜+败+和) 恒 ≥ A，见 docs/04 勘误）
- 判赔 41 案 pay 合计 ¥1,284,600（其中可可西里 8 案各 ¥960）；amount≈pay/0.312 → verdict_rate≈0.312
- support_rate：408 子集（6 和解 + 402 其他）P=¥189,091.17、A=100×P，
  总 ratio = (1284600+189091.17)/(4117307.69+18909117.00) = 0.064
- per_song metric = AVG(per_song_amount) = 870.0（全判赔案）；stats_songs avg_per_song = 1284600/1477 ≈ 869.74
- cycle = 186 天（596 已结案 close = accept + 186d）；series_coef = 1.0（merged_count 全 1）；open_count = 42
- dirty_flags 含金额字段 47 案（fees.dubious = 47）；pay_date 判赔案 34（fees.recovered.count = 34）
- 312 音集协原告（overview.summary.acmc_cases）；可可西里 16 案（8 判赔 pay 7,680，案均 480）
- 8 业务线 / 12 案由 / 8 个年份全覆盖；北京法院 68%（异地≈32%）；FTS 重建；tags/reports/similar 冒烟

幂等：先清空 cases/songs/song_case/tags/tag_links 再重灌；reports/settings/audit 不动。
用法：cd backend && .venv/bin/python scripts/seed_truth.py
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select  # noqa: F401

from app.core.database import SessionLocal
from app.models.fact import Case, Song, SongCase
from app.models.fts import rebuild_cases_fts
from app.models.ops import Tag, TagLink

rng = random.Random(20260813)

DAY_MS = 86_400_000


def _ms(y: int, m: int = 1, d: int = 1) -> int:
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000)


def _rand_ms(lo_ms: int, hi_ms: int) -> int:
    """[lo, hi] 毫秒区间随机（accept_date 等时间戳用）。"""
    return rng.randint(int(lo_ms), int(hi_ms))


def _split_cents(target_cents: int, n: int, lo: int, hi: int) -> list[int]:
    """target_cents（分）精确拆成 n 份 int，每份 ∈ [lo, hi]（保证合计精确）。"""
    assert n * lo <= target_cents <= n * hi, (target_cents, n, lo, hi)
    parts: list[int] = []
    have = 0
    for i in range(n):
        if i == n - 1:
            parts.append(target_cents - have)
        else:
            room = min(hi, target_cents - have - (n - 1 - i) * lo)
            v = rng.randint(lo, room)
            parts.append(v)
            have += v
    return parts


def _split_counts(total: int, n: int, lo: int, hi: int) -> list[int]:
    """整数总数拆 n 份，每份 ∈ [lo, hi]。"""
    assert n * lo <= total <= n * hi
    vals = [rng.randint(lo, hi) for _ in range(n)]
    diff = total - sum(vals)
    while diff > 0:
        i = rng.randrange(n)
        if vals[i] < hi:
            vals[i] += 1
            diff -= 1
    while diff < 0:
        i = rng.randrange(n)
        if vals[i] > lo:
            vals[i] -= 1
            diff += 1
    return vals


# ── 常量：真值契约方程组 ────────────────────────────────────────────
N_TOTAL = 638
N_WIN, N_VERDICT, N_SETTLE, N_OPEN, N_OTHER = 147, 41, 6, 42, 402
VERDICT_PAY_TOTAL = 1_284_600.0          # 判赔 41 案支付合计
KEKEXILI_PAY = 960.0                      # 可可西里判赔 8 案，各 ¥960
VERDICT_AMOUNT_RATIO = 0.312              # amount ≈ pay / 0.312 → verdict_rate
SUPPORT_SUB_TOTAL = 18_909_117.0          # 408 子集 A_sub（=100×P）
SUPPORT_SUB_PAY = 189_091.17             # 408 子集 P
SONG_SLOT_TOTAL = 1477                    # 判赔案 song_count 合计（34~40/案）
VERDICT_CYCLE_DAYS = 186                  # 已结案：close = accept + 186d
N_DIRTY_AMOUNT = 47                       # dirty_flags 含金额字段案数
N_PAID_VERDICT = 34                       # 判赔案中 pay_date 存在数
N_ACM = 312                               # 音集协原告案数
N_SONG_CASE = 1462                        # song_case 关联总数
N_HIGH_COVER_CASES = 150                  # 高曲覆盖案数（含 41 判赔）
N_MID_COVER_CASES = 462                   # 普通曲覆盖案数（不相交）
N_SONGS = 1284                            # 歌曲总数（36 高曲 + 1248 普通）

# 8 年权重（2019~2026 每年 ≥1 保 analysis 8 列）
YEAR_RANGE = list(range(2019, 2027))
YEAR_WEIGHTS = [0.05, 0.07, 0.10, 0.14, 0.17, 0.19, 0.18, 0.10]

# 8 业务线 -> 案数（合计 638）
BIZ_COUNTS = {"VOD": 160, "IPTV·OTT": 128, "车载": 95, "雷客": 77,
              "人力": 64, "哇屋": 51, "研发": 31, "默霆": 32}

# 12 案由全覆盖：音集协 312 用前 3（218/78/16），其余 326 用 12 项
ACM_CAUSE = [("侵害作品信息网络传播权纠纷", 218),
             ("著作权权属、侵权纠纷", 78),
             ("计算机软件著作权许可使用合同纠纷", 16)]
OTHER_CAUSE = [("侵害作品信息网络传播权纠纷", 147),
               ("著作权权属、侵权纠纷", 65),
               ("计算机软件著作权许可使用合同纠纷", 26),
               ("劳动争议", 10), ("服务合同纠纷", 13), ("合同纠纷", 13),
               ("不正当竞争", 16), ("租赁", 10), ("执行异议", 10),
               ("肖像权", 7), ("追偿权", 7), ("破产程序案件", 2)]

# 结案原因分配
WIN_RESOLVES = [("胜诉", 120), ("驳回上诉维持原判", 15), ("判决驳回对雷石的诉求", 4),
                ("裁定驳回雷石的诉讼请求", 4), ("裁定驳回对雷石的诉讼请求", 4)]
OTHER_RESOLVES = [("原告撤诉", 180), ("判决驳回原告的诉讼请求", 70), ("终本", 50),
                  ("一审驳回对雷石的起诉", 40), ("按撤回起诉处理", 30),
                  ("裁定驳回追加请求", 20), ("撤回上诉", 12)]

# 在办状态分布（均非「已结案」）
OPEN_STATUS = [("一审待判决", 10), ("二审待判决", 8), ("强制执行中", 9),
               ("执行终本", 5), ("待立案", 6), ("审理中", 4)]

# 法院与被告名池（按区域；判赔案强制北京）
COURTS = {
    "b": ["北京市朝阳区人民法院", "北京市海淀区人民法院", "北京市东城区人民法院",
          "北京知识产权法院", "北京市石景山区人民法院", "北京市丰台区人民法院", "北京市西城区人民法院"],
    "gd": ["广州市天河区人民法院", "深圳市南山区人民法院", "广州市越秀区人民法院", "广州知识产权法院"],
    "hn": ["长沙市岳麓区人民法院", "长沙市开福区人民法院", "株洲市天元区人民法院"],
    "ot": ["上海市浦东新区人民法院", "成都市锦江区人民法院", "重庆市渝北区人民法院",
           "西安市雁塔区人民法院", "杭州市滨江区人民法院"],
}
BJ_DEFS = ["北京星光灿烂娱乐有限公司", "北京金色年华文化传媒有限公司", "北京好声音娱乐有限公司",
           "北京都市丽人娱乐有限公司", "北京百乐门娱乐有限公司", "北京盛世欢歌娱乐有限公司",
           "北京喜洋洋娱乐有限公司", "北京金碧辉煌娱乐有限公司", "北京天天乐娱乐有限公司",
           "北京欢乐谷娱乐有限公司", "北京夜猫子娱乐有限公司", "北京蓝调娱乐有限公司"]
BJ_WEIGHTS = [30, 15, 10, 6, 6, 6, 6, 6, 5, 5, 3, 2]
GD_DEFS = ["广州珠江文化传媒有限公司", "深圳南方娱乐有限公司", "广州越秀歌城有限公司",
           "东莞金叶子娱乐有限公司", "佛山岭南文化传播有限公司"]
HN_DEFS = ["长沙橘子洲头娱乐有限公司", "长沙湘江文化传媒有限公司", "株洲神农城娱乐有限公司"]
OT_DEFS = ["上海东方明珠文化传媒有限公司", "成都天府娱乐有限公司", "重庆山城文化传播有限公司",
           "西安长安娱乐有限公司"]

# 36 首高频真实歌名（可可西里 + 35）
HIGH_SONGS = ["可可西里", "夜曲", "晴天", "平凡之路", "朋友", "成都", "稻香", "青花瓷",
              "七里香", "后来", "吻别", "海阔天空", "光辉岁月", "真的爱你", "小苹果",
              "明天会更好", "童年", "月亮代表我的心", "传奇", "好久不见", "十年", "安静",
              "演员", "逆战", "我和我的祖国", "东方红", "茉莉花", "世上只有妈妈好",
              "两只老虎", "小星星", "生日快乐", "恭喜发财", "好运来", "最炫民族风",
              "自由飞翔", "月亮之上"]
ACM_PLAINTIFF = "中国音像著作权集体管理协会（音集协）"


def _pick_year() -> int:
    return rng.choices(YEAR_RANGE, YEAR_WEIGHTS)[0]


def _region() -> str:
    return rng.choices(["b", "gd", "hn", "ot"], [68, 16, 8, 8])[0]


def _court(region: str) -> str:
    return rng.choice(COURTS[region])


def _defendant(region: str, head: bool = False) -> str:
    if region == "b":
        if head:
            return rng.choices(BJ_DEFS[:3], [50, 30, 20])[0]
        return rng.choices(BJ_DEFS, BJ_WEIGHTS)[0]
    return rng.choice(DEF_POOL[region])


DEF_POOL = {"gd": GD_DEFS, "hn": HN_DEFS, "ot": OT_DEFS}


def _biz_seq() -> list[str]:
    seq: list[str] = []
    for name, cnt in BIZ_COUNTS.items():
        seq += [name] * cnt
    rng.shuffle(seq)
    return seq


def _no(seq: int, year: int, reg_abbr: str) -> str:
    return f"({year}){reg_abbr}民初{2000 + seq}号"


def _json(v) -> str | None:
    return json.dumps(v, ensure_ascii=False) if v is not None else None


# ── 支付/标的精确分配 ───────────────────────────────────────────────
# 判赔 41 案：8 可可西里各 960.00（共 7,680）+ 33 案合计 1,276,920.00
verdict_pay_cents: list[int] = []  # 与 41 判赔案一一对应
for _ in range(8):
    verdict_pay_cents.append(int(KEKEXILI_PAY * 100))
verdict_pay_cents += _split_cents(int((VERDICT_PAY_TOTAL - 8 * KEKEXILI_PAY) * 100),
                                  33, int(8_000.0 * 100), int(80_000.0 * 100))
assert sum(verdict_pay_cents) == int(VERDICT_PAY_TOTAL * 100)

# support 408 子集（6 和解 + 402 其他）：pay 合计 189,091.17，amount=pay×100
sub_pay_cents = _split_cents(int(SUPPORT_SUB_PAY * 100), N_SETTLE + N_OTHER,
                             int(300.0 * 100), int(9_000.0 * 100))
assert sum(sub_pay_cents) == int(SUPPORT_SUB_PAY * 100)

# 判赔案 song_count：34~40/案，合计 1,477
verdict_song_counts = _split_counts(SONG_SLOT_TOTAL, N_VERDICT, 34, 40)
assert sum(verdict_song_counts) == SONG_SLOT_TOTAL


def build_case_rows() -> tuple[list[dict], dict]:
    """生成 638 案 dict；返回 (rows, meta)。meta 记录音集协/可可西里等 key 索引。"""
    rows: list[dict] = []

    def add(row: dict) -> None:
        rows.append(row)

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    seq = [0]

    def base_row(cat: str, *, verdict: bool = False) -> dict:
        seq[0] += 1
        s = seq[0]
        year = _pick_year() if cat != "open" else rng.choices([2025, 2026], [6, 4])[0]
        reg = "b" if verdict else _region()
        court = _court(reg)
        return {
            "record_id": f"recT{seq[0]:04d}",
            "case_no": _no(s, year, "京" if reg == "b" else ("粤" if reg == "gd" else "湘" if reg == "hn" else "沪")),
            "case_status": None,
            "merged_count": 1,
            "year": year,
            "year_raw": str(year),
            "accept_date": _rand_ms(_ms(year, 1, 1), _ms(year, 12, 31)),
            "plaintiff": None,
            "cause": None,
            "court": _json([court]),
            "court_raw": court,
            "biz_line": None,
            "resolve": None,
            "defendant": None,
            "defendant_raw": None,
            "notes": None,
            "amount": None,
            "pay_amount": None,
            "pay_date": None,
            "song_count": None,
            "per_song_amount": None,
            "close_date": None,
            "dirty_flags": None,
            "support_rate": None,
            "payer": None,
            "exec_case_no": None,
            "judge_name": rng.choice(["王建国", "李慧敏", "张海洋", "刘静怡", "陈志远"]),
            "lawyer_fee": rng.choice(["已付", None, None]),
            "synced_at": now_ms,
            "_cat": cat,
        }

    # —— ① 判赔 41（音集协、北京；含 8 可可西里）——
    verdict_strat = [("诉讼相对方", 25), ("雷石", 10), ("雷客", 6)]
    verdict_payer = []
    for p, c in verdict_strat:
        verdict_payer += [p] * c
    rng.shuffle(verdict_payer)
    for i in range(N_VERDICT):
        r = base_row("verdict", verdict=True)
        pay_cents = verdict_pay_cents[i]
        r["case_status"] = "已结案"
        r["resolve"] = "判赔"
        r["resolve_detail"] = "被告停止侵权并赔偿经济损失，判决已生效"
        r["plaintiff"] = ACM_PLAINTIFF
        r["plaintiff_raw"] = ACM_PLAINTIFF
        r["pay_amount"] = pay_cents / 100.0
        r["amount"] = round(r["pay_amount"] / VERDICT_AMOUNT_RATIO, 2)
        r["song_count"] = verdict_song_counts[i]
        r["per_song_amount"] = 870.0
        r["payer"] = verdict_payer[i]
        r["support_rate"] = round(rng.uniform(0.28, 0.34), 4)
        r["close_date"] = r["accept_date"] + VERDICT_CYCLE_DAYS * DAY_MS
        r["doc1_date"] = r["accept_date"] + rng.randint(90, 130) * DAY_MS
        r["defendant"], r["defendant_raw"] = _json([_defendant("b", head=True)]), None
        r["notes"] = f"音集协批量维权系列案：被告未经许可在经营场所播放涉案作品，一审判决停止侵权并赔偿经济损失，被告已履行。"
        if i < N_PAID_VERDICT:
            r["pay_date"] = r["close_date"] + rng.randint(10, 60) * DAY_MS
        if i < 20:
            r["exec_case_no"] = f"({r['year']})京0105执{3000 + i}号"
        if i < 20:
            r["dirty_flags"] = _json(["amount"])
        add(r)

    # —— ② 胜诉类 147（前期参数：音集协 100 / 非 47）——
    win_res = []
    for name, cnt in WIN_RESOLVES:
        win_res += [name] * cnt
    rng.shuffle(win_res)
    for i in range(N_WIN):
        r = base_row("win")
        r["case_status"] = "已结案"
        r["resolve"] = win_res[i]
        r["resolve_detail"] = "对方诉请被驳回/二审维持原判"
        r["plaintiff"] = ACM_PLAINTIFF if i < 100 else "雷石音乐文化发展有限公司"
        r["plaintiff_raw"] = r["plaintiff"]
        r["close_date"] = r["accept_date"] + VERDICT_CYCLE_DAYS * DAY_MS
        r["notes"] = "二审驳回上诉，维持原判。"
        add(r)

    # —— ③ 和解 6（音集协 4）——
    for i in range(N_SETTLE):
        r = base_row("settle")
        r["case_status"] = "已结案"
        r["resolve"] = "双方和解"
        r["resolve_detail"] = "双方达成和解协议，被告支付和解款"
        r["plaintiff"] = ACM_PLAINTIFF if i < 4 else "雷石音乐文化发展有限公司"
        r["close_date"] = r["accept_date"] + VERDICT_CYCLE_DAYS * DAY_MS
        pc = sub_pay_cents[i]
        r["pay_amount"] = pc / 100.0
        r["amount"] = round(pc / 100.0 * 100, 2)
        r["pay_date"] = r["close_date"] + rng.randint(10, 40) * DAY_MS
        r["notes"] = "双方达成和解协议，被告支付和解款后结案。"
        add(r)

    # —— ④ 在办 42（音集协 7）——
    open_status = []
    for name, cnt in OPEN_STATUS:
        open_status += [name] * cnt
    rng.shuffle(open_status)
    for i in range(N_OPEN):
        r = base_row("open")
        r["case_status"] = open_status[i]
        r["resolve"] = None
        r["plaintiff"] = ACM_PLAINTIFF if i < 7 else "雷石音乐文化发展有限公司"
        r["amount"] = round(rng.uniform(5_000, 90_000), 2)
        if i % 2 == 0:
            r["court_date"] = r["accept_date"] + rng.randint(40, 90) * DAY_MS
        add(r)

    # —— ⑤ 其他 402（音集协 160）——
    other_res = []
    for name, cnt in OTHER_RESOLVES:
        other_res += [name] * cnt
    rng.shuffle(other_res)
    for i in range(N_OTHER):
        r = base_row("other")
        r["case_status"] = "已结案"
        r["resolve"] = other_res[i]
        r["resolve_detail"] = "程序性/实体性结案"
        r["plaintiff"] = ACM_PLAINTIFF if i < 160 else "雷石音乐文化发展有限公司"
        r["close_date"] = r["accept_date"] + VERDICT_CYCLE_DAYS * DAY_MS
        idx = N_SETTLE + i
        pc = sub_pay_cents[idx]
        r["pay_amount"] = pc / 100.0
        r["amount"] = round(pc / 100.0 * 100, 2)
        r["notes"] = rng.choice(["该案按程序结案。", None, None])
        if i % 15 == 0:  # 402/15 ≈ 27 案 → 与判赔 20 合计 dirty=47
            r["dirty_flags"] = _json(["amount"] if i % 30 else ["amount", "year"])
        add(r)

    # —— 分配 biz_line ——
    biz_seq = _biz_seq()
    for r in rows:
        r["biz_line"] = biz_seq.pop()

    # —— 分配 plaintiff=非音集协 的原告名（雷石以外的公司名）——
    # —— 分配案由（音集协 312 前 3；非音集协 12 项）——
    acm_rows = [r for r in rows if r["plaintiff"] == ACM_PLAINTIFF]
    non_acm_rows = [r for r in rows if r["plaintiff"] != ACM_PLAINTIFF]
    assert len(acm_rows) + len(non_acm_rows) == N_TOTAL

    def fill_cause(pool: list[dict], spec: list[tuple[str, int]]) -> None:
        seq_cause = []
        for name, cnt in spec:
            seq_cause += [name] * cnt
        rng.shuffle(seq_cause)
        for r, name in zip(pool, seq_cause):
            r["cause"] = name

    fill_cause(acm_rows, ACM_CAUSE)
    fill_cause(non_acm_rows, OTHER_CAUSE)

    # —— 被告（区域联动：判赔已在 base_row 强制北京 head）——
    for r in rows:
        if r["defendant"] is not None:  # 判赔案已在生成时定被告
            continue
        reg = "b"
        if any(k in (r["court"] or "") for k in ("天河", "南山", "越秀", "广州知识产权")):
            reg = "gd"
        elif any(k in (r["court"] or "") for k in ("长沙", "株洲", "开福", "岳麓")):
            reg = "hn"
        elif any(k in (r["court"] or "") for k in ("上海", "成都", "重庆", "西安", "杭州")):
            reg = "ot"
        d = _defendant(reg)
        r["defendant"] = _json([d])
        r["defendant_raw"] = _json([d])

    # —— dirty_flags 校验（47：判赔 20 + 其他 27）——
    dirty_n = sum(1 for r in rows if r["dirty_flags"] and '"amount"' in r["dirty_flags"])
    assert dirty_n == N_DIRTY_AMOUNT, dirty_n

    meta = {
        "acm": acm_rows,
        "non_acm": non_acm_rows,
        "dirty_n": dirty_n,
        "verdict_rows": [r for r in rows if r["_cat"] == "verdict"],
        "kekexili_verdict": [],  # 由歌曲分配回填
    }
    return rows, meta


def main() -> None:
    with SessionLocal() as db:
        # 幂等清空（顺序满足外键；FTS 由 rebuild_cases_fts 全量重建）
        db.execute(delete(SongCase))
        db.execute(delete(Song))
        db.execute(delete(Case))
        db.execute(delete(TagLink))
        db.execute(delete(Tag))

        rows, meta = build_case_rows()

        # —— cases 批量插入 ——
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        case_objs: list[Case] = []
        for r in rows:
            kw = {k: v for k, v in r.items() if not k.startswith("_")}
            kw["created_at"] = now_ms
            kw["updated_at"] = now_ms
            case_objs.append(Case(**kw))
        db.add_all(case_objs)
        db.flush()
        rid_to_id = {c.record_id: c.id for c in case_objs}

        # —— 歌曲 + 关联 ——
        # 首批 36 首高曲，其余 1248 首普通曲
        song_objs = [Song(record_id=f"recS{i + 1:04d}", song_name=name,
                          song_name_raw=name,
                          artist="索南扎西" if name == "可可西里" else rng.choice(
                              ["周杰伦", "朴树", "周华健", "赵雷", "陈奕迅", "邓紫棋", "凤凰传奇", "筷子兄弟"]),
                          synced_at=now_ms, created_at=now_ms, updated_at=now_ms)
                     for i, name in enumerate(HIGH_SONGS)]
        song_objs += [Song(record_id=f"recS{i + 1:04d}", song_name=f"批量曲目{i + 1:04d}",
                           song_name_raw=f"批量曲目{i + 1:04d}", artist=None,
                           synced_at=now_ms, created_at=now_ms, updated_at=now_ms)
                      for i in range(len(HIGH_SONGS), N_SONGS)]
        db.add_all(song_objs)
        db.flush()
        song_rid_to_id = {s.record_id: s.id for s in song_objs}
        kekexili_song_id = song_rid_to_id["recS0001"]

        # 覆盖案集合：150 高曲案（41 判赔 + 109 其他）+ 462 普通曲案（不相交）
        verdict_ids = [rid_to_id[r["record_id"]] for r in meta["verdict_rows"]]
        non_verdict_ids = [rid_to_id[r["record_id"]] for r in rows
                           if r["_cat"] != "verdict"]
        rng.shuffle(non_verdict_ids)
        other_high_ids = non_verdict_ids[: N_HIGH_COVER_CASES - N_VERDICT]
        rest_ids = non_verdict_ids[N_HIGH_COVER_CASES - N_VERDICT:]
        mid_ids = rng.sample(rest_ids, N_MID_COVER_CASES)
        high_case_ids = verdict_ids + other_high_ids  # 150

        # 可可西里 16 案：8 判赔（pay=960）+ 8 其他
        kekexili_verdict_ids = verdict_ids[:8]
        kekexili_other_ids = other_high_ids[-8:]
        kekexili_case_ids = kekexili_verdict_ids + kekexili_other_ids

        # 其余 35 曲 → 198 条关联到其余 134 案（每曲 ≥1 案，pair 去重保唯一）
        links: list[SongCase] = []
        other_35_ids = [song_rid_to_id[f"recS{i + 2:04d}"] for i in range(35)]
        pool_ids = [c for c in high_case_ids if c not in set(kekexili_case_ids)]  # 134
        rng.shuffle(pool_ids)
        used_pairs: set[tuple[int, int]] = set()
        for r_i, sid in zip(pool_ids, other_35_ids):
            links.append(SongCase(song_id=sid, case_id=r_i, role="主"))  # 每曲 1 案
            used_pairs.add((sid, r_i))
        remain = 198 - 35
        while remain > 0:
            pair = (rng.choice(other_35_ids), rng.choice(pool_ids))
            if pair in used_pairs:
                continue
            used_pairs.add(pair)
            links.append(SongCase(song_id=pair[0], case_id=pair[1], role="主"))
            remain -= 1

        # 可可西里 16 案
        for cid in kekexili_case_ids:
            links.append(SongCase(song_id=kekexili_song_id, case_id=cid, role="主"))

        # 普通曲 1248 → 462 案（每案 2~3 首）
        mid_song_ids = [song_rid_to_id[f"recS{i + 1:04d}"] for i in range(36, N_SONGS)]
        per_mid = _split_counts(N_SONGS - 36, N_MID_COVER_CASES, 2, 3)
        assert sum(per_mid) == N_SONGS - 36
        mid_cursor = 0
        for cid, cnt in zip(mid_ids, per_mid):
            for _ in range(cnt):
                links.append(SongCase(song_id=mid_song_ids[mid_cursor], case_id=cid, role="主"))
                mid_cursor += 1
        assert mid_cursor == N_SONGS - 36
        assert len(links) == N_SONG_CASE, len(links)
        db.add_all(links)
        db.flush()

        # —— 标签 6 + 关联 ——
        tags = [
            Tag(name="批量维权", kind="manual", color="blue", description="音集协批量维权系列案"),
            Tag(name="高标的", kind="manual", color="red", description="标的额超过 10 万元的案件"),
            Tag(name="异地管辖", kind="manual", color="orange", description="受理法院不含北京（音集协注册地异地）"),
            Tag(name="执行到位", kind="manual", color="green", description="判赔后已实际支付（pay_date 存在）"),
            Tag(name="系列案", kind="derived", color="purple", description="多曲/多案关联的系列诉讼"),
            Tag(name="判赔主力", kind="derived", color="amber", description="判赔额 Top 被告画像标签"),
        ]
        db.add_all(tags)
        db.flush()
        tag_ids = {t.name: t.id for t in tags}

        link_rows: list[TagLink] = []

        def tl(tag: str, target_type: str, target_id: str) -> None:
            link_rows.append(TagLink(tag_id=tag_ids[tag], target_type=target_type, target_id=target_id))

        verdict_rids = [r["record_id"] for r in meta["verdict_rows"]]
        # 批量维权 → 判赔案 30 + 高曲 6
        for rid in verdict_rids[:30]:
            tl("批量维权", "case", rid)
        for i in range(6):
            tl("批量维权", "song", f"recS{i + 1:04d}")
        # 高标的 → amount 最大的 12 判赔案
        top_amount = sorted(meta["verdict_rows"], key=lambda r: r["amount"] or 0, reverse=True)[:12]
        for r in top_amount:
            tl("高标的", "case", r["record_id"])
        # 异地管辖 → 非北京法院 20 案
        offsite_rows = [r for r in rows if r["court"] and "北京" not in r["court"]][:20]
        for r in offsite_rows:
            tl("异地管辖", "case", r["record_id"])
        # 执行到位 → pay_date 判赔案 20
        paid = [r for r in meta["verdict_rows"] if r["pay_date"] is not None][:20]
        for r in paid:
            tl("执行到位", "case", r["record_id"])
        # 系列案 → 歌曲关联数 ≥3 的案（取前 15 by 关联数）
        case_song_counts: dict[int, int] = {}
        for l in links:
            case_song_counts[l.case_id] = case_song_counts.get(l.case_id, 0) + 1
        series_cases = sorted(case_song_counts, key=case_song_counts.get, reverse=True)[:15]
        for cid in series_cases:
            tl("系列案", "case", next(r["record_id"] for r in rows if rid_to_id[r["record_id"]] == cid))
        # 判赔主力 → 判赔额 top10 被告
        verdict_by_def: dict[str, float] = {}
        for r in meta["verdict_rows"]:
            d = json.loads(r["defendant"])[0] if r["defendant"] else None
            if d:
                verdict_by_def[d] = verdict_by_def.get(d, 0) + (r["pay_amount"] or 0)
        for name in sorted(verdict_by_def, key=verdict_by_def.get, reverse=True)[:10]:
            tl("判赔主力", "party", name)
        db.add_all(link_rows)

        # —— FTS 全量重建（12 列影子表）——
        n_fts = rebuild_cases_fts(db)
        db.commit()

        # —— 汇总自校验 ——
        total = db.execute(select(func.count(Case.id))).scalar()
        acm = db.execute(select(func.count(Case.id)).where(Case.plaintiff.like("%音集协%"))).scalar()
        songs_n = db.execute(select(func.count(Song.id))).scalar()
        links_n = db.execute(select(func.count(SongCase.id))).scalar()
        tags_n = db.execute(select(func.count(Tag.id))).scalar()
        tlinks_n = db.execute(select(func.count(TagLink.id))).scalar()
        print("=" * 64)
        print("seed_truth 灌入完成（开发库 data/app.db）")
        print(f"  cases={total} / acm={acm} / songs={songs_n} / song_case={links_n}")
        print(f"  tags={tags_n} / tag_links={tlinks_n} / fts={n_fts}")
        print(f"  dirty_amount={meta['dirty_n']}（目标 47） / verdict=41")
        assert total == N_TOTAL and acm == N_ACM
        assert songs_n == N_SONGS and links_n == N_SONG_CASE
        assert tags_n == 6 and n_fts == N_TOTAL
        print("  ✓ 数量断言全部通过")


if __name__ == "__main__":
    main()