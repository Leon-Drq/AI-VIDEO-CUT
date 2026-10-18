# 基础包装器使用

`scripts/behind_titles.py` 提供两个独立命令：`matte` 生成连续灰度人物 alpha；`render` 将背景调色、人后大字与胶囊字幕合成到已精剪视频上。它不做自动选段、字幕转录、B-roll 搜集或自动隐私打码。

## 输入条件

- 已精剪、无旧硬字幕的干净视频。旋转已实际应用，方形像素，恒定帧率，音画时间基准从零开始。源片若有非零音频起点，先在剪辑工程正确处理；不能单纯同时清零而抹掉实际音画偏移。
- 输出画幅与配置 `canvas` 一致。横版模板不能原样套竖版；字幕位置、字宽与人物活动空间须重新确定。
- 人物 matte 与干净视频完全同帧数、帧率、裁切和变速；灰度白色代表人物，黑色代表背景。
- 字体、RVM ONNX、FFmpeg 路径由实际环境提供。不自动下载权重或字体，不把模型放入技能包。

依赖：Python 3、Pillow、NumPy、OpenCV；仅 `matte` 需要 onnxruntime。模型接口为官方 RVM 的 `src/r1i/r2i/r3i/r4i/downsample_ratio` 六输入、前景/alpha/四状态输出。`--help` 查看参数。

## 调用

以下用 PATH 中的 Python/FFmpeg 举例。Windows 使用包含上述库的 Python 完整路径；FFmpeg 未在 PATH 中时，两条命令均增加 `--ffmpeg` 与 `--ffprobe` 绝对路径。

```text
python behind_titles.py matte --input project/source/clean.mp4 --model models/rvm_mobilenetv3_fp32.onnx --output project/assets/person-alpha.mkv --cuts 120,240
python behind_titles.py render --config project/style.json
```

`--cuts` 是零起始的镜头切换帧号，仅在实际有切镜处填写。状态会在这些帧重新初始化。默认 960 px 宽 matte、0.5 内部 downsample；全身细小动作或发丝边缘不足时提高输入宽度，先观察质量再决定。

把 `assets/style-template.json` 复制成当前项目的 `style.json`。模板演示 4 秒布局；所有文字和时间必须由本次台词替换。配置里的文件路径相对配置文件所在目录解析，也支持绝对路径。

## 配置字段

- `input/matte/font/output`：对应文件；输出必须为新 `.mp4`，程序拒绝覆盖已有文件。
- `canvas`：`[宽, 高]`，必须与归一化输入相同，且为偶数尺寸。
- `presenter_ranges`：真人镜头区间。仅这些范围进行背景调色与人物前景复合；录屏镜头可保持原样。
- `titles`：每条含 `text/start/end/x/y/size`，位置是字形区域左上角。可选 `weight`、`tracking`、RGBA `color`、`fade_in`、`rise`、`allow_crop`。标题区间必须完整处于某个人物区间内。
- `spoken_anchor`：为剪辑师保留的语义锚点，程序不推断台词；具体时码由当前转录确定。
- `subtitle_style`：字号、字重、字距、胶囊高度、横向内边距、安全边距、顶边位置、背景模糊与颜色。
- `captions`：`start/end/text`，半开区间 `[start,end)`。字幕过宽、越界或内部重叠会报错，先拆句或改排版再渲染。
- `background`：只对背景使用 RGB 通道增益和偏移；不要用过强蓝调影响遮罩边缘肤色。

变量字体会设置 Weight 轴。若用静态字体，字体文件本身就应是所需字重；程序不会将 Regular 自动伪粗成 Black。需要标题和字幕使用不同静态字体时，改用两份 Typography 实例或现有编辑工程。

## 缓存与校验

`matte` 用 FFV1 输出 `.mkv`，旁边写来源 SHA-256、帧数、帧率与切镜帧清单。`render` 发现此 manifest 时核对来源；源片重新剪过就重新生成或用显式帧映射重建 matte，不能继续使用旧缓存。

已有外部 matte 无 manifest 时允许使用，但报告 `matte_source_verified=false`；帧率、帧数仍需一致，人工确认它来自当前画面。相同帧数并不证明遮罩正确。

画面用 libx264 编码，输入第一条音轨以 stream copy 复用；无音频的输入不会凭空生成音轨。若源音频不能装入 MP4，先在项目中转为兼容音轨，重新校验同步。程序本身不重做响度处理。

临时编码使用 `.partial.mp4/.partial.mkv`，成功核对后改为目标名；错误时保留 partial 和日志供检查，不覆盖源文件。输出旁的 `.render.json` 是技术渲染记录，不等于完整视觉或听感验收。完整解码、边缘、字幕、隐私和音频质量仍按技能的交付要求检查。
