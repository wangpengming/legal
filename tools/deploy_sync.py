#!/usr/bin/env python3
# =============================================
# thunderbox 部署分支同步（方案 A：一仓多分支快照）
#
# 从 monorepo 的 modules/<name>/ 生成「根 = 模块」的部署快照分支，
# 推送到 GitHub（或经 Gitee）。分支只承载模块内容，永不手改。
#
# 安全：默认 dry-run（只打印清单与将执行的命令）；必须显式 --push 才真正推送。
#       push 受 AGENTS.md §10.2 红线约束，需用户逐次授权。
#
# 用法：
#   python3 tools/deploy_sync.py --module case-intelligence                 # dry-run
#   python3 tools/deploy_sync.py --module case-intelligence --push          # 推送
#   python3 tools/deploy_sync.py --module case-intelligence --push --via-gitee
#   python3 tools/deploy_sync.py --all --dry-run
# =============================================
import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "shared" / "config" / "deploy.yaml"


def run(args, cwd=None, check=True):
    return subprocess.run(
        args, cwd=cwd or ROOT, check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def load_registry():
    if not REGISTRY.exists():
        sys.exit(f"注册表不存在: {REGISTRY}")
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def is_excluded(rel, patterns):
    """rel 为模块内相对路径；目录模式以 / 结尾，其余按 glob 匹配。"""
    for p in patterns:
        if p.endswith("/"):
            if rel.startswith(p):
                return True
        elif fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(os.path.basename(rel), p):
            return True
    return False


def module_files(module):
    """模块内 tracked + untracked(非忽略) 文件（相对仓库根的路径）。

    用 -z 输出 NUL 分隔的原始路径：否则 git 会对中文名加引号转义
    （core.quotePath），导致 os.path.exists 判定失败、文件被静默丢弃。
    """
    rel_dir = f"modules/{module}"
    out = run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", rel_dir])
    return [p for p in out.stdout.split("\0") if p.strip()]


def build_snapshot(module, cfg):
    """把模块内容拷进临时目录，返回 (临时目录, 入选文件列表, 被排除文件列表)。"""
    patterns = cfg.get("exclude", []) or []
    picked, dropped = [], []
    for repo_rel in module_files(module):
        inside = os.path.relpath(repo_rel, f"modules/{module}")
        if is_excluded(inside, patterns):
            dropped.append(inside)
            continue
        src = ROOT / repo_rel
        if not src.exists():  # tracked-but-deleted
            continue
        picked.append((inside, src))

    tmp = Path(tempfile.mkdtemp(prefix=f"deploy-{module}-"))
    for inside, src in picked:
        dst = tmp / inside
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return tmp, picked, dropped


def print_manifest(module, cfg, tmp, picked, dropped):
    branch = cfg["branch"]
    print(f"\n{'=' * 62}")
    print(f"模块: {module}   分支: {branch}")
    print(f"快照目录: {tmp}")
    print(f"{'=' * 62}")

    # 顶层分布
    buckets = {}
    total = 0
    for inside, src in picked:
        top = inside.split("/")[0]
        buckets[top] = buckets.get(top, 0) + 1
        total += src.stat().st_size
    print(f"入选 {len(picked)} 个文件 · {total / 1024:.0f} KB")
    for top in sorted(buckets):
        mark = ""
        if top in ("data", "prompts", "output_templates", "templates_extracted"):
            mark = "  ← 关键（数据/模板/提示词）"
        print(f"  {top:<22} {buckets[top]:>5} 文件{mark}")

    if dropped:
        print(f"\n排除 {len(dropped)} 个文件（模式: {', '.join(cfg.get('exclude', []))}）")

    # 显式断言关键目录
    for key in ("data", "prompts", "output_templates", "templates_extracted"):
        ok = key in buckets
        print(f"  [{'✓' if ok else '✗'}] {key}/ {'已包含' if ok else '缺失'}")


def commit_snapshot(tmp, module, sha):
    msg = f"deploy({module}): snapshot from monorepo {sha} @ {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}"
    run(["git", "init", "-q"], cwd=tmp)
    run(["git", "add", "-A"], cwd=tmp)
    run(["git", "-c", "user.name=deploy-sync", "-c", "user.email=deploy-sync@local",
         "commit", "-q", "-m", msg], cwd=tmp)
    return msg


def push_snapshot(tmp, cfg, platform, via_gitee):
    remote = "origin" if via_gitee else platform.get("git_remote", "github")
    branch = cfg["branch"]
    url = run(["git", "remote", "get-url", remote], check=False)
    if url.returncode != 0:
        print(f"\n⚠️  本地无 remote '{remote}'。先执行：")
        print(f"    git remote add {remote} {platform.get('git_push_url')}")
        return False
    print(f"\n推送 → {remote} ({url.stdout.strip()})  分支 {branch}")
    out = run(["git", "push", "--force", remote, f"HEAD:refs/heads/{branch}"], cwd=tmp, check=False)
    print(out.stdout.strip() or "(无输出)")
    return out.returncode == 0


def sync_one(module, registry, do_push, via_gitee):
    platform = registry.get("platform", {})
    cfg = registry.get("allocations", {}).get(module)
    if not cfg:
        sys.exit(f"注册表无模块: {module}")
    if not cfg.get("enabled", False):
        sys.exit(f"模块 {module} 未启用（deploy.yaml enabled=false）")

    sha = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    tmp, picked, dropped = build_snapshot(module, cfg)
    try:
        print_manifest(module, cfg, tmp, picked, dropped)
        commit_snapshot(tmp, module, sha)
        if do_push:
            ok = push_snapshot(tmp, cfg, platform, via_gitee)
            if ok:
                print(f"\n✅ 已推送 {cfg['branch']}（monorepo {sha}）")
        else:
            remote = platform.get("git_remote", "github")
            print(f"\n[dry-run] 未推送。将执行：")
            print(f"    git push --force {remote} HEAD:refs/heads/{cfg['branch']}")
            print(f"    加 --push 才真正推送（守 §10.2 红线）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="thunderbox 部署分支同步（方案 A）")
    ap.add_argument("--module", help="模块名（modules/<name>）")
    ap.add_argument("--all", action="store_true", help="同步所有 enabled 模块")
    ap.add_argument("--push", action="store_true", help="真正推送（默认 dry-run）")
    ap.add_argument("--dry-run", action="store_true", help="仅打印（默认行为）")
    ap.add_argument("--via-gitee", action="store_true", help="推送到 Gitee(origin)，交由服务端镜像同步到 GitHub")
    args = ap.parse_args()

    registry = load_registry()
    allocations = registry.get("allocations", {})

    if args.all:
        targets = [m for m, c in allocations.items() if c.get("enabled")]
    elif args.module:
        targets = [args.module]
    else:
        ap.error("需指定 --module <name> 或 --all")

    if args.push and args.dry_run:
        ap.error("--push 与 --dry-run 互斥")

    for module in targets:
        sync_one(module, registry, do_push=args.push and not args.dry_run, via_gitee=args.via_gitee)


if __name__ == "__main__":
    main()