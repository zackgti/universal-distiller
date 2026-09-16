# Universal Distiller

[English](README.en.md)

把资料变成**能回到原文检查的研究结论**。

一个本地运行的 Python 资料收集与证据整理工具：保存网页或文本、记录出处、
校验逐条引用、保留冲突，导出可离线阅读的 HTML 和 Markdown 报告。
不需要 API Key，没有运行时第三方依赖。当前版本：0.1.0（实验版本）。

## 五分钟体验

需要 Python 3.10 或更新版本。在项目目录打开终端：

```console
python -m pip install .
python examples/demo.py
```

打开 `workspace/demo/projects/示例-图书馆开放时间/report.html`。
示例使用两份**原创虚构资料**，演示闭馆时间冲突的保留和引用；不是实际研究结果。
再次运行请指定新的目录，如 `python examples/demo.py --root workspace/demo2`。

不安装也可以运行示例和测试：

```console
python -m unittest discover -s tests -v
```

## 做一次自己的研究

```console
ud init --root workspace/my-research --title my-topic --goal "我需要回答的问题"
ud collect --project workspace/my-research/projects/my-topic --url https://example.com --publisher "来源机构"
ud collect --project workspace/my-research/projects/my-topic --file ./notes.txt --title "访谈记录"
```

每次采集输出来源 ID（`s-...`）、原始字节、标准化文本、采集时间和 SHA-256。
相同来源、相同内容不会重复新增；不同来源的相同内容共享存储但保留出处。
更新网页内容会新增记录，保留旧版本。发布日期未知时留空，不拿采集时间冒充。

来源默认 `unknown`。人工确认来源性质后，可在首次采集指定
`--tier primary`（一手）、`authoritative`、`reliable`、`context` 或 `unknown`。
`--group` 表示独立原始来源：同一通讯稿的多个转载必须使用同一组。
`--published-at 2026-09-01` 记录已知发布日期。
重复采集不会覆盖已有人工标注；需要修订时先 snapshot，再编辑来源 JSONL。

### 整理结论

阅读 `sources/normalized/` 内的文本，创建 `claim.json`。
将下例中的 `s-实际ID` 替换为 collect 返回的 ID，并逐字复制相关原文：

```json
{
  "id": "c1",
  "text": "研究者根据原文整理的结论",
  "type": "fact",
  "status": "single-source",
  "confidence": "medium",
  "importance": 5,
  "relevance": 5,
  "included": true,
  "evidence": ["s-实际ID"],
  "quotes": {"s-实际ID": "保存在标准化文本中的原文片段"}
}
```

```console
ud claim --project workspace/my-research/projects/my-topic --file claim.json
ud validate --project workspace/my-research/projects/my-topic
ud render --project workspace/my-research/projects/my-topic
```

可编辑项目的 `analysis/result.json` 填写摘要、建议和不确定性。
摘要属于研究者撰写内容；工具不会自动判断它是否被证据支持。
HTML 与 Markdown 的核心发现都会带来源 ID、逐条摘录及相反证据。

## 证据规则

- `type`：`fact` / `viewpoint` / `inference` / `forecast`。
- `status`：`supported` / `single-source` / `conflicted` / `unsupported`。
- 一个 `supported` 事实需要一手来源，或两个明确标注独立组的可靠来源。
- `unsupported` 结论不能进入报告；`conflicted` 结论进入报告时必须提供
  `opposing_evidence`，并为双方提供 `quotes`。
- 新采集来源的引用必须出现在保存的正文中；源文件被修改时校验失败。
- **校验通过仅说明数据结构、引用与规则一致，不证明事实为真。** 来源等级、
  来源独立性、语义是否支持结论及信息时效仍需研究者判断。
- 网络失败写入 `evidence/gaps.jsonl`，在报告中显示；历史失败不会因之后成功而消失。

## 更新与历史

```console
ud snapshot --project workspace/my-research/projects/my-topic
```

先 snapshot，再采集或修改结论。保存命令输出的快照路径，更新后执行：

```console
ud diff --project workspace/my-research/projects/my-topic --snapshot <快照路径>
```

快照保存证据记录、分析与报告；原始资料按哈希保存在项目中，不做重复复制。
迁移时请复制整个项目及其工作根目录标记。diff 比较文件哈希，不做语义判断。

## 与 AI 助手一起用

见 [研究工作流](docs/WORKFLOW.md)。让助手负责检索发现与归纳，CLI 负责落盘和
确定性检查。当前版本没有内置搜索引擎或 LLM，也不会自动生成事实、评估置信度。

## 边界

- 采集普通 HTTP(S) 文本网页和 UTF-8 本地 txt/md/html/csv/json，单份最多 5 MiB。
- HTML 提取器保留可读文字，移除脚本和样式；复杂导航噪声可能仍存在。
- 不支持登录页面、JavaScript 渲染、PDF/OCR、自动搜索或绕过付费墙。
- 网络采集会访问用户指定的地址和重定向，可能使用系统代理。仅在受信任的
  本地研究会话中使用，不要将其直接暴露为接收任意 URL 的服务器接口。
- URL、文件路径及全文保存在本地档案；不要将含令牌的 URL 当作来源。
- 单进程写入；不要让多个助手同时修改同一研究项目。
- 报告本身可离线阅读，原站链接需要网络。引用的网页内容不因采集而获得再分发许可。

## 开发与发布

```console
python -m pip install -e .
python -m unittest discover -s tests -v
```

包含 Windows/Linux × Python 3.10/3.12/3.13 的 CI 配置，需推送后才会实际运行。
详情见 [开发贡献](CONTRIBUTING.md)、[代码来源](docs/PROVENANCE.md)、
[发布清单](docs/RELEASE.md)。代码采用 MIT 许可。收集的第三方资料不属于该许可范围。

本项目与 OpenAI 无隶属或赞助关系，尚无公开用户量或维护历史方面的主张。
