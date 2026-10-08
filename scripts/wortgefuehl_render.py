#!/usr/bin/env python3
import base64
import json
import os
import time
import sys
import pathlib
import re
import shlex
import subprocess
import tempfile
import urllib.parse

BASE = os.environ.get("WG_CLOUD_BASE", "").rstrip("/")
OIDC = os.environ.get("WG_OIDC_TOKEN", "")
JOB_FILE = os.environ.get("WG_JOB_FILE", "").strip()

def refresh_oidc():
    global OIDC
    endpoint = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not endpoint or not request_token:
        return OIDC
    try:
        part = OIDC.split(".")[1]
        expires = float(json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))).get("exp", 0))
    except (ValueError, IndexError, TypeError):
        expires = 0
    if expires > time.time() + 120:
        return OIDC
    separator = "&" if "?" in endpoint else "?"
    response = subprocess.run([
        "curl", "-fsS", "--retry", "2", "--connect-timeout", "20", "--max-time", "60",
        "-H", "Authorization: bearer " + request_token,
        endpoint + separator + "audience=wortgefuehl-autopilot"
    ], capture_output=True, text=True, check=False)
    if response.returncode:
        raise RuntimeError("GitHub OIDC token refresh failed.")
    OIDC = str(json.loads(response.stdout).get("value") or "")
    if not OIDC:
        raise RuntimeError("GitHub returned an empty OIDC token.")
    print("::add-mask::" + OIDC, flush=True)
    return OIDC

def curl_base(method="GET"):
    refresh_oidc()
    return [
        "curl", "-sS", "--retry", "2", "--connect-timeout", "20",
        "--max-time", "300", "-X", method,
        "-H", "Authorization: Bearer " + OIDC,
        "-H", "User-Agent: GitHubActions-Wortgefuehl/1.0",
    ]

def run(args):
    safe_args = ["Authorization: [REDACTED]" if str(x).lower().startswith("authorization:") else str(x) for x in args]
    print("+", " ".join(shlex.quote(x) for x in safe_args), flush=True)
    result = subprocess.run([str(x) for x in args], check=False)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): " + " ".join(shlex.quote(x) for x in safe_args))

def probe_duration(path):
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr or "")
    if not match:
        raise RuntimeError("Videodauer konnte mit ffmpeg nicht ermittelt werden.")
    h, m, s = match.groups()
    return max(0.0, int(h) * 3600 + int(m) * 60 + float(s))

def next_job():
    with tempfile.NamedTemporaryFile(prefix="wg-claim-", suffix=".json", delete=False) as tmp:
        path = pathlib.Path(tmp.name)
    try:
        proc = subprocess.run(
            curl_base("POST") + ["-o", str(path), "-w", "%{http_code}", BASE + "/api/render/claim"],
            capture_output=True, text=True, check=False
        )
        code = proc.stdout.strip()
        if code == "204":
            return None
        if code != "200":
            detail = path.read_text("utf-8", errors="replace")[:1200] if path.exists() else proc.stderr[:1200]
            raise RuntimeError(f"Render claim HTTP {code}: {detail}")
        return json.loads(path.read_text("utf-8")).get("job")
    finally:
        path.unlink(missing_ok=True)

def cloud_asset(key, target):
    encoded = urllib.parse.quote(str(key), safe="/")
    run(curl_base("GET") + [
        "-fL", "-o", str(target),
        BASE + "/api/render/asset/" + encoded
    ])

def public_file(url, target):
    if not str(url).startswith("https://"):
        return False
    try:
        subprocess.run([
            "curl", "-fsSL", "--retry", "2", "--connect-timeout", "20", "--max-time", "120",
            "-H", "User-Agent: GitHubActions-Wortgefuehl/1.0",
            "-o", str(target), str(url)
        ], check=True)
        return pathlib.Path(target).stat().st_size > 1000
    except Exception as exc:
        print("Background download fallback:", exc, flush=True)
        return False

def parse_vtt_time(value):
    h, m, rest = value.split(":")
    s, ms = rest.split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

def ass_time(seconds):
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        s += 1
        cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def vtt_to_ass(vtt_path, ass_path, shift=1.5):
    text = pathlib.Path(vtt_path).read_text("utf-8", errors="replace")
    cues = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" not in line:
            i += 1
            continue
        start_raw, end_raw = [x.strip().split(" ")[0] for x in line.split("-->", 1)]
        start = parse_vtt_time(start_raw) + shift
        end = parse_vtt_time(end_raw) + shift
        i += 1
        body = []
        while i < len(lines) and lines[i].strip():
            body.append(re.sub(r"<[^>]+>", "", lines[i].strip()))
            i += 1
        caption = " ".join(body).replace("{", "(").replace("}", ")").strip()
        if caption:
            cues.append((start, end, caption))
        i += 1

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,DejaVu Sans,58,&H00FFFFFF,&H000000FF,&H00101010,&H76000000,-1,0,0,0,100,100,0,0,3,2,0,5,110,110,240,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events = []
    for start, end, caption in cues:
        caption = caption.replace("\n", " ").replace(",", "\,")
        events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{caption}")
    pathlib.Path(ass_path).write_text(header + "\n".join(events) + "\n", "utf-8")

def create_tts(payload, work):
    script = str(payload.get("script") or "").strip()
    voice = str(payload.get("voice") or "de-DE-KatjaNeural").strip()
    rate = str(payload.get("voice_rate") or "-5%").strip()
    voice_mp3 = work / "voice.mp3"
    voice_vtt = work / "voice.vtt"

    run([
        "edge-tts", "--voice", voice, "--rate=" + rate,
        "--text", script, "--write-media", voice_mp3,
        "--write-subtitles", voice_vtt
    ])
    dur = probe_duration(voice_mp3)
    target = max(62.0, float(payload.get("target_duration_min") or 62))
    if dur < target:
        slower = "-15%"
        print(f"Voice too short ({dur:.1f}s). Re-render at {slower}.", flush=True)
        run([
            "edge-tts", "--voice", voice, "--rate=" + slower,
            "--text", script, "--write-media", voice_mp3,
            "--write-subtitles", voice_vtt
        ])
        dur = probe_duration(voice_mp3)
    return voice_mp3, voice_vtt, dur

def build_visual(payload, work, voice_duration):
    cover = work / "cover.jpg"
    fallback = str(payload.get("fallback_image_key") or payload.get("cover_key") or "")
    if not fallback:
        raise RuntimeError("Cover/Fallback fehlt im Renderauftrag.")
    cloud_asset(fallback, cover)

    bg_source = work / "background.mp4"
    has_video = public_file(str(payload.get("background_video_url") or ""), bg_source)

    intro = work / "intro.mp4"
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-i", cover, "-t", "1.5",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", intro
    ])

    main = work / "main.mp4"
    main_dur = max(voice_duration + 1.0, 62.0)
    if has_video:
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1", "-i", bg_source, "-t", f"{main_dur:.3f}",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,eq=brightness=0.01:saturation=1.08,format=yuv420p",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", main
        ])
    else:
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", cover, "-t", f"{main_dur:.3f}",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,zoompan=z='min(zoom+0.0007,1.08)':d=1:s=1080x1920:fps=30,format=yuv420p",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", main
        ])

    listing = work / "concat.txt"
    listing.write_text(
        "file '" + str(intro).replace("'", "'\\''") + "'\n" +
        "file '" + str(main).replace("'", "'\\''") + "'\n",
        "utf-8"
    )
    base = work / "base.mp4"
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", listing,
        "-c", "copy", base
    ])
    return base

def mix_and_subtitle(payload, work, base, voice_mp3, voice_vtt):
    music = work / "music.mp3"
    music_key = str(payload.get("music_key") or "")
    if music_key:
        cloud_asset(music_key, music)

    ass = work / "captions.ass"
    vtt_to_ass(voice_vtt, ass, shift=1.5)
    output = work / "final.mp4"

    if music.exists():
        audio_filter = (
            "[1:a]adelay=1500|1500,volume=1.0[voice];"
            "[2:a]volume=0.075[music];"
            "[voice][music]amix=inputs=2:duration=first:dropout_transition=2[a]"
        )
        inputs = [
            "-i", base, "-i", voice_mp3,
            "-stream_loop", "-1", "-i", music
        ]
    else:
        audio_filter = "[1:a]adelay=1500|1500,volume=1.0[a]"
        inputs = ["-i", base, "-i", voice_mp3]

    vf = "subtitles=" + str(ass).replace("\\", "\\\\").replace(":", "\\:")
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        *inputs,
        "-filter_complex", audio_filter,
        "-vf", vf,
        "-map", "0:v:0", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-shortest", output
    ])
    return output

def upload_result(job_id, path):
    encoded = urllib.parse.quote(str(job_id), safe="")
    with tempfile.NamedTemporaryFile(prefix="wg-upload-", suffix=".json", delete=False) as tmp:
        result_path = pathlib.Path(tmp.name)
    try:
        proc = subprocess.run(
            curl_base("PUT") + [
                "-f", "-H", "Content-Type: video/mp4",
                "--data-binary", "@" + str(path),
                "-o", str(result_path),
                BASE + "/api/render/complete?job_id=" + encoded
            ],
            capture_output=True, text=True, check=False
        )
        if proc.returncode != 0:
            detail = result_path.read_text("utf-8", errors="replace")[:1200] if result_path.exists() else proc.stderr[:1200]
            raise RuntimeError("Video Rückgabe fehlgeschlagen: " + detail)
        return json.loads(result_path.read_text("utf-8"))
    finally:
        result_path.unlink(missing_ok=True)

def report_failure(job_id, error, retry=False):
    payload = json.dumps({"job_id": job_id, "error": str(error)[:1000], "retry": retry})
    try:
        subprocess.run(
            curl_base("POST") + [
                "-f", "-H", "Content-Type: application/json",
                "--data-binary", payload,
                BASE + "/api/render/fail"
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
    except Exception as exc:
        print("Could not report failure:", exc, flush=True)

def render_job(job):
    job_id = str(job.get("id") or "")
    payload = dict(job.get("payload") or {})
    if not job_id:
        raise RuntimeError("Render job ID fehlt.")
    print("Rendering", job_id, payload.get("platform"), payload.get("brand"), flush=True)

    with tempfile.TemporaryDirectory(prefix="wortgefuehl-render-") as tmp:
        work = pathlib.Path(tmp)
        voice_mp3, voice_vtt, voice_dur = create_tts(payload, work)
        base = build_visual(payload, work, voice_dur)
        output = mix_and_subtitle(payload, work, base, voice_mp3, voice_vtt)
        final_dur = probe_duration(output)
        if final_dur < 61.0:
            raise RuntimeError(f"Gerendertes Video ist mit {final_dur:.1f}s zu kurz.")
        result = upload_result(job_id, output)
        print("Uploaded", job_id, f"{final_dur:.1f}s", result.get("key"), flush=True)

def initial_job():
    if not JOB_FILE:
        return None
    path = pathlib.Path(JOB_FILE)
    if not path.is_file():
        return None
    data = json.loads(path.read_text("utf-8"))
    return data.get("job") if isinstance(data, dict) else None

def main():
    if not BASE or not OIDC:
        raise RuntimeError("WG_CLOUD_BASE oder WG_OIDC_TOKEN fehlt.")

    rendered = 0
    job = initial_job()
    while rendered < 4:
        if job is None:
            job = next_job()
        if not job:
            print("No pending render jobs.", flush=True)
            break
        job_id = str(job.get("id") or "")
        try:
            render_job(job)
        except Exception as exc:
            report_failure(job_id, exc)
            raise
        rendered += 1
        job = None
    print("Rendered jobs:", rendered, flush=True)

if __name__ == "__main__":
    if "--release-initial-job" in sys.argv:
        job = initial_job()
        if job:
            report_failure(str(job["id"]), "GitHub setup or workflow stopped before completion.", retry=True)
    else:
        main()
