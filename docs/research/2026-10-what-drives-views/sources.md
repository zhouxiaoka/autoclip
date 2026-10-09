# Sources · AutoClip Research Note #1 (2026-10-09)

All metrics are **snapshots at fetch time** (UTC+8, 2026-10-09). They are copied from our working files and have not been re-fetched. X metrics are `impression_count` / `like_count` / `bookmark_count` / `media.view_count` as returned by X's read-only API. `view_count` merges views when a video is reused. YouTube metrics come from public pages read with `yt-dlp` (no cookies, proxy or login).

**URL note.** X URLs are copied exactly as recorded. For YouTube, our working files store video IDs. Batch 2 records links as `https://www.youtube.com/shorts/<id>`, so we built Shorts URLs the same way from the IDs in Batches 2–4. The two long videos use `https://www.youtube.com/watch?v=<id>`. Please spot-check these before publishing.

**Figures.** Case figures C1–C23 (`figures/case-*.jpg`) contain stills from third-party public posts, used for commentary and research with attribution (credits table at the end of this file). Charts (`figures/fig1–5,7-*-dark.png`; light variants without `-dark`) are generated from the numbers below by `src/charts.py`. Thumbnail overviews (`figures/fig11-r3-ab-pairs.jpg`, `figures/figA-*.jpg`) are stills from **our own renders** of three segments of a public interview: Dwarkesh Podcast, "Jensen Huang – Will Nvidia's moat persist?", 2026-04-15, 1080p taken from the publisher's public Substack post.

## Internal source files (AutoClip research workspace)

| File | What it contains |
|---|---|
| `packaging-benchmark/editing-research/synthesis.md` | Cross-batch synthesis: what predicts performance, Top-10 techniques, A/B hypotheses H10–H18 |
| `packaging-benchmark/editing-research/techniques.md` | Technique tables X/Y/G/E per batch, "don't copy" lists, proposed rules R21–R45 |
| `packaging-benchmark/editing-research/batch1-news-doc.md` | News + documentary (X), fetched 05:18–05:35 |
| `packaging-benchmark/editing-research/batch2-variety-film.md` | Variety + film (YouTube 06:25–06:28; X 05:50–05:53) |
| `packaging-benchmark/editing-research/batch3-gaming-live.md` | Gaming + live facecam (YouTube 07:06–07:21) |
| `packaging-benchmark/editing-research/batch4-vlog-editorial.md` | Vlog + editorial (YouTube 07:33–07:47) |
| `packaging-benchmark/findings.md`, `case-library.md` | Interview/podcast clips on X: C01–C12, c1–c3 (~03:30), N01–N15 (04:18), R2-01–R2-14 (05:05 / 06:30), R3-01–R3-13 (07:16–07:19); 44-clip motion measurement |
| `packaging-benchmark/playbook.md` | Packaging rules, round-by-round gap tables, hypotheses |
| `packaging-benchmark/renders/README.md`, `renders/qa/*` | Our renders R0–R3 (build/QA details moved to `cut-build-in-public.md`) |
| `input-filter-v1/README.md`, `rubric.md` | Selection radar v1 and its scoring rubric |
| `editing-research/board_batch1–4.jpg` | Overview boards **containing third-party frames: not published**, used only for internal analysis |

## Posts cited in the article

### Distribution confound (X, ~04:18)
| Case | URL | Impressions / likes / saves / views |
|---|---|---|
| N14 Nick Sortor (same video + same copy as N15) | https://x.com/nicksortor/status/2105022267616788722 | 141,835 / 7,754 / 293 / 73,655 |
| N15 AmericanRisingQ | https://x.com/AmericanRisingQ/status/2105037531570217023 | 386 / 5 / 0 / 158 |
| N01 Huberman (top-level post) | https://x.com/hubermanlab/status/2107247283536560173 | 295,248 / 4,378 / 1,746 / 134,468 |
| N02 Huberman (reply in the same thread) | https://x.com/hubermanlab/status/2107248259106578835 | 22,025 / 153 / 45 / 5,958 |
| R2-01 XAngus (same video as R2-02) | https://x.com/XAngus/status/2107085391736230380 | 6,557 impressions |
| R2-02 SonicAIWizard | https://x.com/SonicAIWizard/status/2107375702257303644 | 688 impressions |

### Interview / podcast & design-forward accounts (X)
| Case | URL | Metrics |
|---|---|---|
| N04 20VC "Every seed investment is an option bet." | https://x.com/HarryStebbings/status/2107160639504335164 | 283,526 imp / 131 likes / 103 saves / 85,681 views; 66 quotes |
| N05 20VC Venky (low) | https://x.com/HarryStebbings/status/2107497862149849121 | 16,752 imp / 3,843 views (another low post: 2107199646695080063, 15,374 imp) |
| N06 TBPN Tobi Lütke (85 s) | https://x.com/tbpn/status/2107257100485435610 | 54,897 imp |
| N07 TBPN Mead (224 s, low) | https://x.com/tbpn/status/2107944150993871236 | 13,650 imp |
| N10 WOLF Financial (90 s) | https://x.com/WOLF_Financial/status/2101775769332813830 | 62,298 imp / 15,129 views |
| N11 WOLF Financial (247 s, low) | https://x.com/WOLF_Financial/status/2107979713834893677 | 14,567 imp / 3,707 views |
| R2-03 XAngus (5.0 cuts/min) | https://x.com/XAngus/status/2107678824892895673 | 7,825 imp |
| R2-04 XAngus (20.2 cuts/min) | https://x.com/XAngus/status/2107467373741850852 | 6,165 imp |
| R2-14 XAngus 27-min bilingual full version | https://x.com/XAngus/status/2105116743383634356 | 77,329 imp / 651 saves / 282 reposts |
| R2-10 math_fournity (speculation hook, don't copy) | https://x.com/math_fournity/status/2096039001891414172 | 72,082 imp |
| R3-01 WIRED (playful claim) | https://x.com/WIRED/status/2102430525554135468 | 29,306 imp / 51 likes (1.7‰) |
| R3-02 WIRED (suspense question, low) | https://x.com/WIRED/status/2095475338256044361 | 30,906 imp / 11 likes (0.4‰) |
| R3-05 Colin and Samir "content calendars" | https://x.com/ColinandSamir/status/2100673598986002504 | 11,368 imp / 108 saves (9.5‰) |
| R3-06 Colin and Samir aphorism (low) | https://x.com/ColinandSamir/status/2102464227302621692 | 3,109 imp |
| R3-07 a16z Kanye story | https://x.com/a16z/status/2106814432273973577 | 165,894 imp |
| R3-08 a16z (same session, low) | https://x.com/a16z/status/2106839724698873907 | 35,130 imp |
| R3-10 歸藏 AI 早报 | https://x.com/op7418/status/2108148604447883464 | 55,967 imp / 305 saves (5.4‰) |
| R3-12 Sixth Tone HYROX | https://x.com/SixthTone/status/2099890988307161175 | 49,537 imp |
| R3-13 Sixth Tone (same package, low) | https://x.com/SixthTone/status/2105270155953738185 | 3,013 imp |

Motion measurement (44 clips: C/N/c/R2): vertical-native median 8.8 hard cuts/min vs horizontal 3.5; ≥100K-impression group 3.8/min vs <1K group 4.5/min (`case-library.md`).

### Batch 1 — news + documentary (X, fetched 05:18–05:35)
| Case | URL | Imp / likes / saves / views | Cuts/min | Note |
|---|---|---|---|---|
| ND01 AJ+ | https://x.com/ajplus/status/2108091271839469626 | 19,527 / 45 / 6 / 34,934 | 10.9 | 14 h |
| ND02 AJ+ | https://x.com/ajplus/status/2108271483499987050 | 6,943 / 65 / 7 / 1,425 | 7.0 | 2 h, weak |
| ND03 AJ+ | https://x.com/ajplus/status/2107910329187680286 | 37,529 / 60 / 15 / 30,710 | 16.5 | |
| ND04 60 Minutes "three kinds of jobs" | https://x.com/60Minutes/status/2107962677603553392 | 95,064 / 297 / 165 / 36,396 | 7.6 | |
| ND04b 60 Minutes | https://x.com/60Minutes/status/2107956979712803013 | 39,602 / 97 / 52 / 14,373 | — | |
| ND04c 60 Minutes | https://x.com/60Minutes/status/2107965347844231200 | 47,927 / 191 / 69 / 21,900 | — | |
| ND05 60 Minutes | https://x.com/60Minutes/status/2108228361726369982 | 10,457 / 18 / 3 / 3,803 | 5.2 | 5 h, weak |
| ND06 60 Minutes ⚠ | https://x.com/60Minutes/status/2107584936550998497 | 279,085 / 29 / 4 / 198,642 | 1.3 | excluded (like rate 0.01%) |
| ND07 Vox (controversy) | https://x.com/voxdotcom/status/2107560265936150677 | 283,872 / 48 / 135 / 113,451; 275 replies, 144 quotes | 5.3 | |
| ND08 Vox | https://x.com/voxdotcom/status/2107900026915828119 | 14,122 / 70 / 17 / 4,060 | 9.4 | |
| ND09 WSJ Haaland (silent) | https://x.com/WSJ/status/2108233694049612272 | 58,508 / 42 / 7 / 15,637 | 57.7 | 5 h |
| ND10 WSJ | https://x.com/WSJ/status/2108246818211434720 | 55,085 / 9 / 3 / 13,774 | 9.9 | 4 h |
| ND11 WSJ (chart opening) | https://x.com/WSJ/status/2108251137845449118 | 26,519 / 12 / 3 / 3,329 | 12.1 | 4 h |
| ND12 Bloomberg | https://x.com/business/status/2108288136656666870 | 16,317 / 3 / 1 / 1,798 | 0.6 | 1 h, weak |
| DX01 Veritasium aerogel | https://x.com/veritasium/status/2106394965458739276 | 102,007 / 1,230 / 406 / 200,250 | 4.1 | |
| DX02 Veritasium Lenz's law | https://x.com/veritasium/status/2104908923933262248 | 92,218 / 1,467 / 306 / 108,519 | 18.5 | |
| DX03 Veritasium trapping antimatter | https://x.com/veritasium/status/2104589841316896905 | 14,795 / 119 / 18 / 3,333 | 1.6 | punch-in 1.27× |
| DX04 BBC Earth Attenborough | https://x.com/BBCEarth/status/2052860962223333707 | 120,172 / 5,025 / 443 / 70,403 | 0 | |
| DX05 BBC Earth BP3 trailer (287 s) | https://x.com/BBCEarth/status/2107531340702765350 | 70,147 / 1,049 / 112 / 19,717 | 14.9 | |
| DX06 BBC Earth PE20 | https://x.com/BBCEarth/status/2029210758798614903 | 739,788 / 6,329 / 811 / 225,183 | 51 | |
| DX07 NatGeo DART | https://x.com/NatGeo/status/2107834236623294604 | 124,793 / 351 / 24 / 12,527 | 7.6 | |
| DX08 NatGeo Chile miners | https://x.com/NatGeo/status/2103877256053403817 | 209,519 / 325 / 31 / 34,306 | 43.9 | |

Other Veritasium shorts in the opening comparison (views only, URLs not recorded in our files): credit card 27,416; anti-"digital pickpocket" 25,763; black hole 43,330; LED 6,311; WWII machine 4,932; making antimatter 3,714; 100 prisoners 9,576 (12.6 h, excluded).
AJ+ duration buckets (posts ≥12 h): ≤80 s n=3 median 31,664; 81–135 s n=5 median 17,169; >135 s n=6 median 8,254 (range 3,734–15,990). Excluded: 157 s "joy and hope", 86,215 views, 11 h old.

### Batch 2 — variety + film (YouTube 06:25–06:28; X 05:50–05:53)
| Case | URL | Views | Like rate | Dur |
|---|---|---|---|---|
| VZ01 奔跑吧 | https://www.youtube.com/shorts/0HNC_9sctPs | 189,795 | 1.24% | 19 s |
| VZ02 奔跑吧 (frozen-frame number reveal) | https://www.youtube.com/shorts/OLgudm_D57U | 104,109 | 1.50% | 32 s |
| VZ03 奔跑吧 (same day as VZ01, low) | https://www.youtube.com/shorts/Dxd94InEzCk | 6,848 | 3.53% | 32 s |
| VZ05 芒果TV 杨迪 | https://www.youtube.com/shorts/NHk1rB2fbGE | 1,235,680 | 1.27% | 32 s |
| VZ06 芒果TV 应采儿 | https://www.youtube.com/shorts/lGAK1CfY60M | 399,479 | 0.76% | 33 s |
| VZ07 芒果TV (same day, low) | https://www.youtube.com/shorts/m9ugnTFnH8c | 2,089 | 1.44% | 27 s |
| VZ09 iQIYI SuperShow | https://www.youtube.com/shorts/1m0cHZb0Dv4 | 109,826 | 0.72% | 22 s |
| VZ10 iQIYI SuperShow | https://www.youtube.com/shorts/ZEnBCSLN6-E | 29,245 | 1.0% | 27 s |
| VZ11 iQIYI (slogan, low) | https://www.youtube.com/shorts/doJJucXFF58 | 1,541 | 1.82% | 96 s |
| VZ12 iQIYI (slogan, low) | https://www.youtube.com/shorts/J4TuMq0Vjws | 1,735 | 1.84% | 95 s |
| JV01 有吉の壁「40歳」 | https://www.youtube.com/shorts/QylqRoWtN2E | 3,407,645 | 1.23% | 55 s |
| JV02 有吉の壁「46歳」 | https://www.youtube.com/shorts/dhUG3cW6H64 | 2,519,038 | 0.78% | 52 s |
| FT01 TBS VIVANT | https://www.youtube.com/shorts/1p53axf3HHc | 691,440 | 2.08% | 66 s |
| FT02 TBS VIVANT (identical template, low) | https://www.youtube.com/shorts/2ugQuJPQY98 | 88,565 | 1.73% | 75 s |
| KV01/KV02 MBC ⚠ (excluded as evidence) | https://www.youtube.com/shorts/0PaFmuyc7n4 · https://www.youtube.com/shorts/ktqAOHyh3zw | 604,737 / 465,307 | 0.20% / 0.10% | |

Within-account gap on the same day: 28–600× (`batch2-variety-film.md` §0). Face within 1.6 s: higher-view 7/8, lower-view 2/6.

### Batch 3 — gaming + live facecam (YouTube, 07:06–07:21)
| Case | URL | Views | Like rate | Dur |
|---|---|---|---|---|
| has_h3 HasanAbi | https://www.youtube.com/shorts/fmVTTohcUc8 | 1,340,613 | 4.6% | 78 s |
| has_h4 HasanAbi | https://www.youtube.com/shorts/Ezl2GNeqW94 | 1,293,987 | 6.5% | 180 s |
| has_l1 HasanAbi (low) | https://www.youtube.com/shorts/-JInjUmzmQE | 111,361 | 5.7% | 80 s |
| has_l2 HasanAbi (low) | https://www.youtube.com/shorts/wWAkf7MT3kU | 175,004 | 4.3% | 54 s |
| lud_h3 Ludwig | https://www.youtube.com/shorts/1DQZ5d7_ky0 | 2,091,864 | 2.8% | 22 s |
| lud_l3 Ludwig (same day, low) | https://www.youtube.com/shorts/1cEN-DOk4TU | 449,305 | 1.5% | 11 s |
| val_h1 Valkyrae | https://www.youtube.com/shorts/-0ztV0ayp3s | 1,051,103 | 2.1% | 17 s |
| val_l2 Valkyrae (low) | https://www.youtube.com/shorts/1j3Rtvs4DCY | 151,635 | 2.7% | 13 s |
| sum_h1 summit1g | https://www.youtube.com/shorts/BIn7LyWnRnI | 252,369 | 2.3% | 54 s |
| sum_l2 summit1g (low) | https://www.youtube.com/shorts/VXf47nYxr-w | 22,713 | 1.6% | 34 s |
| cas_h1 CaseOh | https://www.youtube.com/shorts/6Gd1CxO4DR0 | 647,271 | 5.2% | 136 s |
| cas_h2 CaseOh | https://www.youtube.com/shorts/wudwDk11UDQ | 411,908 | 4.4% | 133 s |
| cas_l3 CaseOh (low) | https://www.youtube.com/shorts/QeOmUX88s6Y | 84,991 | 5.3% | 90 s |
| jyn_h1 Jynxzi | https://www.youtube.com/shorts/Ys-CZeXgE1A | 2,954,115 | 3.1% | 25 s |
| jyn_h2 Jynxzi (gameplay counter-example) | https://www.youtube.com/shorts/ld5Tv61_BEo | 1,869,114 | 2.3% | 8 s |
| jyn_l2 Jynxzi (−31.2 LUFS) | https://www.youtube.com/shorts/sgzzT9S0S5U | 294,527 | 2.9% | 30 s |

Loudness range −8.4 to −31.2 LUFS; high louder in 4 pairs (Jynxzi +22.5 LU, Kai +10.3, CaseOh +2.0, Valkyrae +1.7) and quieter in 3 (summit −8.5, Mizkif −6.4, Hasan −1.4 to −3.4). Transient density: has_h3 89.6/min vs has_l1 128.5; jyn_h1 112 vs jyn_l2 40.

### Batch 4 — vlog + editorial (YouTube, 07:33–07:47)
| Case | URL | Views | Like rate | Dur |
|---|---|---|---|---|
| GQ 10 Essentials (high) | https://www.youtube.com/shorts/mV4zTaS_i1U | 2,823,259 | 4.0% | 56 s |
| GQ 10 Essentials | https://www.youtube.com/shorts/qh0RZUoRN78 | 1,306,890 | 3.2% | 58 s |
| GQ 10 Essentials (low, 3 posts) | https://www.youtube.com/shorts/cMdHDiI0T_A · https://www.youtube.com/shorts/WTBkJ_Qcths · https://www.youtube.com/shorts/mDUvN4RIlc8 | 6,261–8,562 | 1.2–1.3% | 44–54 s |
| Vogue cover BTS (Dakota Johnson) | https://www.youtube.com/shorts/XuDyyNOuq2Y | 233,704 | 1.2% | 29 s |
| Vogue cover BTS (same day, low) | https://www.youtube.com/shorts/XGmLXK4iGFY | 26,142 | 2.4% | 31 s |
| Dazed PFW Yung Lean | https://www.youtube.com/shorts/NSt7MBhO_tE | 795,694 | 2.3% | 25 s |
| Dazed PFW Rick Owens "I just choose weirdos." | https://www.youtube.com/shorts/494M0N0voWc | 255,579 | 1.2% | 17 s |
| Dazed (low, studio) | https://www.youtube.com/shorts/binFQ1Yar2w · https://www.youtube.com/shorts/Mnj-XWgnKwc | 7,779 / 8,311 | | 20 s / 28 s |
| Ali Abdaal (serif title + number roll) | https://www.youtube.com/shorts/FE6VL7jpfCs | 94,338 | 4.4% | 88 s |
| Ali Abdaal (sponsored, low) | https://www.youtube.com/shorts/II9Oq4bEXLo | 14,596 | 2.5% | 76 s |
| Peter McKinnon talking head | https://www.youtube.com/shorts/42xyZyqF-Hc | 248,442 | 3.6% | 110 s |
| Peter McKinnon podcast clips (low) | https://www.youtube.com/shorts/vNp5fHaKiY8 · https://www.youtube.com/shorts/QqBsYk89nyc | 25,422 / 32,694 | 3.5% / 3.7% | |
| 影视飓风 MediaStorm (long video, first 90 s; technique only) | https://www.youtube.com/watch?v=3iBpUtRPfYs | 406,115 | 0.6% | |

## Our renders (own data, 2026-10-09)
- Softness: Keynote v2 face 112 px (16% of width), Laplacian variance 12.3 → v3 (1080p) 181 px (25%), 40.7.
- Loudness: all R3 renders −14.02 to −14.17 LUFS, TP −1.36 to −1.45 dBTP. Grade: editorial_clip1t p1 8/255 (`qa/grade_r3.json`).
- Image used in renders: H100 photo, CC BY 3.0, 极客湾Geekerwan / Wikimedia Commons. Moore's-law chart, CC BY 4.0, Our World in Data / Wikimedia Commons.

## Selection radar v1
Weights: velocity 25, guest 20, freshness 15, topic 15, hook density 10, format 5, rights 10, whitelist +2. Thresholds: ≥65 clip now, 50–64 watch. Run 2026-10-09 03:36 UTC+8: 354 candidates in ~55 s; 1 clip-now, 26 watch, 327 skip (128 Shorts). Source: `input-filter-v1/README.md`, `rubric.md`.

## Figure credits / References (case figures C1–C23)

Figures C1–C23 contain stills from third-party public posts, reproduced at reduced size for commentary and research, with attribution. All rights remain with the original owners. Every still was extracted on 2026-10-09 (UTC+8) from footage downloaded for this analysis on that day; no new footage was downloaded. Metrics are the snapshot values recorded at fetch time on 2026-10-09. X metrics marked "imp" are impressions; other numbers are views. YouTube URLs were built from video IDs (see `sources.md`).

| Fig. | Account / channel | Platform | Post | Frame at | Metric shown | Supports |
|---|---|---|---|---|---|---|
| C1 | @nicksortor | X | <https://x.com/nicksortor/status/2105022267616788722> | 3 s | 141,835 impressions | Method §2 (distribution confound) |
| C1 | @AmericanRisingQ | X | <https://x.com/AmericanRisingQ/status/2105037531570217023> | 3 s | 386 impressions | Method §2 (distribution confound) |
| C2 | GQ | YouTube | <https://www.youtube.com/shorts/mV4zTaS_i1U> | 5 s | 2,823,259 views | Finding 1 |
| C2 | GQ | YouTube | <https://www.youtube.com/shorts/cMdHDiI0T_A> | 5 s | 6,261–8,562 views | Finding 1 |
| C2 | Vogue | YouTube | <https://www.youtube.com/shorts/XuDyyNOuq2Y> | 2 s | 233,704 views | Finding 1 |
| C2 | Vogue | YouTube | <https://www.youtube.com/shorts/XGmLXK4iGFY> | 2 s | 26,142 views | Finding 1 |
| C3 | HasanAbi | YouTube | <https://www.youtube.com/shorts/fmVTTohcUc8> | 20 s | 1,340,613 views | Finding 1 |
| C3 | HasanAbi | YouTube | <https://www.youtube.com/shorts/-JInjUmzmQE> | 20 s | 111,361 views | Finding 1 |
| C3 | TBS (VIVANT) | YouTube | <https://www.youtube.com/shorts/1p53axf3HHc> | 10 s | 691,440 views | Finding 1 |
| C3 | TBS (VIVANT) | YouTube | <https://www.youtube.com/shorts/2ugQuJPQY98> | 10 s | 88,565 views | Finding 1 |
| C4 | @veritasium | X | <https://x.com/veritasium/status/2106394965458739276> | 0.05 s | 200,250 views | Finding 2 |
| C4 | @veritasium | X | <https://x.com/veritasium/status/2104908923933262248> | 0.05 s | 108,519 views | Finding 2 |
| C4 | @veritasium | X | <https://x.com/veritasium/status/2104589841316896905> | 0.05 s | 3,333 views | Finding 2 |
| C5 | 芒果TV | YouTube | <https://www.youtube.com/shorts/lGAK1CfY60M> | 1.6 s | 399,479 views | Finding 2 |
| C5 | 芒果TV | YouTube | <https://www.youtube.com/shorts/m9ugnTFnH8c> | 1.6 s | 2,089 views | Finding 2 |
| C5 | 奔跑吧 | YouTube | <https://www.youtube.com/shorts/0HNC_9sctPs> | 0.3 s | 189,795 views | Finding 2 |
| C5 | 奔跑吧 | YouTube | <https://www.youtube.com/shorts/Dxd94InEzCk> | 0.3 s | 6,848 views | Finding 2 |
| C6 | Ludwig | YouTube | <https://www.youtube.com/shorts/1DQZ5d7_ky0> | 5 s | 2,091,864 views | Finding 2 |
| C6 | Ludwig | YouTube | <https://www.youtube.com/shorts/1cEN-DOk4TU> | 3 s | 449,305 views | Finding 2 |
| C6 | Valkyrae | YouTube | <https://www.youtube.com/shorts/-0ztV0ayp3s> | 3 s | 1,051,103 views | Finding 2 |
| C6 | Valkyrae | YouTube | <https://www.youtube.com/shorts/1j3Rtvs4DCY> | 3 s | 151,635 views | Finding 2 |
| C7 | iQIYI SuperShow | YouTube | <https://www.youtube.com/shorts/1m0cHZb0Dv4> | 1 s | 109,826 views | Finding 3 |
| C7 | iQIYI SuperShow | YouTube | <https://www.youtube.com/shorts/doJJucXFF58> | 6 s | 1,541 views | Finding 3 |
| C7 | 芒果TV | YouTube | <https://www.youtube.com/shorts/NHk1rB2fbGE> | 3 s | 1,235,680 views | Finding 3 |
| C8 | @WIRED | X | <https://x.com/WIRED/status/2102430525554135468> | 1.5 s | 29,306 imp · 1.7‰ likes | Finding 3 |
| C8 | @WIRED | X | <https://x.com/WIRED/status/2095475338256044361> | 1.5 s | 30,906 imp · 0.4‰ likes | Finding 3 |
| C8 | @ColinandSamir | X | <https://x.com/ColinandSamir/status/2100673598986002504> | 1.0 s | 11,368 imp | Finding 3 |
| C8 | @ColinandSamir | X | <https://x.com/ColinandSamir/status/2102464227302621692> | 1.0 s | 3,109 imp | Finding 3 |
| C9 | Dazed | YouTube | <https://www.youtube.com/shorts/494M0N0voWc> | 1 s | 255,579 views | Finding 4 |
| C9 | Dazed | YouTube | <https://www.youtube.com/shorts/494M0N0voWc> | 5 s | 255,579 views | Finding 4 |
| C9 | @HarryStebbings | X | <https://x.com/HarryStebbings/status/2107160639504335164> | 3 s | 283,526 impressions | Finding 4 |
| C9 | @HarryStebbings | X | <https://x.com/HarryStebbings/status/2107497862149849121> | 3 s | 16,752 impressions | Finding 4 |
| C10 | iQIYI SuperShow | YouTube | <https://www.youtube.com/shorts/doJJucXFF58> | 1 s | 1,541 views | Finding 5 |
| C10 | HasanAbi | YouTube | <https://www.youtube.com/shorts/Ezl2GNeqW94> | 60 s | 1,293,987 views | Finding 5 |
| C10 | CaseOh | YouTube | <https://www.youtube.com/shorts/6Gd1CxO4DR0> | 60 s | 647,271 views | Finding 5 |
| C11 | @BBCEarth | X | <https://x.com/BBCEarth/status/2052860962223333707> | 6 s | 70,403 views | Finding 6 |
| C11 | @BBCEarth | X | <https://x.com/BBCEarth/status/2029210758798614903> | 0.1 s | 225,183 views | Finding 6 |
| C12 | 芒果TV | YouTube | <https://www.youtube.com/shorts/lGAK1CfY60M> | 2.5 s | 399,479 views | Finding 6 |
| C12 | 芒果TV | YouTube | <https://www.youtube.com/shorts/m9ugnTFnH8c> | 8 s | 2,089 views | Finding 6 |
| C12 | @veritasium | X | <https://x.com/veritasium/status/2104589841316896905> | 13.6 s | 3,333 views | Finding 6 |
| C13 | 芒果TV | YouTube | <https://www.youtube.com/shorts/lGAK1CfY60M> | 1.6 s | 399,479 views | Top-10 #1 |
| C13 | 芒果TV | YouTube | <https://www.youtube.com/shorts/NHk1rB2fbGE> | 31 s | 1,235,680 views | Top-10 #1 |
| C13 | @veritasium | X | <https://x.com/veritasium/status/2106394965458739276> | 0.05 s | 200,250 views | Top-10 #1 |
| C14 | 芒果TV | YouTube | <https://www.youtube.com/shorts/NHk1rB2fbGE> | 3 s | 1,235,680 views | Top-10 #2 |
| C14 | iQIYI SuperShow | YouTube | <https://www.youtube.com/shorts/1m0cHZb0Dv4> | 3 s | 109,826 views | Top-10 #2 |
| C14 | 奔跑吧 | YouTube | <https://www.youtube.com/shorts/0HNC_9sctPs> | 3 s | 189,795 views | Top-10 #2 |
| C15 | Ludwig | YouTube | <https://www.youtube.com/shorts/ys4tEjwM1q4> | 1.0 s | 6,893,182 views | Top-10 #3 |
| C15 | summit1g | YouTube | <https://www.youtube.com/shorts/BIn7LyWnRnI> | 1.5 s | 252,369 views | Top-10 #3 |
| C15 | Dazed | YouTube | <https://www.youtube.com/shorts/494M0N0voWc> | 1 s | 255,579 views | Top-10 #3 |
| C16 | 有吉の壁 (日テレ) | YouTube | <https://www.youtube.com/shorts/QylqRoWtN2E> | 32.5 s | 3,407,645 views | Top-10 #4 |
| C16 | 奔跑吧 | YouTube | <https://www.youtube.com/shorts/OLgudm_D57U> | 10 s | 104,109 views | Top-10 #4 |
| C16 | Ali Abdaal | YouTube | <https://www.youtube.com/shorts/FE6VL7jpfCs> | 1.3 s | 94,338 views | Top-10 #4 |
| C17 | @WSJ | X | <https://x.com/WSJ/status/2108233694049612272> | 25.1 s | 15,637 views | Top-10 #5 |
| C17 | @WSJ | X | <https://x.com/WSJ/status/2108233694049612272> | 25.5 s | 15,637 views | Top-10 #5 |
| C17 | Valkyrae | YouTube | <https://www.youtube.com/shorts/-0ztV0ayp3s> | 7.2 s | 1,051,103 views | Top-10 #5 |
| C17 | Valkyrae | YouTube | <https://www.youtube.com/shorts/-0ztV0ayp3s> | 8.0 s | 1,051,103 views | Top-10 #5 |
| C18 | Peter McKinnon | YouTube | <https://www.youtube.com/shorts/42xyZyqF-Hc> | 2 s | 248,442 views | Top-10 #6 |
| C18 | Peter McKinnon | YouTube | <https://www.youtube.com/shorts/42xyZyqF-Hc> | 40 s | 248,442 views | Top-10 #6 |
| C18 | Ali Abdaal | YouTube | <https://www.youtube.com/shorts/FE6VL7jpfCs> | 2 s | 94,338 views | Top-10 #6 |
| C19 | Ludwig | YouTube | <https://www.youtube.com/shorts/1DQZ5d7_ky0> | 1 s | 2,091,864 views | Top-10 #7 |
| C19 | Ludwig | YouTube | <https://www.youtube.com/shorts/1DQZ5d7_ky0> | 7 s | 2,091,864 views | Top-10 #7 |
| C19 | Ludwig | YouTube | <https://www.youtube.com/shorts/1DQZ5d7_ky0> | 15 s | 2,091,864 views | Top-10 #7 |
| C20 | GQ | YouTube | <https://www.youtube.com/shorts/qh0RZUoRN78> | 40 s | 1,306,890 views | Top-10 #8 |
| C20 | GQ | YouTube | <https://www.youtube.com/shorts/mV4zTaS_i1U> | 44 s | 2,823,259 views | Top-10 #8 |
| C20 | @NatGeo | X | <https://x.com/NatGeo/status/2107834236623294604> | 10 s | 12,527 views | Top-10 #8 |
| C21 | @BBCEarth | X | <https://x.com/BBCEarth/status/2029210758798614903> | 43 s | 225,183 views | Top-10 #9 |
| C21 | @BBCEarth | X | <https://x.com/BBCEarth/status/2029210758798614903> | 46 s | 225,183 views | Top-10 #9 |
| C21 | Matt D'Avella | YouTube | <https://www.youtube.com/shorts/5V2yaRC-9LQ> | 8 s | 361,944 views | Top-10 #9 |
| C22 | Vogue | YouTube | <https://www.youtube.com/shorts/XGmLXK4iGFY> | 8 s | 26,142 views | Top-10 #10 |
| C22 | Vogue | YouTube | <https://www.youtube.com/shorts/XuDyyNOuq2Y> | 8 s | 233,704 views | Top-10 #10 |
| C22 | Dazed | YouTube | <https://www.youtube.com/shorts/binFQ1Yar2w> | 18 s | 7,779 views | Top-10 #10 |
| C23 | @voxdotcom | X | <https://x.com/voxdotcom/status/2107560265936150677> | 0.5 s | 113,451 views | What not to copy |

Added to this table (not in the tables above): Ludwig lud_h1 <https://www.youtube.com/shorts/ys4tEjwM1q4> 6,893,182 views (Batch 3, `batch3-gaming-live.md`); Matt D'Avella <https://www.youtube.com/shorts/5V2yaRC-9LQ> 361,944 views (Batch 4, technique only). Both URLs built from IDs.
