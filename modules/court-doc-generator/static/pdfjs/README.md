# PDF.js 库目录

> 存放 Mozilla PDF.js 浏览器端 PDF 渲染库，用于"浏览器内 PDF 预览"功能。
> 详见 [static/README.md](../README.md) §4。

## 必放文件

| 文件名 | 大小 | 来源 |
|--------|------|------|
| `pdf.min.js` | ~320 KB | [CDN](https://cdnjs.cloudflare.com/ajax/libs/pdf.js/) |
| `pdf.worker.min.js` | ~1 MB | 与主库同版本 |

## 快速下载

```bash
VERSION="4.0.379"

curl -L -o pdf.min.js \
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${VERSION}/pdf.min.js"

curl -L -o pdf.worker.min.js \
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${VERSION}/pdf.worker.min.js"
```

## 当前状态

```
pdfjs/
├── pdf.min.js         ← ⚠️ 待下载
└── pdf.worker.min.js  ← ⚠️ 待下载
```

> ⚠️ 主库与 worker **必须严格同版本**，否则 PDF.js 报 `Setting up fake worker` 警告，性能下降。