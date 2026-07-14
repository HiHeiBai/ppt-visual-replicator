# PPT Visual Replicator

[English](README.md)

一个用于 PowerPoint 视觉重绘与可编辑重建的 Agent Skill。在不改写原始内容的前提下，统一整套演示文稿的视觉风格，并输出可编辑的 `.pptx`。

## 主要能力

- 只需提供 `.pptx`，自动将原始页面渲染成 PNG。
- 可选提供风格描述，或少量全局参考风格图片。
- 默认以 PNG + OCR/视觉识别为内容依据；数字敏感型材料可启用原生文字严格保护。
- 标题、正文、卡片、表格、箭头和结构图形尽量恢复为可编辑 PowerPoint 对象。
- 软件截图、照片、复杂图表和插画可按需保留为独立图片区域。
- 自动识别完全重复页面，复用全局素材，并支持断点续跑。
- 内置 `editppt` 可编辑重建运行时。

## 速度模式

| 模式 | 处理方式 | 适用场景 |
| --- | --- | --- |
| `balanced` | 重绘封面和视觉概念页，截图型页面直接重建 | 默认推荐 |
| `fast` | 尽量减少整页生成，更多复杂区域作为图片保留 | 教程和截图较多的 PPT |
| `strict` | 每个不重复页面都重绘，并完整执行逐页素材分离 | 追求最大程度的对象级可编辑 |

## 安装

使用 Skills CLI 全局安装：

```bash
npx skills add Moxi-Lab/ppt-visual-replicator \
  --skill ppt-visual-replicator --global --yes
```

也可以手动安装：

```bash
git clone https://github.com/Moxi-Lab/ppt-visual-replicator.git
mkdir -p ~/.codex/skills
cp -R ppt-visual-replicator/skills/ppt-visual-replicator ~/.codex/skills/
```

安装后请新建一个 Codex 任务，让 Skill 列表重新加载。

## 环境要求

- Python 3.10+
- LibreOffice（`soffice` 或 `libreoffice`）
- Poppler（`pdftoppm`）
- 支持内置图片生成，并且 `editppt` 能访问图片处理后端的 Codex 环境

macOS：

```bash
brew install --cask libreoffice
brew install poppler
```

Ubuntu/Debian：

```bash
sudo apt-get install libreoffice poppler-utils
```

首次使用时，Skill 会自动安装内置的可编辑 PPT 运行时。

## 使用方法

在 Codex 中提供一个 PPTX，然后输入：

```text
使用 $ppt-visual-replicator 的 balanced 模式重绘这个 PPT，并返回可编辑的 PPTX。
```

还可以补充：

- `fast`、`balanced` 或 `strict` 速度模式
- 只处理某一页
- 风格描述
- 一张或少量全局参考风格 PNG
- 开启原生文字严格保护

## 工作流程

```text
PPTX -> 原始页面 PNG -> 页面生成计划
     -> 选择性视觉重绘 -> 可编辑对象重建
     -> 验证 -> 最终真实渲染检查 -> 可编辑 PPTX
```

完全重复的页面只处理一次。重复出现的 Logo、吉祥物、装饰元素和页面标识可以进入全局素材库，在整套 PPT 中复用。

## 开发与测试

运行测试：

```bash
python3 -m unittest discover -s tests
```

如果本机安装了 OpenAI `skill-creator` Skill，可使用其中的 `quick_validate.py` 检查 Skill 包结构。

## 开源协议

[MIT](LICENSE)
