---
name: sololoopcut
description: 把活动、社群交流、访谈和口播素材直接精剪为 SoloLoopCut 风格正式成片，并按需制作中文封面。用于“SoloLoopCut”“SoloLoop 剪辑”“按上次社群视频剪”“丢素材直接出精简成片”“SoloLoop 封面”等请求。自动完成转写校对、语义选段、橙白大字、衬线身份字、字幕、章节进度、右上角原版 Logo、现场原声与原创配乐、HDR 调色、清晰度保护和交付质检；封面采用纯白扁平斜体大标题与视频真实人物。交付可观看 MP4，而非只给方案。
---

# SoloLoopCut

把有内容的现场表达剪成节奏清楚、人物可信、文字有层级的精简视频。沿用已确认的 SoloLoop v4 剪辑语言：保留高光色彩，从原片单次有损输出，使用原始品牌文件。

## 默认行为

- 收到素材或本地目录后直接开工，完成选段、结构、字幕、大字、配乐、调色和正式导出，不等待常规预览或脚本批准。
- 默认 3:4、1080×1440、30 fps、现场原声 1.0 倍速；目标约45秒，通常30–60秒。材料不足则缩短，复杂完整表达可延至75–90秒，不凑固定时长。用户新要求优先。
- 保留原片及旧版，交付正式 MP4。仅改视觉时锁定已确认的剪辑、速度、台词、字幕时码和音轨，支持复制旧成片音频。
- 默认嘉宾现场原声作为配音，不默认添加AI旁白、克隆声音或把某人台词对到另一人的嘴上。
- 用内置配乐生成器延续本工程的原创96 BPM器乐风格。它不是已识别的对标原片歌曲，不宣称复用了该歌曲。
- 用 assets/SoloLoop-logo-original.png 原始透明标识；不生成式重画近似Logo。用户新提供品牌文件时优先新文件。
- 按新素材重新选段、写标题和章节，不继承旧片的人名、职务、单位、年份、ICT、版权等事实。
- 用户要求封面时，读 [中文封面规范](references/cover.md)：默认优设标题黑斜体、纯白扁平大字、中文主题、视频真实人物和右上角原版 Logo。只将此规范应用于封面，片内字幕与身份字沿用原样式；用户当次明确要求优先。
- 只有素材缺失、不能解码或核心要求互斥时询问，同时继续独立可做的工作。不要把填写EDL交给用户。

## 执行流程

1. 读 [素材与剪辑](references/editing.md)，实际列出原片，排除参考片、旧成片和工程输出。用 prepare 探测旋转、显示尺寸、帧率、音轨起点、色彩和HDR，建立独立工程。
2. 用可用工具或 scripts/transcribe.py 取带词级时间戳的逐字稿，回到原音核对姓名、数字、年份、单位、术语和不清楚处。ASR是草稿，不据此编身份或原话。
3. 按“真实观点 → 活动定位 → 人物经历 → 具体方法 → 交流启发 → 收尾”组织，按完整意群切，保留限定词和否定，删除重复及无意义停顿。在 edit.json 写可追溯的源入点、整数帧和图文锚点。
4. 读 [视觉规范](references/visual-system.md)，按实际人物位置设计4–6个有内容的章节、橙白大字、衬线身份字、数字卡和递进标签；字幕最后合成。检查约360px手机预览。
5. 必读 [画质](references/picture.md) 和 [声音与字幕](references/audio-captions.md)。区分SDR/HLG/PQ，直接从原片裁切调色，无损中间文件，最终一次H.264有损输出。保护高光色彩、皮肤细节和真实现场光。
6. 运行 validate、render、qa，按 [交付规范](references/delivery.md) 检查全部镜头、剪切点、开头结尾、大字/字幕/Logo避让、黑帧停帧、完整解码、时长和最终AAC响度。修复后交付，如实记录没看的画面及没听的声音。
7. 用户要求封面时，按 [中文封面规范](references/cover.md) 制作并检查最终图；封面修改不重剪已确认的成片。给正式MP4及已请求封面的可点击链接和本地绝对路径；保留工程、EDL、SRT、混音与QA，按环境要求保存成片，不擅自上传平台。

## 工具

Python3.10+，FFmpeg/ffprobe，Pillow、numpy、scipy；本地转写另需faster-whisper及本地模型。配乐以标准库写24bit WAV，不依赖音频写入扩展。复用已有环境，不强制更换渲染框架。

```text
python scripts/sololoopcut.py prepare INPUT... --project PROJECT
python scripts/transcribe.py PROJECT --model LOCAL_WHISPER_MODEL
# 剪辑代理根据真实画面和校对后的原话填写 edit.json。
python scripts/sololoopcut.py validate PROJECT
python scripts/sololoopcut.py render PROJECT
python scripts/sololoopcut.py qa PROJECT
```

支持 --ffmpeg/--ffprobe、SOLOLOOP_FFMPEG/SOLOLOOP_FFPROBE 和PATH；字体与模型可通过参数/环境变量指定。本机旧路径仅作可选发现，不是跨机器硬依赖。工程字段见 [工程格式](references/project-format.md)。scripts/overlay.py绘图，scripts/score.py按目标时长生成原创配乐。

公开归档保留规则、脚本、样式和原版品牌图；用配乐生成器替代已渲染录音，不收录嘉宾肖像示例、原片、成片、模型、缓存和凭据。归档内容按本对话已确认的流程恢复并做跨平台验证，不声称与未挂载的原Windows目录逐字节一致。
