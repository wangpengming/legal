#!/usr/bin/env python3
"""
批量入库脚本
将99个历史案例批量导入 case_registry.db
"""
import sys
import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime

# 数据库路径
DB_PATH = Path(__file__).parent.parent / "data" / "case_registry.db"

# 审查结果文件
REVIEW_FILE = Path(__file__).parent / "review_results_with_ocr.json"

def get_db_connection():
    """获取数据库连接"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn):
    """初始化数据库表"""
    cursor = conn.cursor()
    
    # 检查并添加缺失的列
    cursor.execute("PRAGMA table_info(cases)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'year' not in columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN year INTEGER")
    if 'quality' not in columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN quality TEXT")
    if 'court' not in columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN court TEXT")
    
    conn.commit()

def generate_case_name(row: dict) -> str:
    """生成案件名称"""
    plaintiff = row.get("原告", "")
    defendant = row.get("被告", "")
    cause = row.get("案由", "纠纷")
    
    if plaintiff and defendant:
        return f"{plaintiff}诉{defendant}{cause}"
    elif plaintiff:
        return f"{plaintiff}案件"
    else:
        return row.get("目录名", "未知案件")[:50]

def import_case(conn, row: dict) -> str:
    """导入单个案例"""
    cursor = conn.cursor()
    
    # 检查案号是否已存在
    case_number = row.get("案号", "")
    if case_number:
        cursor.execute("SELECT id FROM cases WHERE case_number = ?", (case_number,))
        existing = cursor.fetchone()
        if existing:
            print(f"  ⚠️ 案号已存在: {case_number}")
            return existing[0]
    
    # 生成 UUID
    case_id = str(uuid.uuid4())
    
    # 生成案件名称
    case_name = generate_case_name(row)
    
    # 准备数据
    now = datetime.now().isoformat()
    
    # 提取年份
    year = row.get("年度")
    if year:
        try:
            year = int(year)
        except:
            year = None
    
    # 字段列表
    fields = [
        "id", "case_number", "case_name", "plaintiff", "defendant", "cause", "court",
        "status", "source_path", "created_at", "entry_method", "year", "quality",
        "notes", "extracted_at"
    ]
    
    # 值列表
    values = [
        case_id,
        case_number or None,
        case_name,
        row.get("原告") or None,
        row.get("被告") or None,
        row.get("案由") or None,
        row.get("法院") or None,
        "extracted",
        row.get("目录名"),
        now,
        "batch_import",
        year,
        row.get("质量"),
        json.dumps(row.get("问题", []), ensure_ascii=False) if row.get("问题") else None,
        now
    ]
    
    # 插入数据
    placeholders = ", ".join(["?"] * len(fields))
    sql = f"INSERT INTO cases ({', '.join(fields)}) VALUES ({placeholders})"
    cursor.execute(sql, values)
    
    return case_id

def main():
    """主函数"""
    print("=" * 60)
    print("历史案例批量入库")
    print("=" * 60)
    
    # 读取审查结果
    with open(REVIEW_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)
    
    print(f"\n共 {len(results)} 个目录")
    
    # 连接数据库
    conn = get_db_connection()
    init_db(conn)
    
    print(f"\n📦 数据库: {DB_PATH}")
    
    # 统计
    total_imported = 0
    total_skipped = 0
    by_year = {}
    by_quality = {"A": 0, "B": 0, "C": 0, "D": 0}
    by_status = {"正式案件": 0, "非案件目录": 0}
    
    # 按年度分组导入
    for row in results:
        is_case = row.get("是否案件") == "是"
        by_status["正式案件" if is_case else "非案件目录"] += 1
        
        if not is_case:
            print(f"  ⏭ 跳过非案件目录: {row['目录名'][:40]}...")
            total_skipped += 1
            continue
        
        year = row.get("年度", "未知")
        if year not in by_year:
            by_year[year] = {"imported": 0, "skipped": 0}
        
        quality = row.get("质量", "C")
        by_quality[quality] += 1
        
        try:
            case_id = import_case(conn, row)
            by_year[year]["imported"] += 1
            total_imported += 1
            
            case_num = row.get("案号", "无案号")[:30] if row.get("案号") else "无案号"
            print(f"  ✅ [{row['年度']}] {case_num}")
            
        except Exception as e:
            by_year[year]["skipped"] += 1
            total_skipped += 1
            print(f"  ❌ 导入失败: {row['目录名'][:40]}... ({e})")
    
    conn.commit()
    
    # 统计结果
    print("\n" + "=" * 60)
    print("入库完成")
    print("=" * 60)
    print(f"\n📊 统计:")
    print(f"  总目录: {len(results)} 个")
    print(f"  正式案件: {by_status['正式案件']} 个")
    print(f"  非案件目录: {by_status['非案件目录']} 个")
    print(f"  成功入库: {total_imported} 个")
    print(f"  跳过/失败: {total_skipped} 个")
    
    print(f"\n📅 年度分布:")
    for year in sorted(by_year.keys()):
        data = by_year[year]
        print(f"  {year}: {data['imported']} 个")
    
    print(f"\n🏷️ 质量分布:")
    for quality in ["A", "B", "C", "D"]:
        print(f"  {quality}级: {by_quality[quality]} 个")
    
    # 验证入库
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cases")
    db_count = cursor.fetchone()[0]
    print(f"\n✅ 数据库验证: cases 表共 {db_count} 条记录")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("💾 入库完成！数据已保存到 case_registry.db")
    print("=" * 60)

if __name__ == "__main__":
    main()
