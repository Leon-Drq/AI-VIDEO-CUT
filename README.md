# AI-VIDEO-CUT

个人视频剪辑技能的私有归档仓库。保存可复用的剪辑方法、脚本、配置模板和必要参考说明，持续收录后续个人剪辑技能。

## 已收录技能

| 技能 | 用途 | 入口 |
| --- | --- | --- |
| `lengke-broll` | 冷科长式语义 B-roll 精剪：真实资料、产品录屏、图解、关键词、真人画中画与字幕 | [SKILL.md](skills/lengke-broll/SKILL.md) |
| `behind-person-titles` | 人物背后大字精剪：连续抠像、原始人物遮挡粗白巨字、轻量圆角字幕与连贯口播 | [SKILL.md](skills/behind-person-titles/SKILL.md) |

机器可读索引见 [catalog.json](catalog.json)。

## 使用

将所需的 `skills/<skill-name>/` 整个目录安装到本机 Codex 技能目录（通常为 `~/.codex/skills/`；设置过 `CODEX_HOME` 时使用其下 `skills/`）。已有同名技能时先比对本机和仓库的修改，保留未归档的工作。

安装后可以这样调用：

```text
用 $lengke-broll 给这段口播补充与台词对应的真实素材和图解，保留原声，输出正式 MP4。

用 $behind-person-titles 按上次背景大字的方式剪这条横版视频，保持语言连贯，让人物自然挡住大字。
```

两者可以配合：先完成对白取舍和语义配画面，再用人物背后巨字及字幕强化关键段落。已有视频工程继续使用，不强制迁移渲染技术栈。

`behind-person-titles` 包含 `matte` 和 `render` 两个可运行命令。模型、字体、FFmpeg 与运行环境由实际项目提供，具体条件见 [渲染说明](skills/behind-person-titles/references/renderer.md)。技能中列出的本地案例路径用于原机器定位，不是其他机器运行的必需文件。

## 后续维护

新增技能放入 `skills/<skill-name>/`，同时更新 README 和 catalog.json。维护规则见 [AGENTS.md](AGENTS.md)。

检查仓库：

```text
python tools/check_repository.py
```

技能更新后还需做对应的实际行为检查，并同步本机安装版本。仓库检查仅验证目录、索引、引用和代码语法，不替代成片视觉与听感检查。

本仓库保持私有。每期原片、录音、成片、模型权重、运行缓存和凭据留在项目或环境中；可复用的轻量模板与固定配套资产按实际需要收录。原点社区、原点学堂、原点夜校相关技能继续归档到其独立的社区技能仓库。
