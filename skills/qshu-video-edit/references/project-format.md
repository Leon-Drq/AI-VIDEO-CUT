# 项目与执行模板

下列命令里的 `SKILL` 指当前 skill 的实际目录；`python`、`ffprobe` 用当前环境已经发现的可执行文件，Windows 可传完整路径。

```text
python SKILL/scripts/init_project.py INPUT.mp4 --out NEW_VERSION_DIR --ffprobe FFPROBE_PATH --width 1080 --height 1920
python SKILL/scripts/audit_timeline.py NEW_VERSION_DIR/shot-map.json --out NEW_VERSION_DIR/verify/timeline-audit.json
```

初始化器不改源文件，输出目录存在就拒绝；默认沿用源尺寸和帧率，传宽高覆盖尺寸，`--fps` 覆盖帧率。保存完整 probe，旋转/VFR信息需要剪辑时读取并正确处理。初始化得到的是草稿，不是已完成工程。

`project.json` 保存源、输出尺寸、帧率、时长、音轨策略与字幕语言。完成对白剪辑后更新最终 duration；B-roll 时码全部使用最终时间轴。

`shot-map.json` 示例（示例值不能直接套新片）：

```json
{
  "duration": 45.0,
  "fps": 30,
  "items": [
    {
      "id": "room-reveal",
      "timeline_in": 10.2,
      "timeline_out": 12.3,
      "spoken_anchor": 10.2,
      "asset_key": "official-room-01",
      "purpose": "explain",
      "source_kind": "primary",
      "source_url": "https://example.com/actual-source-page",
      "rights_note": "Record the actual permission or license basis",
      "information_card": false,
      "state_changes": [{"time": 10.2, "state": "Show the room on its spoken name"}]
    }
  ]
}
```

- `items` 记录 B-roll 和图解；真人底片不用为了通过审核伪造素材记录。
- `information_card: true` 用于全屏信息卡，超过 2.5 秒时有多个论点应安排有意义状态；完整案例需要稳定阅读可记录非空 `hold_reason` 说明。普通照片无需机械套状态数量。理由用于复核，不代表可以把动态功能演示替换成静图。
- 状态 `time` 是全局时间，不是镜头局部时间。实际字幕与数字揭示还需对照转录。
- 合理重复用 `reuse_reason`；合理提前用 `early_entry_reason`；叠加/转场重叠用 `overlap_reason` 说明。
- `source_kind: generated` 不可与 `purpose: prove` 组合。来源缺失会提示，具体素材仍须在 `assets/sources.json` 和 `SOURCES.md` 有完整归属。
- 审核器检查时间边界、提前展示、状态顺序、重复及重叠，不会判断词义、许可真伪、字幕宽度或成片观感。这些必须实查。

案例镜头还应记录 `framing`：源尺寸、来源入出点、完整内容范围、目标展示框、`fit: contain`、必须可见的标题/坐标轴/按钮，以及是否使用说明用静帧及其理由。这些是制作与复核记录，时间轴脚本不验证其几何正确性；按 [完整取景](full-frame-materials.md) 实查最终画面。

其余文件按任务需要创建：干净对白、EDL、词级转录、ASS/SRT、素材清单、渲染脚本、`renders/final-vN.mp4`、`verify/delivery-review.md`。不用为所有任务预先生成空占位文件。
