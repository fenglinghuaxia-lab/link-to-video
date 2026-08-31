# BGM 曲库

来源：incompetech.com（Kevin MacLeod 作品），**CC-BY 4.0**。
每首已裁剪为 90 秒 / 128kbps / 1.4MB（原曲 4-6MB，27 秒的视频用不了整首）。

曲目清单和署名信息见 `manifest.json`，由 `fetch_bgm.py` 自动维护，不要手改。

## 四个情绪包

| 目录 | 首数 | 适用 |
|---|---|---|
| `upbeat/` | 8 | 轻快积极 —— 教程、干货、开场抓人 |
| `calm/` | 5 | 沉静思考 —— 深度分析、读书、长文解读 |
| `focus/` | 5 | 专注商业 —— 数据、科技、品牌、企业向 |
| `warm/` | 4 | 温暖叙事 —— 故事、人物、情感、收尾 |

## 用法

```bash
--bgm random     # 全库随机
--bgm upbeat     # 只在该情绪包内随机
--bgm <文件路径>  # 指定某一首
--bgm none       # 不要音乐
```

## 署名（CC-BY 4.0 硬性要求）

用在视频号/抖音等公开平台**必须署名**。选曲后脚本会打印署名文本，
把它贴到视频简介末尾即可，格式：

```
Music: "Sunshine" Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 4.0
http://creativecommons.org/licenses/by/4.0/
```

## 扩充曲库

```bash
# 线上 1400+ 首里搜
python fetch_bgm.py --search "piano"
python fetch_bgm.py --search "Carefree" --exact

# 下载并归入某个情绪包
python fetch_bgm.py --fetch "Sunshine,Cipher" --mood upbeat

# 查看当前曲库
python fetch_bgm.py --list
```

### 网络注意事项

incompetech 服务器很慢：

- 曲库清单（`pieces.json`，939KB）单次下载约 **100 秒** —— 已做本地缓存
  `_pieces_cache.json`（7 天 TTL），**别改成每次都拉**
- mp3 下载约 200KB/s，`--curate` 全量 22 首约 10 分钟，建议放后台跑

### 想换别的音源

把任意 mp3 丢进对应情绪包目录，再往 `manifest.json` 的 `tracks` 里补一条：

```json
{"file": "upbeat/MySong.mp3", "title": "MySong", "mood": "upbeat",
 "feel": "Bright", "instruments": "Piano", "duration": 90,
 "credit": "署名信息"}
```
