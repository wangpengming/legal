#!/usr/bin/env python3
# =============================================
# extractor_cli.py - 案例提取 CLI
# 用法:
#   python bin/extract.py register --name "案件名" --plaintiff "原告" --defendant "被告" ...
#   python bin/extract.py list
#   python bin/extract.py extract --case-id <id> --type defense_argument_chain --title "标题"
#   python bin/extract.py promote --artifact-id <id> --template-name "模板名" --category "答辩状"
#   python bin/extract.py complete --case-id <id>
#   python bin/extract.py search --query "关键词"
#   python bin/extract.py check --case-number "案号"
#   python bin/extract.py report
# =============================================
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import database as db
from src import case_recognizer as cr
from src import artifact_store
from src import template_store


# =============================================
# 辅助函数
# =============================================

def _print_case(c: dict) -> None:
    """打印案件概要。"""
    status_emoji = {"pending": "⏳", "extracted": "✅", "archived": "📦"}.get(
        c["status"], "❓"
    )
    n = db.count_artifacts_by_case(c["id"])
    print(
        f"  [{status_emoji}] {c['case_name']}"
        f"\n       案号: {c.get('case_number', 'N/A')}"
        f"\n       原告: {c.get('plaintiff', '')} | 被告: {c.get('defendant', '')}"
        f"\n       案由: {c.get('cause', '')}"
        f"\n       提取物: {n} 个 | 状态: {c['status']}"
        f"\n       ID: {c['id']}"
    )


def _input_multiline(prompt: str) -> str:
    """多行输入（Ctrl+D 结束）。"""
    print(f"\n{prompt}（输入完成后按 Ctrl+D 结束）:")
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines).strip()


def _input_required(prompt: str) -> str:
    """必填输入（不能为空）。"""
    while True:
        val = input(prompt).strip()
        if val:
            return val
        print("  ❌ 不能为空，请重新输入。")


def _select_one(options: list[str], prompt: str) -> str:
    """数字选择（单选）。"""
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        try:
            idx = int(input(prompt)) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print("  ❌ 无效选择，请重新输入。")


# =============================================
# register 命令
# =============================================

def cmd_register(args) -> None:
    """注册新案件。"""
    print(f"\n📋 注册案件")
    print("=" * 50)

    # 全部从 args 获取（支持 --name 'xxx' 或纯交互式运行）
    name = getattr(args, "name", None) or getattr(args, "case_name", None)
    if not name:
        try:
            name = _input_required("案件名称: ")
        except EOFError:
            print("❌ 交互式输入失败，请使用 --name 等参数重试")
            sys.exit(1)
    case_number = getattr(args, "case_number", None) or ""
    plaintiff = getattr(args, "plaintiff", None) or ""
    defendant = getattr(args, "defendant", None) or ""
    cause = getattr(args, "cause", None) or ""
    result = getattr(args, "result", None) or ""
    source_path = getattr(args, "source_path", None) or ""
    notes = getattr(args, "notes", None) or ""

    # 识别重复
    if case_number:
        r = cr.recognize_case(case_number=case_number)
        if r["exact"]:
            print(
                f"\n⚠️  案号已存在: {r['exact']['case_name']}"
                f"\n   状态: {r['exact']['status']} | ID: {r['exact']['case_id']}"
            )
            if not input("\n是否仍要注册？（y/N）: ").strip().lower() == "y":
                print("已取消。")
                return

    try:
        case = db.create_case(
            case_name=name,
            case_number=case_number or None,
            plaintiff=plaintiff,
            defendant=defendant,
            cause=cause,
            result=result,
            source_path=source_path,
            notes=notes,
        )
        print(f"\n✅ 案件注册成功")
        _print_case(case)
    except Exception as e:
        print(f"❌ 注册失败: {e}", file=sys.stderr)
        sys.exit(1)


# =============================================
# link 命令
# =============================================

def cmd_link(args) -> None:
    """关联原始材料路径。"""
    case = db.get_case(args.case_id)
    if not case:
        print(f"❌ 案件不存在: {args.case_id}")
        sys.exit(1)

    path = args.path or input("原始文件路径: ").strip()
    if not path:
        print("❌ 路径不能为空")
        sys.exit(1)

    # 更新 source_path
    conn = db._get_conn()
    conn.execute(
        "UPDATE cases SET source_path = ? WHERE id = ?", (path, args.case_id)
    )
    conn.commit()
    conn.close()
    print(f"✅ 路径已关联: {path}")


# =============================================
# extract 命令
# =============================================

def cmd_extract(args) -> None:
    """提取 Artifact。"""
    case = db.get_case(args.case_id)
    if not case:
        print(f"❌ 案件不存在: {args.case_id}")
        sys.exit(1)

    print(f"\n📦 提取 Artifact")
    print(f"案件: {case['case_name']}")
    print("=" * 50)

    # 确认类型
    if args.type:
        artifact_type = args.type
    else:
        artifact_type = _select_one(
            db.ARTIFACT_TYPES,
            "选择提取物类型（数字）: ",
        )

    # 标题
    title = args.title or _input_required("提取物标题: ")

    # 来源引用
    source_ref = args.source_ref or input("来源引用（如：从答辩状第3段提取，可选）: ").strip()

    # 内容
    if args.content:
        content = args.content
    else:
        content_map = {
            "defense_argument_chain": "## 抗辩主线\n\n## 核心论点\n\n## 法律依据\n\n## 论证结构\n\n## 适用条件\n",
            "cross_exam_strategy": "## 质证结论\n\n## 理由\n\n## 攻击点\n",
            "evidence_structure": "## 证据分类\n\n## 证据清单\n",
            "legal_reasoning_chain": "## 推理前提\n\n## 推理步骤\n\n## 结论\n",
            "quantitative_analysis": "## 量化指标\n\n## 计算公式\n\n## 数据来源\n",
            "liability_calculation": "## 责任类型\n\n## 计算方式\n\n## 参考法条\n",
            "contingency_response": "## 场景\n\n## 应变话术\n\n## 注意事项\n",
            "reverse_strategy": "## 打击维度\n\n## 弹药路径\n\n## 时间轴\n",
            "court_statement": "## 开场\n\n## 主体论点\n\n## 总结\n",
            "case_key_facts": "## 关键事实清单\n\n## 事实状态\n",
        }
        content = _input_multiline(
            content_map.get(artifact_type, "## 内容\n\n")
        )

    artifact = artifact_store.create_artifact(
        case_id=args.case_id,
        artifact_type=artifact_type,
        title=title,
        content=content,
        source_ref=source_ref,
    )
    print(f"\n✅ Artifact 创建成功")
    print(f"  ID: {artifact['id']}")
    print(f"  类型: {artifact['artifact_type']}")
    print(f"  标题: {artifact['title']}")
    print(f"  文件: {artifact.get('file_path', 'N/A')}")


# =============================================
# promote 命令
# =============================================

def cmd_promote(args) -> None:
    """将 Artifact 归纳为通用 Template。"""
    artifact = db.get_artifact(args.artifact_id)
    if not artifact:
        print(f"❌ 提取物不存在: {args.artifact_id}")
        sys.exit(1)

    print(f"\n📄 从 Artifact 归纳 Template")
    print(f"Artifact: {artifact['title']}（{artifact['artifact_type']}）")

    name = args.template_name or _input_required("模板名称: ")
    category = args.category or _select_one(
        db.TEMPLATE_CATEGORIES, "选择模板分类（数字）: "
    )
    template = template_store.create_template(
        name=name,
        content=artifact.get("content", ""),
        category=category,
        source_artifacts=[artifact["id"]],
        source_case_ids=[artifact["case_id"]],
    )
    print(f"\n✅ Template 创建成功")
    print(f"  ID: {template['id']}")
    print(f"  分类: {template['category']}")
    print(f"  文件: {template.get('file_path', 'N/A')}")


# =============================================
# complete 命令
# =============================================

def cmd_complete(args) -> None:
    """标记案件为 extracted。"""
    case = db.get_case(args.case_id)
    if not case:
        print(f"❌ 案件不存在: {args.case_id}")
        sys.exit(1)
    db.update_case_status(args.case_id, "extracted")
    n = db.count_artifacts_by_case(args.case_id)
    print(f"✅ 案件标记为 extracted，共 {n} 个提取物")


# =============================================
# list 命令
# =============================================

def cmd_list(args) -> None:
    """列出案件列表。"""
    status = args.status
    cases = db.list_cases(status=status)
    if not cases:
        print("暂无案件")
        return
    total = len(cases)
    extracted = sum(1 for c in cases if c["status"] == "extracted")
    print(f"\n📋 案件列表（共 {total} 个，已提取 {extracted} 个）")
    print("=" * 60)
    for c in cases:
        _print_case(c)
        print()


# =============================================
# search 命令
# =============================================

def cmd_search(args) -> None:
    """搜索案件。"""
    results = db.search_cases(args.query)
    if not results:
        print("未找到匹配案件")
        return
    print(f"\n🔍 搜索结果（{len(results)} 个）")
    print("=" * 60)
    for c in results:
        _print_case(c)
        print()


# =============================================
# check 命令
# =============================================

def cmd_check(args) -> None:
    """识别新案件是否重复。"""
    r = cr.recognize_case(
        case_number=args.case_number,
        plaintiff=args.plaintiff or "",
        defendant=args.defendant or "",
        cause=args.cause or "",
    )
    print("\n🔍 案件识别结果")
    print("=" * 50)
    if r["exact"]:
        c = r["exact"]
        print(f"✅ 完全匹配（案号精确）")
        print(f"   案件: {c['case_name']}")
        print(f"   案号: {c['case_number']}")
        print(f"   状态: {c['status']} | ID: {c['case_id']}")
    elif r["partial"]:
        print(f"⚠️  当事人匹配（{len(r['partial'])} 个）")
        for c in r["partial"]:
            print(f"   - {c['case_name']} | 案由: {c['cause']} | 状态: {c['status']}")
            print(f"     ID: {c['case_id']}")
    elif r["cause_fuzzy"]:
        print(f"🔎 案由相似（{len(r['cause_fuzzy'])} 个）")
        for c in r["cause_fuzzy"]:
            print(f"   - {c['case_name']} | 案由: {c['cause']} | 置信度: {c['confidence']}")
    else:
        print("🆕 新案件（未找到匹配）")


# =============================================
# report 命令
# =============================================

def cmd_report(args) -> None:
    """生成案件处理报告。"""
    s = db.get_summary()
    print("\n📊 案例库统计报告")
    print("=" * 50)
    print(f"  案件总数:   {s['total_cases']}")
    print(f"  已提取:     {s['extracted_cases']} 个")
    print(f"  待提取:     {s['pending_cases']} 个")
    print(f"  提取物总数: {s['total_artifacts']} 个")
    print(f"  模板总数:   {s['total_templates']} 个")

    # 按类型统计提取物
    conn = db._get_conn()
    rows = conn.execute(
        """
        SELECT artifact_type, COUNT(*) as cnt
        FROM artifacts
        GROUP BY artifact_type
        ORDER BY cnt DESC
        """
    ).fetchall()
    conn.close()
    if rows:
        print("\n  提取物类型分布:")
        for r in rows:
            print(f"    {r[0]}: {r[1]} 个")

    # 待提取案件
    pending = db.list_cases(status="pending")
    if pending:
        print(f"\n  待提取案件（{len(pending)} 个）:")
        for c in pending[:5]:
            print(f"    - {c['case_name']} | {c.get('case_number', 'N/A')}")


# =============================================
# templates 命令
# =============================================

def cmd_templates(args) -> None:
    """列出或搜索模板。"""
    if args.templates_action == "list":
        templates = template_store.list_templates_by_category(
            args.category if args.category else None
        )
        if not templates:
            print("暂无语板")
            return
        # 按分类分组
        from collections import defaultdict
        by_cat = defaultdict(list)
        for t in templates:
            by_cat[t["category"]].append(t)
        print(f"\n📄 模板列表（共 {len(templates)} 个）")
        print("=" * 60)
        for cat, ts in sorted(by_cat.items()):
            print(f"\n  [{cat}] ({len(ts)} 个)")
            for t in ts:
                src = json.loads(t.get("source_case_ids", "[]"))
                case_hint = f"来源案件: {len(src)}个" if src else ""
                print(
                    f"    - {t['name']}  "
                    f"(v{t['version']} | 使用:{t['usage_count']}次) {case_hint}"
                )
                print(f"      ID: {t['id']}")
    elif args.templates_action == "search":
        results = template_store.search_templates(args.query)
        if not results:
            print("未找到匹配模板")
            return
        print(f"\n🔍 模板搜索结果（{len(results)} 个）")
        print("=" * 60)
        for t in results:
            print(
                f"  [{t['category']}] {t['name']} "
                f"(v{t['version']} | 使用:{t['usage_count']}次)"
            )
            # 显示匹配片段
            if args.show_content:
                content = t.get("content", "")[:200]
                print(f"    内容预览: {content}...")
            print(f"    ID: {t['id']}")
    elif args.templates_action == "show":
        tmpl = db.get_template(args.template_id)
        if not tmpl:
            print(f"❌ 模板不存在: {args.template_id}")
            sys.exit(1)
        print(f"\n📄 {tmpl['name']} [{tmpl['category']}]")
        print("=" * 60)
        print(f"  ID:     {tmpl['id']}")
        print(f"  版本:   {tmpl['version']}")
        print(f"  分类:   {tmpl['category']}")
        print(f"  引用数: {tmpl['usage_count']}")
        src_cases = json.loads(tmpl.get("source_case_ids", "[]"))
        print(f"  来源案件: {', '.join(src_cases) if src_cases else '无'}")
        src_artifacts = json.loads(tmpl.get("source_artifacts", "[]"))
        print(f"  来源提取物: {', '.join(src_artifacts) if src_artifacts else '无'}")
        print()
        print(tmpl.get("content", "(无内容)"))


# =============================================
# artifacts 命令
# =============================================

def cmd_artifacts(args) -> None:
    """列出某案件下所有提取物。"""
    artifacts = artifact_store.list_artifacts_by_case(args.case_id)
    if not artifacts:
        print("暂无提取物")
        return
    case = db.get_case(args.case_id)
    print(f"\n📦 提取物列表（{len(artifacts)} 个）| 案件: {case['case_name'] if case else args.case_id}")
    print("=" * 60)
    for a in artifacts:
        print(
            f"  [{a['artifact_type']}] {a['title']}"
            f"\n  ID: {a['id']} | 版本: {a['version']} | 来源: {a.get('source_ref', 'N/A')}"
        )


# =============================================
# 主入口
# =============================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="case-intelligence 提取 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # register
    p = sub.add_parser("register", help="注册新案件")
    p.add_argument("--name", help="案件名称")
    p.add_argument("--case-number", dest="case_number", help="案号")
    p.add_argument("--plaintiff", help="原告")
    p.add_argument("--defendant", help="被告")
    p.add_argument("--cause", help="案由")
    p.add_argument("--result", help="案件结果")
    p.add_argument("--source-path", dest="source_path", help="原始文件路径")
    p.add_argument("--notes", help="备注")
    p.set_defaults(func=cmd_register)

    # link
    p = sub.add_parser("link", help="关联原始材料路径")
    p.add_argument("--case-id", required=True, dest="case_id")
    p.add_argument("--path", help="原始文件路径")
    p.set_defaults(func=cmd_link)

    # extract
    p = sub.add_parser("extract", help="提取 Artifact")
    p.add_argument("--case-id", required=True, dest="case_id")
    p.add_argument("--type", help=f"提取物类型（{', '.join(db.ARTIFACT_TYPES)}）")
    p.add_argument("--title", help="提取物标题")
    p.add_argument("--source-ref", dest="source_ref", help="来源引用")
    p.add_argument("--content", help="提取物内容（Markdown）")
    p.set_defaults(func=cmd_extract)

    # promote
    p = sub.add_parser("promote", help="将 Artifact 归纳为 Template")
    p.add_argument("--artifact-id", required=True, dest="artifact_id")
    p.add_argument("--template-name", dest="template_name")
    p.add_argument("--category", choices=db.TEMPLATE_CATEGORIES)
    p.set_defaults(func=cmd_promote)

    # complete
    p = sub.add_parser("complete", help="标记案件为 extracted")
    p.add_argument("--case-id", required=True, dest="case_id")
    p.set_defaults(func=cmd_complete)

    # list
    p = sub.add_parser("list", help="列出所有案件")
    p.add_argument("--status", choices=["pending", "extracted", "archived"])
    p.set_defaults(func=cmd_list)

    # search
    p = sub.add_parser("search", help="搜索案件")
    p.add_argument("--query", required=True, help="搜索关键词")
    p.set_defaults(func=cmd_search)

    # check
    p = sub.add_parser("check", help="识别新案件是否重复")
    p.add_argument("--case-number", dest="case_number", help="案号")
    p.add_argument("--plaintiff", help="原告")
    p.add_argument("--defendant", help="被告")
    p.add_argument("--cause", help="案由")
    p.set_defaults(func=cmd_check)

    # report
    p = sub.add_parser("report", help="生成统计报告")
    p.set_defaults(func=cmd_report)

    # artifacts
    p = sub.add_parser("artifacts", help="列出案件下所有提取物")
    p.add_argument("--case-id", required=True, dest="case_id")
    p.set_defaults(func=cmd_artifacts)

    # templates
    p = sub.add_parser("templates", help="模板管理（list/search/show）")
    sub_t = p.add_subparsers(dest="templates_action", required=True)
    # templates list
    p_list = sub_t.add_parser("list", help="列出所有模板")
    p_list.add_argument("--category", choices=db.TEMPLATE_CATEGORIES, help="按分类筛选")
    p_list.set_defaults(func=cmd_templates)
    # templates search
    p_search = sub_t.add_parser("search", help="搜索模板")
    p_search.add_argument("--query", required=True, help="搜索关键词")
    p_search.add_argument("--show-content", action="store_true", dest="show_content", help="显示内容预览")
    p_search.set_defaults(func=cmd_templates)
    # templates show
    p_show = sub_t.add_parser("show", help="查看模板详情")
    p_show.add_argument("--template-id", required=True, dest="template_id")
    p_show.set_defaults(func=cmd_templates)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
