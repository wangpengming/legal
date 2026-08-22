# SPEC-enhancements-v2.2 — 拍照扫描集成到新建案件

> 对应 backlog：2026-08-22「拍照扫描集成到新建案件（增强）」
> 前置：v2.1（七项体验增强）已归档，本规格在 dev 分支增量演进。

## 1. 背景与动机

法务日常工作流的真实场景：**收到对方起诉状 → 拍照/扫描 → 新建案件**。
v2.0 已有独立「拍照扫描」页（/scan），但两个断裂点导致几乎不可用：

1. **入口错位**：扫描页与新建案件表单分离，识别后仅提示"前往案件页新建"（sessionStorage 中间态），案件页实际未消费该数据，链路是断的。
2. **角色选项缺失**：起诉状场景下我方诉讼地位不限于 原告/被告/第三人。

## 2. 方案

### 2.1 入口收敛（前端）

- 移除侧边栏「拍照扫描」导航与 `/scan` 路由，删除 `pages/ScanPage.tsx`。
- 案件页（CasesPage）新建按钮旁并列「扫描起诉状」按钮（btn-outline + Camera 图标）。
- 点击弹出 `ScanModal`（components/ScanModal.tsx，复用 modal-overlay/modal-panel 体系），内含：
  - 文件上传区（JPG/PNG/PDF ≤ 20MB）
  - URL 识别输入
  - 识别结果字段表（案号/法院/案由/原告/被告/开庭时间/立案日期/标的金额，值非空才展示）
  - 「填入案件表单」按钮 + OCR 原始文本折叠区

### 2.2 字段映射（前端 lib/scan.ts 纯函数）

| OCR 字段 | 表单字段 | 处理 |
|---------|---------|------|
| 案号 | case_number | 原样 |
| 法院 | court | 原样 |
| 案由 | cause | extractCause 提取「XX纠纷」词干（去 本案/本案系/系/属/因/为 前缀）→ 去「纠纷」后缀 |
| 开庭时间 | hearing_date | normalizeHearingDate：`2026年9月15日`/`2026-9-15` → `2026-09-15` |
| 被告 → 对方当事人 | opposing_party | 有被告取被告，仅原告取原告；名称内 OCR 空格噪音清洗 |
| 我方角色 | our_role | 有被告 → 原告（我方起诉）；仅原告 → 被告（对方起诉我方） |

### 2.3 我方角色选项

下拉扩展为四个选项：**原告 / 被告 / 第三人 / 法院**（法院角色为业务新增，如法院作为诉中送达对象的场景；后端 our_role 为自由字符串，无需枚举约束）。

### 2.4 OCR 后端增强（scan_service.py）

- 案由清洗：`re.sub(r'^(本案系|本案|系|属|因|为)', '', cause)`，防前缀污染 → 表单案由。
- 语言包：`_detect_lang()` 自动探测 chi_sim，缺失时回退 eng（本机已补 chi_sim.traineddata = tessdata_fast）。

## 3. 验收（已勾选 = 已通过）

- [x] 案件页新建按钮旁有「扫描起诉状」按钮，打开扫描面板（上传 + URL 两方式）
- [x] OCR 识别结果显示字段表（7 字段）
- [x] 「填入表单」映射填充 + 自动展开表单
- [x] 对方当事人智能推断（被告优先 / 仅原告时我方=被告）
- [x] 我方角色下拉：原告 / 被告 / 第三人 / 法院
- [x] 移除独立「拍照扫描」导航与路由
- [x] 后端 pytest 40 passed（+4 scan_service 用例 +1 our_role=法院 用例）；前端 tsc 零错误 + vite build 成功；浏览器 E2E 全链路（上传宋体合成起诉状 → 识别 7 字段 → 填入 → 保存落库）通过

## 4. 验证证据

- `backend/tests/test_scan_service.py`：extract_fields 全文档/半角冒号/案由前缀清洗
- `backend/tests/test_api.py::test_case_our_role_court`：our_role=「法院」创建 + 回读
- E2E 截图：`docs/qoder-raw/v22-verify/{01-scan-modal-result,02-form-filled,03-case-created}.png`
- 测试图片生成脚本：PIL + Songti.ttc 合成起诉状（OCR 对宋体识别率最高，识别结果 7/7 字段命中）

## 5. 备注

- Vitest 缺失，前端遵循 v2.1 既定调整：纯函数断言（node + assert 逻辑快照）+ tsc + 浏览器 E2E。
- OCR 引擎为 Tesseract 5.5.2（Homebrew）；chi_sim.traineddata 来自 tessdata_fast（jsdelivr 镜像），识别中文印刷体（宋体）效果佳；手写体/低清照片可能有个别字段漏识别，可在 Modal 内二次手工修改后保存。