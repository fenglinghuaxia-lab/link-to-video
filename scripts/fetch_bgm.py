# -*- coding: utf-8 -*-
"""
fetch_bgm.py - BGM 曲库管理（下载 / 截取 / 登记）

音源：incompetech.com（Kevin MacLeod，CC-BY 4.0，可商用需署名）
它的曲库清单是一个静态 JSON：https://incompetech.com/music/royalty-free/pieces.json
下载直链：/music/royalty-free/mp3-royaltyfree/<urlencoded filename>
（需带 Referer，否则可能 403）

用法：
  # 搜索（从线上 1400+ 首里找）
  python fetch_bgm.py --search "piano"
  python fetch_bgm.py --search "Carefree" --exact

  # 下载并截取到曲库（--mood 决定归入哪个情绪包）
  python fetch_bgm.py --fetch "Sunshine,Cipher" --mood upbeat

  # 按内置精选清单批量重建曲库
  python fetch_bgm.py --curate

  # 查看当前曲库
  python fetch_bgm.py --list

下载后会自动截取片段（默认 90 秒）并转码到 128kbps，
避免整首 4-6MB 占空间——一段 27 秒的视频用不了整首。
"""
import argparse
import json
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
BGM_DIR = SKILL / "assets" / "bgm"
MANIFEST = BGM_DIR / "manifest.json"
PIECES_URL = "https://incompetech.com/music/royalty-free/pieces.json"
DL_URL = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"

UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Referer": "https://incompetech.com/music/royalty-free/music.html",
}

# 情绪包定义
MOODS = {
    "upbeat": "轻快积极 —— 教程、干货、开场抓人",
    "calm":   "沉静思考 —— 深度分析、读书、长文解读",
    "focus":  "专注商业 —— 数据、科技、品牌、企业向",
    "warm":   "温暖叙事 —— 故事、人物、情感、收尾",
}

# 内置精选清单：Kevin MacLeod 经典曲目，按情绪分组
# 已排除 Dark / Eerie / Aggressive / Somber 等不适合知识类内容的情绪
CURATED = [
    # (曲名, 情绪包)
    ("Carefree",       "upbeat"),
    ("Wallpaper",      "upbeat"),
    ("Super Friendly", "upbeat"),
    ("Sunshine",       "upbeat"),
    ("Electrodoodle",  "upbeat"),
    ("Carpe Diem",     "upbeat"),
    ("Nowhere Land",   "upbeat"),
    ("Nothing Broken", "upbeat"),

    ("Easy Lemon",     "calm"),
    ("Ambiment",       "calm"),
    ("Tranquility",    "calm"),
    ("Light Awash",    "calm"),
    ("Northern Glade", "calm"),

    ("Cipher",         "focus"),
    ("Inspired",       "focus"),
    ("Motivator",      "focus"),
    ("Tech Live",      "focus"),
    ("Presenterator",  "focus"),

    ("Wholesome",      "warm"),
    ("Past Sadness",   "warm"),
    ("Funkorama",      "warm"),
    ("Adding the Sun", "warm"),
]


def _ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


CACHE = BGM_DIR / "_pieces_cache.json"
CACHE_TTL = 7 * 86400  # 曲库清单很少变，缓存 7 天


def load_pieces(force=False):
    """
    拉取线上曲库清单（1442 首，939KB）。
    重要：这个请求实测要 100 秒左右（服务器慢），
    所以必须缓存到本地，绝不能每下一首曲就重新拉一次。
    """
    import time
    if not force and CACHE.exists():
        age = time.time() - CACHE.stat().st_mtime
        if age < CACHE_TTL:
            print(f"[cache] 使用本地曲库清单（{age/86400:.1f} 天前缓存）")
            return json.loads(CACHE.read_text(encoding="utf-8"))
    print("[net] 下载曲库清单（约 100 秒，请耐心）...", flush=True)
    req = urllib.request.Request(PIECES_URL, headers=UA)
    data = urllib.request.urlopen(req, timeout=300, context=_ctx()).read()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(data)
    return json.loads(data.decode("utf-8", "ignore"))


def secs(s):
    try:
        h, m, ss = (s or "").split(":")
        return int(h) * 3600 + int(m) * 60 + int(ss)
    except Exception:
        return -1


def find_piece(pieces, title):
    t = title.strip().lower()
    for p in pieces:
        if p["title"].strip().replace("\r", "").replace("\n", "").lower() == t:
            return p
    return None


def download(piece, dest_raw, timeout=600):
    """
    下载整首 mp3。服务器带宽不稳（实测 9~60 KB/s），超时放宽到 600s。
    边下边写，每 1MB 打个点，方便判断是真在跑还是卡死了。
    """
    import time
    url = DL_URL + urllib.parse.quote(piece["filename"])
    req = urllib.request.Request(url, headers=UA)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        last_mark = 0
        with open(dest_raw, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if got - last_mark >= 1048576:
                    last_mark = got
                    el = max(0.1, time.time() - t0)
                    spd = got / 1024 / el          # KB/s
                    tail = f" / {total/1048576:.1f}MB" if total else ""
                    print(f"    {got/1048576:.1f}MB{tail}  {spd:.0f} KB/s", flush=True)
    return got


def trim(src, dst, duration=90, skip=None):
    """用 ffmpeg 截取片段并重编码到 128kbps"""
    import imageio_ffmpeg
    import subprocess
    exe = imageio_ffmpeg.get_ffmpeg_exe()

    total = probe_duration(src)
    if skip is None:
        # 超长曲（如 Ambiment 22:53）从头截会拿到大段铺垫，改从 1/3 处取
        skip = int(total / 3) if total > 600 else 5
    skip = max(0, min(skip, max(0, int(total) - 20)))

    cmd = [exe, "-y", "-v", "error", "-ss", str(skip), "-i", str(src),
           "-t", str(duration), "-acodec", "libmp3lame", "-b:a", "128k",
           "-ar", "44100", "-ac", "2", str(dst)]
    subprocess.run(cmd, check=True, capture_output=True)
    return skip


def probe_duration(path):
    import imageio_ffmpeg
    import subprocess
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    r = subprocess.run([exe, "-i", str(path)], capture_output=True,
                       text=True, encoding="utf-8", errors="ignore")
    for line in (r.stderr or "").splitlines():
        if "Duration:" in line:
            part = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = part.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"moods": MOODS, "tracks": []}


def save_manifest(m):
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_search(args):
    pieces = load_pieces()
    q = args.search.lower()
    hits = [p for p in pieces
            if q in p["title"].lower()
            or q in (p.get("instruments") or "").lower()
            or q in (p.get("description") or "").lower()]
    if args.exact:
        hits = [p for p in hits if p["title"].strip().replace("\r", "").lower() == q]
    print(f"命中 {len(hits)} 首：\n")
    for p in hits[:args.limit]:
        t = p["title"].strip().replace("\r", "")
        L = secs(p.get("length"))
        feel = (p.get("feel") or "").replace("\r", "").strip()
        inst = (p.get("instruments") or "").replace("\r", "").strip()
        print(f"  {L//60}:{L%60:02d}  {t[:32]:32s} | {feel[:30]:30s} | {inst[:44]}")


def cmd_fetch(args, pieces=None):
    pieces = pieces or load_pieces()
    man = load_manifest()
    # 临时文件放系统 temp，不放 BGM_DIR/_raw：
    # 沙箱会阻止删除技能目录下的文件（SAFE_DELETE_FAIL_CLOSED），
    # 导致 _raw 里堆满几十上百 MB 的中间文件清不掉。
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="bgm_"))

    names = [n.strip() for n in args.fetch.split(",") if n.strip()]
    for name in names:
        p = find_piece(pieces, name)
        if not p:
            print(f"[跳过] 线上找不到: {name}")
            continue
        title = p["title"].strip().replace("\r", "").replace("\n", "")
        mood = args.mood or "upbeat"
        out = BGM_DIR / mood
        out.mkdir(parents=True, exist_ok=True)
        dst = out / f"{title}.mp3"

        if dst.exists() and not args.force:
            print(f"[已有] {mood}/{title}.mp3")
        else:
            raw = tmp / f"{p['filename']}"
            print(f"[下载] {title} ...", end=" ", flush=True)
            n = download(p, raw)
            print(f"{n/1048576:.1f}MB", end=" ", flush=True)
            skip = trim(raw, dst, duration=args.duration)
            print(f"-> 截取 {skip}s 起 {args.duration}s")
            try:
                raw.unlink()
            except Exception:
                pass

        # 登记
        entry = {
            "file": f"{mood}/{title}.mp3",
            "title": title,
            "mood": mood,
            "feel": (p.get("feel") or "").replace("\r", "").strip(),
            "instruments": (p.get("instruments") or "").replace("\r", "").strip(),
            "duration": args.duration,
            "credit": f'"{title}" Kevin MacLeod (incompetech.com) '
                      f'Licensed under Creative Commons: By Attribution 4.0',
        }
        man["tracks"] = [t for t in man["tracks"] if t["file"] != entry["file"]]
        man["tracks"].append(entry)

    man["moods"] = MOODS
    save_manifest(man)
    print(f"\n曲库现有 {len(man['tracks'])} 首 -> {MANIFEST}")


def cmd_curate(args):
    # 曲库清单只拉一次，然后复用给所有曲目（否则每首都等 100 秒）
    pieces = load_pieces()
    for title, mood in CURATED:
        args.fetch = title
        args.mood = mood
        cmd_fetch(args, pieces=pieces)
    # 清掉旧的平铺文件（Carefree.mp3 / Wallpaper.mp3 已归入 upbeat/）
    for old in ("Carefree.mp3", "Wallpaper.mp3"):
        f = BGM_DIR / old
        if f.exists():
            try:
                f.unlink()
                print(f"[清理] 旧文件 {old}")
            except Exception:
                pass


def cmd_list(args):
    man = load_manifest()
    if not man["tracks"]:
        print("曲库为空，先跑 --curate")
        return
    for mood, desc in MOODS.items():
        ts = [t for t in man["tracks"] if t["mood"] == mood]
        if not ts:
            continue
        print(f"\n=== {mood}（{desc}）{len(ts)} 首 ===")
        for t in ts:
            print(f"  {t['title'][:28]:28s} {t['feel'][:34]:34s} {t['instruments'][:36]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", help="线上搜索关键词")
    ap.add_argument("--exact", action="store_true", help="精确匹配曲名")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--fetch", help="下载曲目，逗号分隔多个")
    ap.add_argument("--mood", choices=list(MOODS), help="归入的情绪包")
    ap.add_argument("--duration", type=int, default=90, help="截取时长（秒）")
    ap.add_argument("--force", action="store_true", help="已存在也重新下载")
    ap.add_argument("--curate", action="store_true", help="按内置精选清单批量重建")
    ap.add_argument("--list", action="store_true", help="查看当前曲库")
    args = ap.parse_args()

    if args.search:
        cmd_search(args)
    elif args.curate:
        cmd_curate(args)
    elif args.fetch:
        cmd_fetch(args)
    elif args.list:
        cmd_list(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
