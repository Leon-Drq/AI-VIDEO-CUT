# AI-VIDEO-CUT

个人视频剪辑技能归档仓库，收录可复用的剪辑方法、脚本、模板和参考说明。

## 已收录技能

| 技能 | 用途 | 入口 |
| --- | --- | --- |
| **SoloLoopCut** · `$sololoopcut` | 活动、社群与访谈精剪：橙白大字、衬线身份字、章节进度、原版 Logo、现场原声与原创配乐，含 HDR 转色与单次视频有损输出 | [SKILL.md](skills/sololoopcut/SKILL.md) |
| **DrqCut** · `$drqcut` | 从口播原片到正式 MP4 和字幕。人物背后白色巨字、精简小字、重点词推近与概念动画；纸张照片分次入场，真实证据从全貌到细节，配纯黑底和姜黄高亮 | [SKILL.md](skills/drqcut/SKILL.md) |
| `qshu-video-edit` · Q叔口播视频剪辑 | 基于已确认的冷科长式方法：前3秒案例与真人同屏、无底框粗白大字和人物遮挡、大幅完整案例、姜黄色高亮、自然背景，保留原声与已确认速度 | [SKILL.md](skills/qshu-video-edit/SKILL.md) |
| `lengke-broll` | 冷科长式语义 B-roll 精剪：拆解参考，按口播推进对象、证据和关系；强化前3秒、真实案例及分层动效，保留已确认风格、真人原声与字幕 | [SKILL.md](skills/lengke-broll/SKILL.md) |
| `behind-person-titles` | 人物背后大字精剪：连续抠像、原始人物遮挡粗白巨字、轻量圆角字幕与连贯口播 | [SKILL.md](skills/behind-person-titles/SKILL.md) |

机器可读索引见 [catalog.json](catalog.json)。

DrqCut 的[人后大字与信息减法](skills/drqcut/references/presenter-typography.md)规定真人标题默认提炼为背景关键词，通过同帧连续遮罩让头发、手势自然挡住文字，并清理重复副标签。[概念动画](skills/drqcut/references/evidence-motion.md#概念动画按词落点)用可识别对象的状态变化解释台词，例如工牌退场与失业状态翻面；动作按重点词落定，完整口播字幕保持清楚。

## 使用

将所需的 `skills/<skill-name>/` 整个目录安装到本机 Codex 技能目录（通常为 `~/.codex/skills/`；设置过 `CODEX_HOME` 时使用其下 `skills/`）。已有同名技能时先比对本机和仓库的修改，保留未归档的工作。

安装后可以这样调用：

```text
用 $drqcut 精剪这条口播，语速调到 1.1 倍。开头给真人和真实案例，讲到证据时放大关键原句，直接交付 MP4 和字幕。

用 $qshu-video-edit 精剪这段口播，竖版原速，案例完整放大，使用姜黄色高亮和无底框粗白大字，背景不要虚化或打码，直接交付 MP4。

用 $lengke-broll 给这段口播补充与台词对应的真实素材和图解，保留原声，输出正式 MP4。

用 $behind-person-titles 按上次背景大字的方式剪这条横版视频，保持语言连贯，让人物自然挡住大字。
```

`qshu-video-edit` 是独立可安装的「Q叔口播视频剪辑」，在冷科长式方法上整理用户已经确认的偏好；调用时不需要同时安装或叠加旧技能。原有两个技能继续保留。已有视频工程继续使用，不强制迁移渲染技术栈。

Q叔版的重点是[完整取景与大画面](skills/qshu-video-edit/references/full-frame-materials.md)：整体案例等比包含，横版教学居中保留横版，检查来源缩放和模板退场，避免图表、幻灯片与海报只剩半张。自制高亮改为姜黄，真人背景不新增虚化或打码。新片默认原速，同一视频修订保留已确认速度；仅口播加速时不连带加速案例动画。默认配色、标题与全流程见其 [SKILL.md](skills/qshu-video-edit/SKILL.md)。

`lengke-broll` 与 `behind-person-titles` 也可按需配合：先完成对白取舍和语义配画面，再用人物背后巨字及字幕强化关键段落。

`lengke-broll` 的[真实素材与分层动效指南](skills/lengke-broll/references/image-led-motion.md)说明如何用头像替代冗余姓名大字、用照片表达单人到群体，以及在金融语境中制作纸币展开与飘落。保留必要数字、单位和字幕，并检查运动全程的遮挡；具体素材与动画按台词选择。

新增的[参考拆解与语义分镜](skills/lengke-broll/references/semantic-shot-design.md)把“全屏了仍然粗糙”的修正落实到分镜：实际查看参考并记录范围，同一对象连续移位以引入新证据，图表只设一个主焦点，文件从整体推进到真实条款；按口播补齐长段中应呈现的对象。修订版按同一句口播比较，并检查运动极值、图文避让和手机阅读。素材覆盖率与自动场景检测只辅助定位问题。

升级后的默认制作与验收见[前3秒与素材精修](skills/lengke-broll/references/hook-and-polish.md)：首帧建立对象、前三秒形成看点与正文衔接；从来源角标、地址栏、截图/录屏到收尾清除可见网址，完整出处保存在项目文件；放大真实案例细节，检查叠层、阴影和图文避让。先保留项目已确认的配色、字体与真人背景，纯黑底、白字和姜黄高亮不被其他默认配色覆盖；未确定风格时可从暖白与深色展示场景起步。真人背景补光与素材展示底色分开处理。

真人主标题默认采用**白色粗重无衬线大字＋人物自然遮挡**，去掉黑框、圆角底板与标题横条。通过连续人物遮罩将原始人物放回文字前方，检查头发、帽沿、手势边缘与遮挡后的可读性；详细排字、分层和验收见[视觉规范](skills/lengke-broll/references/visual-system.md)。这一默认用于需要标题的真人镜头，素材展示与对白字幕保留各自的排版。

`behind-person-titles` 包含 `matte` 和 `render` 两个可运行命令。模型、字体、FFmpeg 与运行环境由实际项目提供，具体条件见 [渲染说明](skills/behind-person-titles/references/renderer.md)。技能中列出的本地案例路径用于原机器定位，不是其他机器运行的必需文件。


## SoloLoopCut

把活动或访谈素材直接剪成精简正式 MP4。默认 3:4、1080×1440、30fps、原速、约45秒；保留真实观点和限定词，自动完成选段、字幕、大字、章节、Logo、配乐、调色和质检。

```text
用 $sololoopcut 剪辑这批活动素材，按 SoloLoop 的风格，直接出精简成片。
```

[完整规范](skills/sololoopcut/SKILL.md) · [工程字段](skills/sololoopcut/references/project-format.md)。附可运行的准备、转写、验证、渲染、QA及原创96BPM配乐生成脚本。依赖Python、FFmpeg、中文字体和基础科学计算库；转写需自行提供本地模型。

本公开归档版根据已确认的对话规范和渲染流程恢复，并在当前Linux环境验证；当前环境未挂载原Windows技能目录，因此不声称与该目录逐字节一致。保留原版品牌图和配乐生成器，不附每期原片、成片、嘉宾肖像示例或录音。原始品牌图用于SoloLoop品牌排版，其他品牌请提供自己的标识。

## 后续维护

新增技能放入 `skills/<skill-name>/`，同时更新 README 和 catalog.json。维护规则见 [AGENTS.md](AGENTS.md)。

检查仓库：

```text
python tools/check_repository.py
```

技能更新后还需做对应的实际行为检查，并同步本机安装版本。仓库检查仅验证目录、索引、引用和代码语法，不替代成片视觉与听感检查。

本仓库当前公开，DrqCut 已获授权在此发布。每期原片、录音、成片、模型权重、运行缓存和凭据留在项目或环境中。原点社区、原点学堂、原点夜校相关技能继续归档到其独立的社区技能仓库。
