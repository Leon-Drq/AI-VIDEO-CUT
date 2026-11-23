# 工程与命令

由剪辑代理查看预览、转写和原片并填写edit.json，不推给用户，也不让脚本猜语义。源时间为原片秒，frames为正整数；镜头顺序即cuts顺序，总长=sum(frames)/fps。

```json
{
  "name":"SoloLoopCut", "width":1080, "height":1440, "fps":30,
  "version":1, "music":true, "music_gain":0.24,
  "cuts":[
    {"source_id":"source-01","source_in":2.3,"frames":90,"voice":true,"focus":[0.5,0.58],"evidence":"verified source audio"},
    {"source_id":"source-02","source_in":1.2,"frames":45,"voice":false,"fit":"contain"}
  ],
  "captions":[{"start":0.05,"end":2.8,"text":"替换为核实后的真实原话","highlight":"真实原话"}],
  "elements":[
    {"type":"line","text":"已核实观点","start":0,"end":2.9,"x":62,"y":712,"size":160,"font":"black","color":"#F59A31"},
    {"type":"line","text":"简明问题？","start":0.16,"end":2.9,"x":62,"y":912,"size":126,"exit":"scatter"},
    {"type":"card","text":"阶段一","start":3.05,"end":4.4,"x":55,"y":676,"width":580,"height":138,"size":92}
  ],
  "topics":[],
  "chapters":[{"label":"观点","start":0,"end":3},{"label":"现场","start":3,"end":4.5}]
}
```

示例文字是说明占位，不能直接作为真实台词交付，时间不是固定模板。

| 可选字段 | 含义 |
| --- | --- |
| cut.crop | 旋转后原生[x,y,w,h]，cover时保持画幅比例，避免拉伸 |
| cut.focus | 相对裁切中心，按人物调整 |
| cut.fit | cover/contain，横屏默认contain保护主体 |
| cut.zoom | 默认1，4K可轻微放大，1080p忽略额外放大 |
| cut.grade | saturation/gamma/sharpen/desat/peak；PQ需核实peak |
| cut.gain_db | 原声增益，默认0 |
| voice | true现场原声，false静音B-roll，无音轨不能true |
| audio_from | 视觉修订的旧成片绝对路径，时长和语义时间轴必须相同 |
| logo/font_dir | 自定义品牌图/字体目录 |
| music_file | 用户提供且可用的配乐，否则原创生成 |
| elements.font | black/bold/regular/serif/identity |
| elements.subtitle | 数字卡下面的说明，须有依据 |
| topics | text/start/end，避开右上Logo |

scripts/requirements.txt为基础依赖，本地转写另外安装faster-whisper并提供模型路径。字体优先Noto SC可变体，Linux支持Noto CJK集合。脚本保存render-result.json和SRT，重复导出递增版本。qa生成实际编码接触表和技术报告，仍需看画面、校事实、尽可能听审。
