"""G5~G10 真值断言（阶段验证 b09）。

对开发库（data/app.db，seed_truth.py 灌入的真值基线）走真实 HTTP 端点
（TestClient 触发 lifespan init_db 幂等），逐项断言 docs/05 G5~G10 数值基准：

- G5 对手方画像：overview.summary{638,312,1,284,600} + 8 KPI
  （0.7819 / 0.7887 / 0.064 / 0.312 / 870 / 186 / 1.0 / 42）+ parties/party；
- G6 多维分析：analysis bizYear 8×8（total 638、判赔 41）+ drill x=VOD 160；
- G7 歌曲维度：song_case 失效场景 可可西里{16, 7,680} + aggregate{869.74, 1477, 41}；
- G8 费用看板：verdict{1,284,600/41}、recovered{1,284,600/34}、expense/net=None、dubious=47；
- G9 检索/同质案类推：search 音集协=312、similar recT0001 命中（相似度权重组）；
- G10 标签/报告：tags=6、reports≥1、report-templates T1~T7 全量。

运行：cd backend && .venv/bin/python scripts/verify_g_values.py
退出码：0=全过；1=存在 FAIL（逐项输出 PASS/FAIL，全量结果打印归档）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"
FAIL: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  | {detail}" if detail else ""))
    if not cond:
        FAIL.append(f"{label} | {detail}")


def approx(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= tol


def ok_data(resp) -> dict:
    body = resp.json()
    assert body["code"] == 0, f"code != 0: {body}"
    return body["data"]


with TestClient(app) as client:
    print("== G5 对手方画像（overview / parties / party） ==")
    d = ok_data(client.get(f"{API}/stats/overview"))
    s = d["summary"]
    check("overview.summary.total_cases == 638", s["total_cases"] == 638, f"total={s['total_cases']}")
    check("overview.summary.acmc_cases == 312", s["acmc_cases"] == 312, f"acmc={s['acmc_cases']}")
    check("overview.summary.verdict_total == 1284600", approx(s["verdict_total"], 1284600.0, 0.01),
          f"verdict_total={s['verdict_total']}")
    kpis = {m["key"]: m["value"] for m in d["kpis"]}
    expect = {
        "win_rate_a": (0.7819, 0.0001),
        "win_rate_b": (0.7887, 0.0001),
        "support_rate": (0.064, 0.0005),
        "verdict_rate": (0.312, 0.001),
        "per_song": (870.0, 0.0),
        "cycle": (186.0, 0.0),
        "series_coef": (1.0, 0.0),
        "open_count": (42, 0),
    }
    for k, (v, tol) in expect.items():
        check(f"KPI {k} ≈ {v}", k in kpis and approx(kpis[k], v, tol), f"value={kpis.get(k)}")
    trend_cc = sum(r["case_count"] for r in d["trend"])
    trend_va = sum(r["verdict_amount"] for r in d["trend"])
    check("trend sum(case_count) == 638", trend_cc == 638, f"sum={trend_cc}")
    check("trend sum(verdict_amount) == 1284600", approx(trend_va, 1284600.0, 0.01), f"sum={trend_va}")
    biz_cc = sum(r["case_count"] for r in d["bizline"])
    biz_va = sum(r["verdict_amount"] for r in d["bizline"])
    check("bizline sum(case_count) == 638", biz_cc == 638, f"sum={biz_cc}")
    check("bizline sum(verdict_amount) == 1284600", approx(biz_va, 1284600.0, 0.01), f"sum={biz_va}")

    d = ok_data(client.get(f"{API}/stats/parties"))
    items = d["items"]
    check("parties.covered_cases == 638", d["covered_cases"] == 638, f"covered={d['covered_cases']}")
    check("parties.total_parties > 0", d["total_parties"] > 0, f"n={d['total_parties']}")
    check("parties 按 case_count 降序", all(items[i]["case_count"] >= items[i + 1]["case_count"]
                                            for i in range(len(items) - 1)))
    top = max(items, key=lambda x: x["verdict_count"])
    print(f"  判赔主力 party：{top['name']} verdict={top['verdict_count']}件 "
          f"amount={top['verdict_amount']}（抽查详情）")
    pd = ok_data(client.get(f"{API}/stats/party", params={"name": top["name"]}))
    check("party.total > 0", pd["total"] > 0, f"total={pd['total']}")
    check("party.verdict_count == 榜单值", pd["verdict_count"] == top["verdict_count"],
          f"detail={pd['verdict_count']} list={top['verdict_count']}")
    check("party.verdict_amount 在榜", approx(pd["verdict_amount"], top["verdict_amount"], 0.01))
    check("party.years/causes 非空", bool(pd["years"]) and bool(pd["causes"]))
    check("party.win_rate_a 0~1", pd["win_rate_a"] is None or 0 <= pd["win_rate_a"] <= 1,
          f"win_rate_a={pd['win_rate_a']}")

    print("== G6 多维分析（analysis + drill） ==")
    d = ok_data(client.get(f"{API}/stats/analysis", params={"dim": "bizYear"}))
    rows, cols = d["rows"], d["cols"]
    cells = d["cells"]  # 二维数组 [row_i][col_j]（行=业务线，列=年份）
    tot = sum(cells[i][j]["case_count"] for i in range(len(rows)) for j in range(len(cols)))
    vtot = sum(cells[i][j]["verdict_count"] for i in range(len(rows)) for j in range(len(cols)))
    check("analysis bizYear rows == 8", len(rows) == 8, f"rows={len(rows)}")
    check("analysis bizYear cols == 8", len(cols) == 8, f"cols={len(cols)}")
    check("analysis total_cases == 638", d["total_cases"] == 638, f"total={d['total_cases']}")
    check("analysis sum(cells.case_count) == 638", tot == 638, f"sum={tot}")
    check("analysis sum(cells.verdict_count) == 41", vtot == 41, f"sum={vtot}")
    dd = ok_data(client.get(f"{API}/stats/analysis/drill", params={"dim": "bizYear", "x": "VOD"}))
    check("drill x=VOD total == 160", dd["total"] == 160, f"total={dd['total']}")
    check("drill items == 160", len(dd["items"]) == 160, f"items={len(dd['items'])}")
    check("drill causes 非空", bool(dd["causes"]), f"causes={len(dd['causes'])}")

    print("== G7 歌曲维度（songs） ==")
    d = ok_data(client.get(f"{API}/stats/songs"))
    s0 = d["songs"][0]
    check("songs[0] 可可西里", s0["song_name"] == "可可西里", f"name={s0['song_name']}")
    check("songs[0].case_count == 16", s0["case_count"] == 16, f"count={s0['case_count']}")
    check("songs[0].verdict_amount == 7680", approx(s0["verdict_amount"], 7680.0, 0.01),
          f"amount={s0['verdict_amount']}")
    agg = d["aggregate"]
    check("aggregate.avg_per_song == 869.74", approx(agg["avg_per_song"], 869.74, 0.01),
          f"avg={agg['avg_per_song']}")
    check("aggregate.total_song_slots == 1477", agg["total_song_slots"] == 1477,
          f"slots={agg['total_song_slots']}")
    check("aggregate.case_count == 41", agg["case_count"] == 41, f"count={agg['case_count']}")
    check("songs.metric.per_song == 870.0", approx(d["metric"]["value"], 870.0, 0.0),
          f"metric={d['metric']['value']}")

    print("== G8 费用看板（fees） ==")
    d = ok_data(client.get(f"{API}/stats/fees"))
    four = d["four"]
    check("fees.verdict {1284600, 41}", approx(four["verdict"]["amount"], 1284600.0, 0.01)
          and four["verdict"]["count"] == 41,
          f"verdict={four['verdict']}")
    check("fees.recovered {1284600, 34}", approx(four["recovered"]["amount"], 1284600.0, 0.01)
          and four["recovered"]["count"] == 34,
          f"recovered={four['recovered']}")
    check("fees.expense 未接入 None", four["expense"]["amount"] is None
          and four["expense"]["count"] is None)
    check("fees.net 未接入 None", four["net"]["amount"] is None)
    check("fees.dubious == 47", len(d["dubious"]) == 47, f"dubious={len(d['dubious'])}")
    check("fees.monthly 非空", bool(d["monthly"]))

    print("== G9 检索 / 同质案类推 ==")
    sbody = client.post(f"{API}/search", json={"q": "音集协", "page": 1, "page_size": 5}).json()
    check("search 音集协 total == 312", sbody["meta"]["total"] == 312,
          f"total={sbody['meta']['total']}")
    check("search rows 含 record_id", bool(sbody["data"]) and all("record_id" in r for r in sbody["data"]))
    sd = ok_data(client.post(f"{API}/similar", json={"case_id": "recT0001"}))
    check("similar target 非空", bool(sd.get("target")))
    top_sim = max((i.get("similarity", 0) for i in sd["items"]), default=0)
    check("similar items ≥ 1 且 top > 0", len(sd["items"]) >= 1 and top_sim > 0,
          f"items={len(sd['items'])} top={top_sim}")
    check("similar weights 非空", bool(sd.get("weights")), f"weights={list(sd.get('weights', {}))}")
    cd = ok_data(client.get(f"{API}/cases/recT0001"))
    check("cases/recT0001 详情五区可读", bool(cd.get("base")) and bool(cd.get("case_no", cd["base"].get("case_no")))
          and "songs" in cd and "series" in cd,
          f"detail_keys={list(cd)}")

    print("== G10 标签 / 报告 ==")
    body = client.get(f"{API}/tags").json()
    tags = body["data"]
    check("tags total == 6", body["meta"]["total"] == 6 and len(tags) == 6,
          f"tags={len(tags)}")
    check("tag dict 字段齐全", all(t.get("name") and t.get("kind") and "link_count" in t for t in tags))
    rb = client.get(f"{API}/reports").json()
    check("reports total ≥ 1", rb["meta"]["total"] >= 1, f"reports={rb['meta']['total']}")
    check("report 列表不含 body", bool(rb["data"]) and "body" not in rb["data"][0])
    tb = client.get(f"{API}/ai/report-templates").json()
    tkeys = [t["key"] for t in tb["data"]]
    check("report-templates total == 7", tb["meta"]["total"] == 7 and len(tkeys) == 7,
          f"keys={tkeys}")
    check("template 字段齐全", all(t.get("title") and t.get("description") for t in tb["data"]))

print()
if FAIL:
    print(f"共 {len(FAIL)} 项 FAIL：")
    for f in FAIL:
        print(f"  - {f}")
    sys.exit(1)
print("全部真值断言通过（G5~G10 数值基线一致）")