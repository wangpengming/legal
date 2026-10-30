# 模板管理页
import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.auth import require_auth
from ui.nav import render_sidebar
from src import case_service as svc
from src import extractor
from src import importer

require_auth()

st.set_page_config(
    page_title="案例分析 - 模板管理",
    page_icon="🧩",
    layout="wide"
)

render_sidebar()

st.title("🧩 模板管理")

tab_list, tab_new, tab_import = st.tabs(["📋 模板列表", "➕ 新建模板", "📥 导入 JSON"])

# ========== 列表 / 搜索 / 编辑 / 删除 ==========
with tab_list:
    fcol1, fcol2 = st.columns([2, 1])
    with fcol1:
        query = st.text_input("🔍 搜索模板", placeholder="按名称/分类/内容搜索...")
    with fcol2:
        cat_filter = st.selectbox("分类筛选", options=["全部"] + svc.TEMPLATE_CATEGORIES)

    if query:
        templates = svc.search_templates(query)
    elif cat_filter != "全部":
        templates = svc.list_templates(cat_filter)
    else:
        templates = svc.list_templates()

    st.caption(f"共 **{len(templates)}** 个模板")

    if not templates:
        st.info("暂无模板")
    else:
        for t in templates:
            with st.expander(f"📄 {t['name']}（{t.get('category')}）｜引用 {t.get('usage_count', 0)} 次"):
                st.markdown(t.get('content') or "_（无内容）_")

                with st.form(f"edit_tpl_{t['id']}"):
                    e_name = st.text_input("名称", value=t['name'])
                    e_cat = st.selectbox(
                        "分类", options=svc.TEMPLATE_CATEGORIES,
                        index=svc.TEMPLATE_CATEGORIES.index(t['category'])
                        if t.get('category') in svc.TEMPLATE_CATEGORIES else 0,
                    )
                    e_content = st.text_area("内容（Markdown）", value=t.get('content') or "", height=160)
                    if st.form_submit_button("💾 保存修改"):
                        svc.update_template(
                            t['id'], name=e_name.strip() or t['name'],
                            category=e_cat, content=e_content,
                        )
                        st.success("✅ 已保存")
                        st.rerun()

                dcol1, dcol2 = st.columns([3, 1])
                with dcol1:
                    st.caption(f"ID: {t['id']}")
                with dcol2:
                    if st.button("🗑️ 删除", key=f"del_tpl_{t['id']}"):
                        svc.delete_template(t['id'])
                        st.success("已删除")
                        st.rerun()

# ========== 新建 ==========
with tab_new:
    with st.form("new_template_form", clear_on_submit=True):
        n_name = st.text_input("模板名称 *")
        n_cat = st.selectbox("分类", options=svc.TEMPLATE_CATEGORIES)
        n_content = st.text_area("内容（Markdown）", height=220)
        if st.form_submit_button("✅ 创建模板", type="primary"):
            if not n_name.strip():
                st.error("模板名称必填")
            else:
                svc.create_template(
                    name=n_name.strip(), content=n_content, category=n_cat,
                )
                st.success(f"✅ 已创建模板：{n_name.strip()}")

# ========== 导入 JSON ==========
with tab_import:
    st.caption("从 JSON 文件增量导入案件（案号已存在则跳过）。支持单案件对象或案件数组。")
    uploaded = st.file_uploader("选择 JSON 文件", type=["json"])
    if uploaded is not None and st.button("📥 导入", type="primary"):
        try:
            data = json.loads(uploaded.getvalue().decode("utf-8"))
            cases = data if isinstance(data, list) else [data]
            success = skipped = 0
            errors = []
            for case_data in cases:
                extracted = extractor.extracted_from_dict(case_data)
                if extracted.case_number:
                    if svc.resolve_case(extracted.case_number):
                        skipped += 1
                        continue
                try:
                    importer.CaseImporter().import_full(extracted, generation_method="import-json")
                    success += 1
                except Exception as e:
                    errors.append(f"{case_data.get('case_name')}: {e}")
            st.success(f"导入完成：成功 {success}，跳过 {skipped}，失败 {len(errors)}")
            for e in errors:
                st.warning(e)
        except json.JSONDecodeError as e:
            st.error(f"JSON 解析失败：{e}")