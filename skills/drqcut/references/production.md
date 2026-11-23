# 工程工具与交付检查

## 建立最终时间轴

已有工程直接在新版本上操作。新片可从技能根目录运行以下命令。两个工程脚本只需 Python 标准库；初始化还会调用 ffprobe。

```text
python scripts/init_project.py source.mp4 --out edit-v1 --ffprobe ffprobe --width 1080 --height 1920
python scripts/audit_timeline.py edit-v1/shot-map.json --out edit-v1/verify/timeline-audit.json
```

第一条命令读取元数据并建立目录，拒绝覆盖已有版本。剪完对白后更新项目和分镜的最终时长、帧率。第二条命令在填入实际分镜后执行。以下是一段示例，数值均为**最终时间轴**秒数。

```json
{
  "duration": 12.0,
  "fps": 25,
  "items": [{
    "id": "document-detail",
    "timeline_in": 3.2,
    "timeline_out": 7.12,
    "spoken_anchor": 3.2,
    "asset_key": "provided-document-p1",
    "source_kind": "user",
    "purpose": "explain",
    "information_card": true,
    "state_changes": [
      {"time": 3.2, "state": "先认文件标题和发布者"},
      {"time": 4.8, "state": "移到原文中对应的一句，停稳供阅读"}
    ]
  }]
}
```

在来源清单按 `asset_key` 记录具体素材、出处、授权依据和转用范围。公开来源分镜另写 `source_url` 和 `rights_note`。同一素材呼应复用时记录 `reuse_reason`，合理提前出现用 `early_entry_reason`，有意转场重叠用 `overlap_reason`。长时间稳定阅读可用 `hold_reason`。分镜检查能发现时间越界、含糊的重复与顺序问题，语义、来源和阅读感受仍需人工复核。

原速源片多个保留段以相同倍率播放时，累计已保留段时长除以倍率，再加上当前段内偏移除以倍率，即为最终秒数。跳切、不同倍率及定格分别记录映射。字幕和配画锚点统一到同一输出帧率；切换镜头后需要连续抠像时重置时序模型，缓存绑定源文件、剪口、尺寸和帧号。

## 合成与导出

先出干净对白与同轴底片，再叠主素材、必要的局部提示和字幕。真人主标题默认采用[人后大字](presenter-typography.md)，按“真人底片 → 白色标题 → 逐帧 alpha 恢复原人物”的顺序；重叠处用真实人物遮罩，推近时遮罩和底片使用同一变换。用不同透明度或底片渐隐时避免留下第二张脸或重影。人物小窗在素材上方、对白字幕在阅读安全区。逐段检查连续动作中的极值位置。

用现有 FFmpeg、Remotion 或其他项目渲染器输出 H.264、yuv420p 和兼容音频。若已有渲好的画面和同起点、同长度的兼容音轨，可用以下命令把两者无损合流。先用 ffprobe 核对流起点、帧数、帧率、声轨布局和时长；多语言、多音轨项目按任务明确映射。时长不符时回到时间轴查找原因。

```text
ffmpeg -n -i picture.mp4 -i approved-audio.mp4 -map 0:v:0 -map 1:a:0 -c copy -movflags +faststart final-v2.mp4
ffprobe -v error -show_streams -show_format -of json final-v2.mp4
ffmpeg -v error -xerror -i final-v2.mp4 -map 0:v:0 -map 0:a:0 -f null -
```

## 从交付文件复核

- 连播前三秒、主要动作、每个争议片段与结尾。用约 360 像素宽静音复看，能否认出对象、读到关键句、看清前后关系。人像遮罩、录屏裁切和大字检查入场、最大位移及退场。
- 核对字幕、专名、金额、时间、来源署名及可见网址。局部修订在相同台词的同一帧并排看新旧版，区分装饰线、原图边缘和数据坐标。
- 听对白接缝、轻声尾字、音效覆盖和结尾是否截断。检查响度与真峰值、黑屏或异常静音，逐一解释候选。只做过解码或响度测量时如实记录。
- 画面修订若要求音轨原样保留，用同样的命令分别对新旧文件执行 `ffmpeg -v error -i FILE -map 0:a:0 -c copy -f hash -hash sha256 -`。再分别核对音轨起点、时长及首中尾口型。单独核对 SRT 文件与实际烧录画面的字和时码。
