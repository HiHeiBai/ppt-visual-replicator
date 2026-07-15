# PPT Visual Replicator

[English](README.md)

把已有 PPT 重做成视觉统一、真正可编辑的 `.pptx`，同时不改变它表达的任何内容。

`PPTX → 干净的原始页 → imagegen 重绘 → 逐页审核 → 可编辑 PPTX`

这是一个内容保护型 Codex Skill。原始 PPT 页面是文字、数据、图表、引用、Logo 和页序的唯一依据；用户提供的参考图只用于定义视觉风格。

## 最终交付什么

- 一套视觉更统一、更有完成度的演示文稿。
- 最终 `.pptx` 中的原生可编辑文本和结构对象。
- 截图、照片、图表、复杂插画等在拆解不会带来有效编辑价值时，保留为独立图片区域。
- 与原始页、生成图 hash 绑定的逐页审核记录与交付 gate：未审核、内容被替换、或整页截图式的结果都不能通过。

它不是“把整页截图贴进 PPT，再盖一层文字”。

## 内容与风格严格分离

| 只能来自原始 PPT | 可以来自用户提供的风格参考图 |
| --- | --- |
| 文案、数字、表格、图表、引用、Logo、阅读顺序 | 色彩、字体气质、留白、边框、阴影、装饰语言 |

医疗、金融、法律、科研或数字密集型材料可开启严格文本保护：原始原生文字与关键数值会作为重建的权威依据。

## 安装

```bash
npx skills add Moxi-Lab/ppt-visual-replicator \
  --skill ppt-visual-replicator --global --yes
```

也可以 clone 本仓库后，将 `skills/ppt-visual-replicator` 拷贝到 `~/.codex/skills/`。完成后新建一个 Codex 任务，让 Skill 列表刷新。

## 怎么使用

向 Codex 提供一个 `.pptx`，然后直接说：

```text
使用 $ppt-visual-replicator 将这套 PPT 重做为可编辑 PPTX。
保留原始页面的所有结论、数字、图表、引用、Logo 和页序。
```

还可以补充：

- 只处理某一页。
- 一句简短的风格描述。
- 一张或多张用户提供的参考风格 PNG。
- 开启严格文本保护。

参考图不能提供事实、文案、图表、Logo 或布局内容。

## 一次运行会发生什么

1. 渲染所需页面，并验证原始 PNG 是否完整可用。
2. 用内置 imagegen 重绘需要生成的页面。
3. 每页生成后立刻人工比对，并写入与图像 hash 绑定的审核 checkpoint。
4. 先通过生成交付 gate，再进入可编辑重建。
5. 在本地把已通过审核的页面重建为可编辑 PowerPoint 对象。
6. 校验可编辑性，再渲染最终 PPT 做视觉 QA。

每页都有独立状态和审核证据。运行被中断后，从已记录的 checkpoint 接续；已经审核通过的页面不应重新生成。

## 本地依赖

- Python 3.10+
- LibreOffice（`soffice` 或 `libreoffice`）
- Poppler（`pdftoppm`）
- 支持内置图片生成的 Codex 环境

macOS：

```bash
brew install --cask libreoffice
brew install poppler
```

Ubuntu/Debian：

```bash
sudo apt-get install libreoffice poppler-utils
```

首次需要时会自动安装内置 `editppt` 运行时；复用前会核验它确实加载的是当前 skill 的源码。

## 开发校验

```bash
python3 -m unittest discover -s tests -v
python3 /path/to/skill-creator/scripts/quick_validate.py skills/ppt-visual-replicator
```

## 开源协议

[MIT](LICENSE)
