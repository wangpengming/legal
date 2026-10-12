# UI 工具函数
import sys
import os
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import database as db
from src import scanner
from src import parser
from src import extractor
from src import importer
from src import artifact_store

def get_cases(search: str = "", page: int = 1, page_size: int = 20):
    """获取案件列表，支持搜索和分页"""
    if search:
        cases = db.search_cases(search)
    else:
        cases = db.list_cases()
    
    total = len(cases)
    start = (page - 1) * page_size
    end = start + page_size
    return cases[start:end], total

def get_case_health(case_id: str) -> dict:
    """计算案件健康度"""
    case = db.get_case(case_id)
    if not case:
        return {"health": 0, "passed": 0, "total": 6, "checks": []}
    
    checks = []
    total = 6
    passed = 0
    
    # 基本信息
    if case.get('case_number'):
        checks.append(('✅', '案号'))
        passed += 1
    else:
        checks.append(('❌', '案号'))
    
    if case.get('plaintiff'):
        checks.append(('✅', '原告'))
        passed += 1
    else:
        checks.append(('❌', '原告'))
    
    if case.get('defendant'):
        checks.append(('✅', '被告'))
        passed += 1
    else:
        checks.append(('❌', '被告'))
    
    if case.get('cause'):
        checks.append(('✅', '案由'))
        passed += 1
    else:
        checks.append(('❌', '案由'))
    
    if case.get('court'):
        checks.append(('✅', '法院'))
        passed += 1
    else:
        checks.append(('❌', '法院'))
    
    # 提取物
    artifacts = db.list_artifacts_by_case(case_id)
    if len(artifacts) > 0:
        checks.append(('✅', f'提取物({len(artifacts)}个)'))
        passed += 1
    else:
        checks.append(('❌', '提取物'))
    
    health = int((passed / total) * 100)
    return {"health": health, "passed": passed, "total": total, "checks": checks}

def scan_and_import(path: str):
    """扫描目录并导入案件"""
    path = Path(path).resolve()
    if not path.exists():
        raise ValueError(f"目录不存在: {path}")
    
    # 扫描
    result = scanner.scan_directory(path)
    
    # 解析
    parsed = parser.parse_files(result.files)
    
    # AI提取
    extracted = extractor.extract_case(parsed, result.case_name, "minimax")
    
    # 导入
    imp = importer.CaseImporter()
    result_import = imp.import_full(extracted)
    
    return result_import

def get_summary():
    """获取统计摘要"""
    return db.get_summary()

def get_cause_distribution():
    """获取案由分布"""
    conn = db._get_conn()
    rows = conn.execute("""
        SELECT cause, COUNT(*) as cnt
        FROM cases
        WHERE cause IS NOT NULL AND cause != ''
        GROUP BY cause
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchall()
    conn.close()
    return rows

def get_pending_cases(limit: int = 10):
    """获取待提取案件"""
    return db.list_cases(status="pending")[:limit]
