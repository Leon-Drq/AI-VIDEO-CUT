# 从原片到交付

每期建独立工作目录，公开归档只保存技能。可用本地剪辑工程完成复杂的全屏追踪、2.5D 截图或演示；随包的 Python 工具能独立产出带真人、字幕、证据和混音的完整 MP4。示例里的文件名是本期提供的输入。命令在本期目录运行，将 `SKILL` 替换为当前技能安装目录。脚本以 UTF-8 读取 JSON，支持中文路径。

## 1. 锁定对白和遮罩

基础依赖为 Python 3、FFmpeg / FFprobe（含 libx264、ALAC、AAC 和 loudnorm）、Pillow、NumPy、OpenCV，以及可用的中文粗无衬线字体。转写另需 faster-whisper 及本地多语言模型目录，抠像另需 onnxruntime 和六输入的 RVM MobileNetV3 FP32 ONNX。在本机先找已有模型、中文字库和 FFmpeg；命令找不到时给相应脚本传入 `--ffmpeg`、`--ffprobe` 的绝对路径。可用同等质量的本地转写、同帧蒙版或现有对白工程替代。真人和音频在本机处理。

```text
python SKILL/scripts/prepare.py transcribe --input 原片.mp4 --model 本地Whisper模型目录 --out 原声逐词.json
python SKILL/scripts/lock_cut.py 原片.mp4 --keep 保留区间.json --out cut
python SKILL/scripts/prepare.py transcribe --input cut/presenter.mp4 --model 本地Whisper模型目录 --out 成片逐词.json
python SKILL/scripts/prepare.py matte --input cut/presenter.mp4 --cut-map cut/cut-map.json --model 本地RVM.onnx --out host.mkv
```

`保留区间.json` 形如 `[[0.0, 4.6], [5.2, 12.3]]`，用原片秒数，前闭后开，去除复述时核实删前删后语义连贯。全段保留可省略 `--keep`。默认为原速；需要时加 `--speed 1.1`。锁定脚本同时剪声音和画面并保持音高，按 30 fps 对齐，输出保留细节的 9:16 中间片和剪口数据。横片默认等比完整纳入画布；如果主体太小先人工确定构图，避免居中裁掉手势。修订已有成片时沿用已批准的映射。遮罩从锁定的人像生成，遇到剪口清空时序记忆；黑为背景，白为前景。

## 2. 按句编排真实素材

复制[六秒工程示例](project.example.json)到本期目录，按整条新片的台词重写。将现有证据下载或截取到本地，记录原始地址、真实主体、发布者、截图/视频入点和所支撑的句子。优先一手论文、官方页面、实际产品、现场照。替换示例字体为有权使用的中文字体。素材和字体路径相对工程 JSON，也支持绝对路径。

| 字段 | 如何使用 |
| --- | --- |
| `presenter / matte / font` | 已锁定口播、同步灰度蒙版、字体文件。`face_roi` 是完整人像画框中的脸部裁切 `[左,上,右,下]`，四边取 0–1；看真人选取，裁完要能完整看到嘴和头顶。 |
| `scenes` | 每项含成片秒数 `start / end` 与 `host`。默认空档显示真人原镜。`sticker` 做真人与资料同屏，`pip` 做圆形同步小窗，`large` 做人后巨字。标题用一至两行数组。可用 `push_at` 指定关键词推近时刻。 |
| `box / moves` | `box=[左,上,宽,高]` 用 1080×1920 像素。`moves=[[成片秒数,目标框], ...]` 依次平滑插值。想先停稳再移动，在起动时刻重复初始框。字段可用于人物或素材；小窗保持正方形。 |
| `materials` | 使用 `file / start / end / kind`；将每个资料镜头完整放入相应场景。有 `paper`、`photo`、`screen` 三种边缘。框内默认等比完整展示。真实现场可用 `full_bleed: true` 与满幅框。多层按数组顺序叠加。`credit` 和可选的 `credit_xy` 写简短出处。 |
| 原始画面与局部 | `crop` 是归一化四边。`detail=[起动秒,落稳秒,[左,上,右,下]]` 从整体推到原句或操作细节。不同机构的证据各自署名。视频用 `video: true`，`offset` 为素材自身起点秒数；用同一项移动布局让演示持续播放。可变帧率录屏先转恒帧率，先检查片长足够。 |
| `captions` | 校对后的 `start / end / text` 采用成片秒数，可用换行切为两个意群。`highlight` 必须是同一行里实际出现的短词。烧录字幕和 SRT 共用同一份数据。 |
| `sounds` | 每项含成片起点 `at`、本地文件 `file`、`duration`、相对源文件的 `gain_db`；可用 `offset` 跳过前导静音。选可使用的真实翻纸、相纸摩擦、轻扫等声音，本地留来源记录。示例增益要按实际音源试听。 |

实际案例的混音顺序是人声先听清、再加动作声。渲染器先测量原声，轻度压缩并以 −15 LUFS 为人声目标，在独立声轨按动作入点混入音效并限峰。每个新镜头用手机扬声器听，小音量下特别检查纸声有没有吞掉“论”“纸”等轻声辅音。

## 3. 渲染、三轮复核和交付

```text
python SKILL/scripts/render.py 本期工程.json --out 交付候选
python SKILL/scripts/check.py 交付候选/成片.mp4 --at 0.15 1.7 2.1 --out 本轮检查
```

成片和 SRT 在渲染成功、音画时长差不超过一帧、整片能解码后才写入交付目录。每版使用新目录。检查工具另存手机尺寸抽帧与响度、黑场、静音提示；给 `--at` 传本期的关键落词和入退场点。重新打开实际 MP4 看运动，带声播放每个剪口，跟读字幕；核对材料归属、演示连续、人物边缘、嘴型、尾音及句尾。发现问题回改工程，导出后复查，最后将 MP4 与 SRT 放入本期成片目录并使用相同的描述性文件名。
