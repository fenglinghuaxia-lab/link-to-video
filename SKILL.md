---
name: link-to-video
version: 1.3.0
description: 文章链接 → 手机版截图切片 → 封面 + BGM → 视频号竖版短视频。给一个知乎/公众号/网页文章链接，自动生成 1080x1920 MP4。11 种卡片边框配色可选，22 首 CC-BY 免授权音乐按情绪随机。
trigger_when:
  - 用户给出文章链接要求"转视频/生成短视频/切片视频/截图视频"
  - 用户提到"知乎文章做成视频"、"公众号文章转视频"、"文章转视频号短视频"
  - 用户要求换边框颜色 / 换 BGM / 重出封面（此时截图已存在，直接跳到第 4、5 步）
---

# link-to-video：文章链接 → 视频号短视频

把用户的知乎文章（或公众号/网页文章）转成「封面 + 截图切片轮播 + BGM」的竖版短视频。

---

## ⚠️ 第一步：先问边框配色，再动任何命令

**每次调用本技能，在跑第一条命令之前，必须先让用户选边框配色。**
不要默认用 `deepblue` 直接往下做——用户明确要求过这一步。

展示方式（二选一，优先第一个）：

1. 把 `assets/examples/presets.png` 用 present_files 给用户看（11 种配色套在同一页上的对比图）
2. 或者用 show_widget 画一张色卡（外层圆角底 + 白色内容区 + 内虚线）

```
预设名      外层       虚线       适用
deepblue   #7FA8D4   #5A82B0   深蓝 · 专业商务（金融/科技）
navy       #5B7FA6   #3E5C7E   藏青 · 沉稳权威（财经分析/研报）
mint       #D8EDE5   #A8C9BC   薄荷绿 · 清新自然（教育/读书/生活）
warm       #E8D5C4   #C4A484   暖棕 · 温暖文艺（随笔/故事/情感）
lavender   #DDD6EB   #B0A0CC   淡紫 · 优雅高级（艺术/设计/女性向）
gold       #F0E4C8   #C9A961   香槟金 · 高端质感（品牌/奢侈品/年终）
crimson    #F2DADA   #C08080   朱红 · 热烈醒目（行情/节日/促销）
teal       #D2E8E6   #7FA8A4   青碧 · 冷静科技（医疗/制造/数据）
slate      #DDE1E6   #9AA4B0   石墨灰 · 中性理性（资讯/干货/通用）
sand       #EDE4D3   #BFAA8A   米杏 · 柔和耐看（长文/连载/日更）
plain      #FFFFFF   #DDDDDD   无框 · 极简白
```

**同一轮里顺带问的另外两件事**（不要分多轮骚扰用户）：
- BGM 情绪包：upbeat / calm / focus / warm / random / none
- 切片数：默认 5，长文 7（跑两版比一下更稳，见后文）

用户答完再进入下面的流水线。

---

## 目录结构

- `scripts/capture.py` — 手机视口截图 + 按段落边界切片
- `scripts/reslice.py` — **按视觉跨度重新切片**（推荐，替代 capture 的等高分法）
- `scripts/clean_slices.py` — 智能裁剪空白/UI/孤立图标 → `screenshots/`（小红书用）
- `scripts/add_border.py` — 卡片式边框 → `video_frames/`（视频用）
- `scripts/make_final.py` — 封面（标题自动取 meta.json）+ ffmpeg 合成
- `scripts/fetch_bgm.py` — BGM 曲库管理（搜索 / 下载 / 截取 / 登记）
- `scripts/make_video.py` — 旧版一步式合成（简单场景可用）
- `assets/bgm/` — BGM 曲库（按情绪分 4 个子目录，清单见 `manifest.json`）
- `assets/storage_state.json` — 知乎登录态（--login 后自动生成）

## 运行环境

- Python: `C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe`
  已装 playwright / imageio-ffmpeg / pillow / numpy
- 浏览器：本机 Chrome（playwright channel="chrome"）

## 标准流程（五步，推荐）

```bash
PY=C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe
SKILL=C:/Users/Lenovo/.workbuddy/skills/link-to-video
WORK=<工作目录，如 C:/Users/Lenovo/WorkBuddy/<日期>/link2video/<文章slug>>

# 1. 截图（--out 就是工作目录，产出 full.png + slice_*.png + meta.json）
$PY $SKILL/scripts/capture.py "<文章URL>" --out $WORK/capture_v1 --slices 7

# 2. 按视觉跨度重新切片（关键：capture 的等高分法遇到空白/大图会失衡）
$PY $SKILL/scripts/reslice.py --base $WORK --input-dir capture_v1 \
    --out-dir capture_v2 --slices 7

# 3. 裁剪空白与垃圾元素 -> screenshots/slide_*.png（小红书用）+ video_frames/frame_*.png
$PY $SKILL/scripts/clean_slices.py --base $WORK --input-dir capture_v2

# 4. 卡片边框（颜色按用户选择，见下方预设）
$PY $SKILL/scripts/add_border.py --workdir $WORK \
    --bg-color "#7FA8D4" --dash-color "#5A82B0"

# 5. 合成（封面标题自动从 capture_v2/meta.json 读取，需先 cp meta.json 过去）
cp $WORK/capture_v1/meta.json $WORK/capture_v2/meta.json
$PY $SKILL/scripts/make_final.py --workdir $WORK --slices-dir capture_v2 \
    --out $WORK/final.mp4 --theme warm

# 产物: $WORK/final.mp4 (1080x1920, 30fps) + cover.png + screenshots/slide_*.png
```

> **截图先给用户确认再生成视频**——用户明确要求过这一步（省积分）。
> 第 3 步跑完就展示 `screenshots/`，确认后再跑 4、5。

## 知乎登录（首次必做）

知乎未登录会把专栏/回答重定向回首页，**首次使用前需保存登录态**（约 3 分钟有效期内无需重复）：

```bash
$PY $SKILL/scripts/capture.py login --out $WORK --login
# 会打开 Chrome 窗口，手动扫码登录知乎，脚本自动保存 storage_state.json
```

登录态存于 `assets/storage_state.json`，失效（截图被重定向/内容缺失）时重新执行一次即可。

## 可调参数

| 参数 | 默认 | 说明 |
|---|---|---|
| --slices | 5 | 切片数，长文 6-8，短文 3-4 |
| --slide-dur | 3.5s | 每片展示时长（静态轮播模式） |
| --cover-dur | 2.5s | 封面停留时长 |
| --bgm | random | 见下方「BGM 选择」，支持情绪包 / 随机 / 指定文件 / none |
| --cover-title | 文章标题 | 封面主标题（可让用户改写爆款标题） |
| --cover-subtitle | 无 | 封面副标题 |
| --theme | warm | dark / light / warm 三套封面配色 |
| **--preset** | **deepblue** | **内页卡片边框配色预设（见下方 11 个）** |

### BGM 选择（`--bgm`）

| 取值 | 含义 |
|---|---|
| `random` | 全曲库随机（默认） |
| `upbeat` | 轻快积极 —— 教程、干货、开场抓人 |
| `calm` | 沉静思考 —— 深度分析、读书、长文解读 |
| `focus` | 专注商业 —— 数据、科技、品牌、企业向 |
| `warm` | 温暖叙事 —— 故事、人物、情感、收尾 |
| `<文件路径>` | 指定某一首 |
| `none` | 不要音乐（纯静音视频） |

曲库按情绪分 4 个子目录，清单在 `assets/bgm/manifest.json`。
选完脚本会打印署名信息，**必须让用户把署名贴到视频简介里**（CC-BY 4.0 要求）。

扩充曲库：
```bash
$PY $SKILL/scripts/fetch_bgm.py --search "piano"          # 线上 1400+ 首里搜
$PY $SKILL/scripts/fetch_bgm.py --fetch "曲名1,曲名2" --mood upbeat
$PY $SKILL/scripts/fetch_bgm.py --list                    # 看当前曲库
```

> 音源 incompetech.com（Kevin MacLeod，CC-BY 4.0，可商用需署名）。
> **服务器很慢**：曲库清单 939KB 要 ~100 秒，必须走本地缓存
> （`assets/bgm/_pieces_cache.json`，7 天 TTL）——脚本已内置，别改成每次都拉。
> mp3 下载约 200KB/s，`--curate` 全量 22 首实测 10 分钟，放后台跑。
>
> 当前已内置 22 首（upbeat 8 / calm 5 / focus 5 / warm 4），够用，一般不用再下。
> 临时文件走系统 temp 而非 `assets/bgm/_raw`——沙箱禁止删除技能目录下的文件，
> 放技能目录里会堆几十 MB 清不掉（SAFE_DELETE_FAIL_CLOSED）。

### 边框配色预设（`--preset`）

11 个预设，选色原则：低饱和、不抢文字、禁霓虹色。

| 预设名 | 外层 | 虚线 | 适用 |
|---|---|---|---|
| **deepblue** | `#7FA8D4` | `#5A82B0` | 深蓝 · 专业商务（默认，金融/科技） |
| navy | `#5B7FA6` | `#3E5C7E` | 藏青 · 沉稳权威（财经分析/研报） |
| mint | `#D8EDE5` | `#A8C9BC` | 薄荷绿 · 清新自然（教育/读书/生活） |
| warm | `#E8D5C4` | `#C4A484` | 暖棕 · 温暖文艺（随笔/故事/情感） |
| lavender | `#DDD6EB` | `#B0A0CC` | 淡紫 · 优雅高级（艺术/设计/女性向） |
| gold | `#F0E4C8` | `#C9A961` | 香槟金 · 高端质感（品牌/奢侈品/年终） |
| crimson | `#F2DADA` | `#C08080` | 朱红 · 热烈醒目（行情/节日/促销） |
| teal | `#D2E8E6` | `#7FA8A4` | 青碧 · 冷静科技（医疗/制造/数据） |
| slate | `#DDE1E6` | `#9AA4B0` | 石墨灰 · 中性理性（资讯/干货/通用） |
| sand | `#EDE4D3` | `#BFAA8A` | 米杏 · 柔和耐看（长文/连载/日更） |
| plain | `#FFFFFF` | `#DDDDDD` | 无框 · 极简白 |

```bash
$PY $SKILL/scripts/add_border.py --list-presets            # 打印全部
$PY $SKILL/scripts/add_border.py --workdir $WORK --preset navy
$PY $SKILL/scripts/add_border.py --workdir $WORK --preset navy --dash-color '#2E4A6B'  # 微调
```
自定义色会**覆盖**预设中对应的那一层，另一层仍用预设值。

## 使用约定（重要）

1. **先问再动手**：边框配色（必问）+ BGM 情绪包 + 切片数，见开头「第一步」。
   封面标题文案可一并给 2-3 个备选让用户挑。
2. **截图完成后先给用户看再合成视频** —— 用户明确要求过这一步。
   第 3 步（clean_slices）跑完就展示 `screenshots/`，确认后再跑 4、5。
3. **首次生成后展示成片**，用户偏好"多版对比再定稿"——
   换 `--theme` / `--bgm` / `--preset` 就能快速出变体，**不用重跑截图**
4. 选了 BGM 后**必须提醒用户把署名贴进视频简介**（脚本会打印署名文本）
5. 用户只做**自己写的文章**（版权安全）
6. 支持平台：知乎专栏/回答、微信公众号文章（自动识别选择器），其他平台用 `--selector` 手动指定
7. 想更新技能描述里的预览图：`python scripts/make_preview.py`

## 已知问题

- 知乎登录态约几天~两周失效，症状是截图内容为首页，重新 `--login` 即可
- 公众号文章部分被防盗链拦截，正文容器识别不到时用 `--selector "#js_content"` 手动指定
- capture.py 结尾用 `os._exit()` 规避 playwright greenlet 清理报错，属正常

## 已内置的四个修复（勿删）

**1. 加粗失效修复（重要）**
知乎移动端把 `<b>/<strong>` 的 `font-weight` 设为 **500(Medium)** 而非标准 700。
Windows 无 PingFang SC，回退到微软雅黑后只有 400/700 两个字重，
CSS 规范下 500 会就近回退到 **400 → 加粗完全消失**（Mac/iOS 上正常，因为苹方有 Medium 字重）。
capture.py 已内置修复：把 500~699 的字重强制提升到 700。
实测墨水量 +13.8%（首段加粗多的切片 +22.3%）。
**症状判断**：截图里加粗文字和普通文字看起来一样粗。

**2. 正文 UI 残留清理**
知乎把互动栏（点赞/评论/收藏）、评论区、推荐阅读塞在正文容器附近，
直接切会混进视频画面。capture.py 已内置 `JUNK_SELECTORS` 移除这些元素，
并移除所有 `fixed/sticky` 定位元素（顶部导航、底部悬浮栏）。
**症状判断**：切片里出现"欢迎参与讨论"+图标，或顶部带搜索框。

**3. 懒加载图片强制加载（重要）**
微信/知乎把真实图片地址放在 `data-src` / `data-original`，靠滚动触发。
触发失败时图片渲染成**整宽、几百px高、灰度恒定的浅灰占位块**（实测灰度 247、零对比度），
截图后就是一大片空白，肉眼极难定位，只能靠像素分析发现。
capture.py 已内置：滚动后强制把 `data-*` 写回 `src`，并 `wait_for_function` 等
所有图片 `complete && naturalWidth>0`（超时 15s 会打印警告）。
**症状判断**：`full.png` 里出现整宽、高度 300~1000px、灰度 247 的纯色块；
或 capture 日志打印"有图片加载超时"。

**4. 裁剪截断修复（clean_slices.py v2，重要）**
旧版用「整行非背景像素占比 > 5%」判定内容行，**短行会被漏检**——
换行后只剩几个字（占行宽约 15%）的最后一行被当成空白裁掉。
实际案例：公众号文章第②点"不适合完全0基础的小白。"被切成"不适合完"。
v2 改为 numpy 逐行统计 + **连续空白行分块 + 孤立小图标剔除**：

| 参数 | 值 | 作用 |
|---|---|---|
| INK_THR | 45 | 与背景灰度差超过此值算有墨 |
| LINE_GAP | 25 | 块内合并间隙（一行文字的上下部分） |
| CLUSTER_GAP | 220 | 簇合并间隙（行距 63 / 段距 137 都远小于此） |
| JUNK_SPAN/WIDTH | 90 / 70 | 孤立小图标尺寸上限 |
| JUNK_INK_RATIO | 0.15 | 孤立小图标墨量上限（相对主簇） |

**症状判断**：某页最后一行明显被切一半，或切片里残留一个孤零零的小圆环/按钮图标。
**验收方法**（改完必跑）：逐张检查顶/底 6px 是否有墨，必须为 0：
```python
g = np.asarray(Image.open(p).convert('L'), dtype=np.int16)
te = int((np.abs(g[:6]-255)>45).sum()); be = int((np.abs(g[-6:]-255)>45).sum())
# te == 0 and be == 0 才算没截断
```

## 为什么必须用 reslice.py 重新切片

capture.py 按**页面高度**均分，遇到大片空白（未加载图片、大间距模块）就会失衡：
实测某篇公众号文章 7 片中最矮的一片只有 755px、最高的 2133px（3 倍差距），
画面长短悬殊很难看。reslice.py 改为：

1. 逐行统计墨量 → 找出所有 ≥80px 的空白段
2. 把超过 120px 的空白段在**度量上压缩到 120px**（只用于计算，不改图）
3. 在压缩后的坐标轴上等分，切口吸附到最近的空白段中心（±500px）
   → 保证切口落在段落间隙，不会把一行字劈开

实测同一篇文章从 755~2133（3.0x）收敛到 1743~2200（1.26x）。
`--cap-gap` 可调（默认 120）。

> 注意：别用「按内容墨量行数均分」——图片会贡献几百行墨量却只是一个元素，
> 实测反而更失衡（372~782 行）。

### 切片数怎么定：跑两版比一下

capture 只跑一次（最慢最贵），之后 `reslice.py --slices N` 随便试，
所以切片数不用纠结——直接跑两版比高度跨度，选更匀的：

```bash
for N in 5 6; do
  $PY $SKILL/scripts/reslice.py --base $WORK --input-dir capture_v1 \
      --out-dir capture_n$N --slices $N
done
```

挑的时候别只看均衡度，**还要看最高那页会不会顶到画布**：
卡片 = 内容 + 88px 边框，画布 1920，所以单页裁剪后高度最好 ≤ 1830px。
再高 add_border.py 会自动缩小，字就变小了。

实例（知乎《巴菲特和段永平对期权的态度截然不同》，full.png 11190px）：

| 片数 | 各页裁剪后高度 | 跨度 | 判断 |
|---|---|---|---|
| 5 | 2379 / 2226 / 1952 / 2195 / 2438 | 1.25x | 最高的 2438 会顶到画布，字被压小 |
| 6 | 1939 / 1842 / 1632 / 1938 / 1920 / 1919 | 1.19x | 更匀且都在 1830 附近，选它 |

### 内容密度参考

`reslice.py` 打印的「内容行总数 / 原高度」能预判切片难度：

- ~23%（公众号《新手小白如何快速掌握期权》）—— 图文稀疏，最容易出极短页
- ~43%（知乎《巴菲特和段永平》）—— 图文很满，5-6 片都合适

密度低于 30% 的文章**必须**用 reslice，等高分法必翻车。

### 首屏顶部那一大块通常是标题，别删

知乎专栏截图后，第 1 页顶部常有一整块 300-400px 高、整宽、墨量 20-37%
且行间几乎不断开的内容——容易误判成 UI 垃圾。
实际是文章大标题（88px 字号 × 3 行左右），**保留**，视频开头显示标题是对的。

区分方法：UI 垃圾会有图标轮廓、宽度不满行、且被 JUNK_SELECTORS 清掉；
标题则是整宽、多行、颜色单一（深色像素 RGB 标准差 < 30）。

## 排错

| 症状 | 处理 |
|---|---|
| 截图是知乎首页 | 登录态失效，重新 --login |
| "Element is not attached" | 页面结构变化，加 --selector 手动指定正文容器 |
| ffmpeg 失败 | 看 stderr 最后 3000 字符，多为图片损坏（重跑 capture） |
| BGM 无声 | 确认 mp3 完整（probe Duration 正常） |
| 某页文字被切一半 | clean_slices.py 边界检测失效，用上面"验收方法"定位后调 CLUSTER_GAP |
| 卡片超出画布被裁 | add_border.py 已自动收缩（CARD_PAD=88 + BREATH=40），若仍溢出调 --target-width |
| 页面长短悬殊 | 用 reslice.py 重新切片，别用 capture.py 的等高分法 |
| 视频里少了一张配图 | 图片懒加载失败，capture.py 已内置强制加载；仍失败看日志"有图片加载超时" |
