#!/usr/bin/env python3
"""fx.py — remix toolkit for the Athena projection-mapping clips.

One command, any number of steps, applied left to right:

    python3 fx.py in.mp4 out.mp4 pingpong
    python3 fx.py in.mp4 out.mp4 pingpong glitch:amount=0.7
    python3 fx.py in.mp4 out.mp4 kaleido:segments=8,spin=0.2 hueshift:period=12 --repeat 4
    python3 fx.py in.mp4 out.mov fit:w=1920,h=480 --codec hap

Steps and their options (defaults in brackets):

    pingpong                           forward then backward — a seamless loop
    reverse
    speed     factor[1.0] smooth[0]    smooth=1 interpolates frames for slow-mo (slow)
    glitch    amount[0.5] jitter[1]    row tears, RGB-split flicker, noise, frame jitter
    trails    decay[0.95]              light trails / smear
    kaleido   segments[6] zoom[1.0] spin[0.0] drift[0.0]
                                       true radial kaleidoscope; spin in rad/s,
                                       drift roams the sample point over the source
    mirror4   from[tl]                 quadrant mirror: tl tr bl br center
    tile      cols[2] rows[2] mirror[1]
                                       grid of the clip; mirrored cells tile seamlessly
    hueshift  period[8] sat[1.2]       hue cycles once every `period` seconds
    strobe    rate[4] duty[0.15]       inverts the image in short flashes
    invert
    fit       w h mode[cover]          exact section size; mode cover|contain

Global options:  --codec x264|prores|hap|lossless   --repeat N   --seed N   --info
"""

import argparse
import json
import math
import os
import shlex
import subprocess
import sys
import tempfile

import numpy as np

FFMPEG = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

ENCODERS = {
    # yuv420p mp4 — plays anywhere, including browsers and projector media players
    "x264": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17",
             "-preset", "medium", "-movflags", "+faststart"],
    # ProRes 422 HQ in .mov — edit-friendly master
    "prores": ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"],
    # HAP Q in .mov — GPU-decoded, what Resolume / MadMapper / TouchDesigner want
    "hap": ["-c:v", "hap", "-format", "hap_q"],
    # FFV1 in .mkv — lossless, used between passes
    "lossless": ["-c:v", "ffv1", "-level", "3", "-pix_fmt", "yuv444p"],
}
# dimension rounding each codec needs (x264 even, hap multiples of 4)
ROUNDING = {"x264": 2, "prores": 2, "hap": 4, "lossless": 1}
INTERMEDIATE = ENCODERS["lossless"]


def sh(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        sys.exit("command failed (%d): %s" % (r.returncode, " ".join(shlex.quote(c) for c in cmd)))
    return r


def probe(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames:format=duration",
        "-of", "json", path])
    d = json.loads(out)
    s = d["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {
        "width": s["width"], "height": s["height"],
        "fps": float(num) / float(den),
        "frames": int(s["nb_read_frames"]),
        "duration": float(d["format"]["duration"]),
    }


def round_filter(n):
    return "" if n <= 1 else "scale=trunc(iw/%d)*%d:trunc(ih/%d)*%d" % (n, n, n, n)


# ---------------------------------------------------------------- filter graphs
# Each builder returns an ffmpeg filtergraph string. Graphs containing ';' use
# split/stack and must run as their own pass; plain chains get merged with ','.

def g_pingpong(src, **_):
    n = probe(src)["frames"]
    # reversed copy drops its first and last frame so neither loop point doubles up
    return ("split[a][b];[b]reverse,trim=start_frame=1:end_frame=%d,setpts=PTS-STARTPTS[r];"
            "[a][r]concat=n=2:v=1:a=0" % (n - 1))


def g_reverse(src, **_):
    return "reverse"


def g_speed(src, factor=1.0, smooth=0, **_):
    fps = probe(src)["fps"]
    chain = "setpts=PTS/%s" % factor
    if int(smooth) and float(factor) < 1:
        chain += ",minterpolate=fps=%s:mi_mode=mci:mc_mode=aobmc:vsbmc=1" % fps
    else:
        chain += ",fps=%s" % fps
    return chain


def g_glitch(src, amount=0.5, jitter=1, seed=7, **_):
    a = max(0.0, min(1.0, float(amount)))
    block_h, rate = 18, 24
    # deterministic per-row-block, per-frame hash -> blocky horizontal tears
    h = "sin(floor(Y/%d)*12.9898+floor(T*%d)*78.233+%s)*43758.5453" % (block_h, rate, seed)
    frac = "(%s-floor(%s))" % (h, h)
    thr = round(1 - 0.3 * a, 3)
    shift = "(gt(%s,%s)*(%s-%s)*W*%s)" % (frac, thr, frac, thr, round(1.2 * a, 3))
    e = "p(mod(X+%s,W),Y)" % shift
    f = ["format=yuv444p", "geq=lum='%s':cb='%s':cr='%s'" % (e, e, e)]
    px = max(1, int(round(14 * a)))
    f.append("rgbashift=rh=%d:bh=%d:enable='gt(random(1),%s)'" % (px, -px, round(1 - 0.6 * a, 3)))
    f.append("noise=alls=%d:allf=t+u" % int(round(40 * a)))
    if int(jitter) and a > 0.3:
        f.append("random=frames=%d:seed=%s" % (int(round(3 + 10 * a)), seed))
    return ",".join(f)


def g_trails(src, decay=0.95, **_):
    return "lagfun=decay=%s" % decay


def g_mirror4(src, **kw):
    frm = kw.get("from", "tl")
    pos = {"tl": "0:0", "tr": "iw/2:0", "bl": "0:ih/2", "br": "iw/2:ih/2",
           "center": "iw/4:ih/4"}[frm]
    return ("crop=iw/2:ih/2:%s,split[a][b];[b]hflip[bh];[a][bh]hstack[top];"
            "[top]split[t1][t2];[t2]vflip[bot];[t1][bot]vstack" % pos)


def g_tile(src, cols=2, rows=2, mirror=1, **_):
    cols, rows, mirror = int(cols), int(rows), int(mirror)
    n = cols * rows
    parts = ["scale=iw/%d:ih/%d,split=%d%s" % (cols, rows, n, "".join("[c%d]" % i for i in range(n)))]
    labels, layout = [], []
    for j in range(rows):
        for i in range(cols):
            k = j * cols + i
            flips = []
            if mirror and i % 2:
                flips.append("hflip")
            if mirror and j % 2:
                flips.append("vflip")
            if flips:
                parts.append("[c%d]%s[d%d]" % (k, ",".join(flips), k))
                labels.append("[d%d]" % k)
            else:
                labels.append("[c%d]" % k)
            layout.append("%s_%s" % ("+".join(["w0"] * i) or "0", "+".join(["h0"] * j) or "0"))
    parts.append("%sxstack=inputs=%d:layout=%s" % ("".join(labels), n, "|".join(layout)))
    return ";".join(parts)


def g_hueshift(src, period=8, sat=1.2, **_):
    return "hue=H=2*PI*t/%s:s=%s" % (period, sat)


def g_strobe(src, rate=4, duty=0.15, **_):
    rate, duty = float(rate), float(duty)
    return "negate=enable='lt(mod(t,%s),%s)'" % (round(1 / rate, 4), round(duty / rate, 4))


def g_invert(src, **_):
    return "negate"


def g_fit(src, w=None, h=None, mode="cover", **_):
    if not (w and h):
        sys.exit("fit needs w and h, e.g. fit:w=1920,h=480")
    if mode == "contain":
        return ("scale=%s:%s:force_original_aspect_ratio=decrease,"
                "pad=%s:%s:(ow-iw)/2:(oh-ih)/2:black" % (w, h, w, h))
    return "scale=%s:%s:force_original_aspect_ratio=increase,crop=%s:%s" % (w, h, w, h)


# ------------------------------------------------------------------ numpy pass

def reflect(v, n):
    """Fold coordinates back into [0, n-1] like a mirror, so sampling never leaves the frame."""
    p = 2 * (n - 1)
    v = np.mod(v, p)
    return np.where(v > n - 1, p - v, v)


def kaleido_pass(src, dst, enc, tail, segments=6, zoom=1.0, spin=0.0, drift=0.0, **_):
    segments, zoom, spin, drift = int(segments), float(zoom), float(spin), float(drift)
    info = probe(src)
    W, H, fps = info["width"], info["height"], info["fps"]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = (W - 1) / 2, (H - 1) / 2
    r = np.hypot(xx - cx, yy - cy) / zoom
    theta = np.arctan2(yy - cy, xx - cx)
    wedge = 2 * math.pi / segments
    animated = spin != 0 or drift != 0

    def sample_map(t):
        th = np.mod(theta + spin * t, wedge)
        th = np.minimum(th, wedge - th)          # mirror inside the wedge
        ox = drift * W / 2 * math.sin(0.37 * t)  # slow roam of the sample point
        oy = drift * H / 2 * math.cos(0.23 * t)
        sx = reflect(cx + ox + r * np.cos(th), W)
        sy = reflect(cy + oy + r * np.sin(th), H)
        return np.rint(sy).astype(np.intp), np.rint(sx).astype(np.intp)

    dec = subprocess.Popen(FFMPEG + ["-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    vf = ["-vf", tail] if tail else []
    encp = subprocess.Popen(FFMPEG + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                                      "-r", str(fps), "-i", "-", "-an", *vf, *enc, dst],
                            stdin=subprocess.PIPE)
    fsize = W * H * 3
    n = 0
    static = None if animated else sample_map(0)
    while True:
        buf = dec.stdout.read(fsize)
        if len(buf) < fsize:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        iy, ix = static if static is not None else sample_map(n / fps)
        encp.stdin.write(frame[iy, ix].tobytes())
        n += 1
    encp.stdin.close()
    dec.wait()
    if encp.wait():
        sys.exit("kaleido: encoder failed")


GRAPHS = {
    "pingpong": g_pingpong, "reverse": g_reverse, "speed": g_speed, "glitch": g_glitch,
    "trails": g_trails, "mirror4": g_mirror4, "tile": g_tile, "hueshift": g_hueshift,
    "strobe": g_strobe, "invert": g_invert, "fit": g_fit,
}
PYTHON_STEPS = {"kaleido": kaleido_pass}


# ------------------------------------------------------------------ driver

def parse_step(spec):
    name, _, opts = spec.partition(":")
    if name not in GRAPHS and name not in PYTHON_STEPS:
        sys.exit("unknown step %r — see --help" % name)
    kw = {}
    for pair in filter(None, opts.split(",")):
        k, _, v = pair.partition("=")
        kw[k] = v
    return name, kw


def plan(steps, src, seed):
    """Group consecutive plain filter chains into one ffmpeg pass; split/stack
    graphs and numpy steps run alone. Builders that need frame counts probe the
    *original* source, which is fine because every earlier step keeps timing
    except pingpong/speed/reverse — those are handled by probing per pass."""
    groups = []
    for name, kw in steps:
        if name in PYTHON_STEPS:
            groups.append(("py", name, kw))
        else:
            groups.append(("vf", name, kw))
    return groups


def run(src, dst, steps, codec, repeat, seed):
    groups = plan(steps, src, seed)
    with tempfile.TemporaryDirectory(prefix="fx-") as td:
        cur = src
        i = 0
        while i < len(groups):
            kind, name, kw = groups[i]
            last = i == len(groups) - 1
            if kind == "py":
                out = dst if last else os.path.join(td, "step%d.mkv" % i)
                enc = ENCODERS[codec] if last else INTERMEDIATE
                tail = round_filter(ROUNDING[codec]) if last else ""
                PYTHON_STEPS[name](cur, out, enc, tail, **kw)
                cur = out
                i += 1
                continue
            # merge following plain chains into this pass
            chain = [GRAPHS[name](cur, seed=seed, **kw)]
            j = i + 1
            if ";" not in chain[0]:
                while j < len(groups) and groups[j][0] == "vf":
                    g = GRAPHS[groups[j][1]](cur, seed=seed, **groups[j][2])
                    if ";" in g:
                        break
                    chain.append(g)
                    j += 1
            last = j == len(groups)
            out = dst if last else os.path.join(td, "step%d.mkv" % i)
            enc = ENCODERS[codec] if last else INTERMEDIATE
            tail = round_filter(ROUNDING[codec]) if last else ""
            vf = ",".join(chain + ([tail] if tail else []))
            sh(FFMPEG + ["-i", cur, "-an", "-vf", vf, *enc, out])
            cur = out
            i = j
        if repeat > 1:
            looped = os.path.join(td, "looped" + os.path.splitext(dst)[1])
            sh(FFMPEG + ["-stream_loop", str(repeat - 1), "-i", dst, "-c", "copy", looped])
            os.replace(looped, dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output", nargs="?")
    ap.add_argument("steps", nargs="*", help="effect[:key=val,key=val] ...")
    ap.add_argument("--codec", default="x264", choices=sorted(ENCODERS))
    ap.add_argument("--repeat", type=int, default=1, help="loop the finished clip N times")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--info", action="store_true", help="print the input's dimensions, fps, frames")
    a = ap.parse_args()
    if a.info or not a.output:
        print(json.dumps(probe(a.input), indent=2))
        return
    if not a.steps:
        sys.exit("give at least one step, e.g. pingpong")
    run(a.input, a.output, [parse_step(s) for s in a.steps], a.codec, a.repeat, a.seed)
    print(json.dumps({"output": a.output, **probe(a.output)}))


if __name__ == "__main__":
    main()
