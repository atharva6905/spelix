# Squat test-clip corpus

Gathered 2026-05-25 for the oblique-camera / monocular-3D investigation
(`docs/audit/2026-05-25-squat-oblique-3d-investigation.md`). For validating pose
models across camera angles. Re-downloadable from the YouTube IDs below via
`yt-dlp` (the .mp4 binaries are local scratch — not necessarily git-tracked; see
the repo's policy on large fixtures).

Fetch command pattern (video-only, no audio needed for pose):
```
uv run python -m yt_dlp --js-runtimes node -f "best[height<=720]/best" \
  -o "e2e/fixtures/<name>-%(id)s.%(ext)s" "https://www.youtube.com/shorts/<id>"
```

## Usable clips (by camera angle)

| file | YouTube id | angle | res / dur | notes |
|---|---|---|---|---|
| `olympic-squat-sample.mp4` | (user-provided) | **front-oblique ~45°** | 360p / 18s | 260 kg ATG squat, competition. Primary oblique test clip. |
| `yt-sq2-i7J5h7BJ07g.mp4` | i7J5h7BJ07g | **front-oblique** | **720p** | Best quality; tightest MeTRAbs 3D (<2% bone CV). |
| `yt-short-Kw7sEq6A1a4.mp4` | Kw7sEq6A1a4 | front-oblique | 360p / 57s | Front squat (front-rack arms harder). |
| `yt-short-EzvnMZuxGWw.mp4` | EzvnMZuxGWw | oblique | 360p / 60s | Back squat, coach in frame. |
| `yt-squat-ZBVhGwwWpCw.mp4` | ZBVhGwwWpCw | front-oblique | 360p / 43s | Back squat. |
| `yt-squat-tHOES61y1dw.mp4` | tHOES61y1dw | front/oblique | 360p / 71s | Commercial gym, dimmer. |
| `yt-squat-BPPFMUu9NFQ.mp4` | BPPFMUu9NFQ | **clean side** | 360p / 53s | Sagittal baseline / plate-occlusion case. |
| `yt-squat-a06n7KysFS8.mp4` | a06n7KysFS8 | **rear** | 360p / 29s | Dark home gym; tests rear angle. |
| `yt-short-YYhRCEVT2pI.mp4` | YYhRCEVT2pI | side | 360p / 15s | "285 form check"; clean. |
| `yt-short-8M7HVKI7u08.mp4` | 8M7HVKI7u08 | side-ish | 202×360 / 18s | Narrow framing. |
| `atharva-squat.mov` | (own) | side | — | Original pure-side fixture (plate occludes the bottom). |

## Rejected (downloaded, not useful)
- `yt-short-9dkg-I3L-E0` — split-screen talking-head.
- `yt-short-hscOjLrW60c` — first-person POV of own feet.
- `yt-short-PPmvh7gBTi0` — legs-only stance demo (no full-body squat).
- `yt-short-u8keG4_6TgE` — subject small / obstructed by rack.

## Notes
- 360p is adequate for pose testing, but **higher resolution measurably tightens MeTRAbs 3D** (720p → <2% bone-length CV vs 4–10% at 360p). Prefer ≥720p when re-gathering; needs `--remote-components ejs:github` for yt-dlp to unlock >360p YouTube formats.
- Some clips are AV1 (yt-dlp format 398); OpenCV decoded them fine here.
