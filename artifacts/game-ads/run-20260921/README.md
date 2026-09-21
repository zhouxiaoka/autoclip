# 跑酷买量视频样片 · 2026-09-21

本批为同一段玩法的三种开头变体：A「连续避障」、B「下一步往哪躲？」、C「换你能躲过去吗？」。前三点二秒不同，其余主体、声音、结尾一致。用于比较开头方向，尚无投放表现数据。

- 输入：[用户提供的 Subway Princess Runner 视频](https://www.youtube.com/watch?v=jzccuci8znM)。游戏名称依据上传标题，未核对官方商店包名。
- 源区间：226.5–248.5 秒，连续 22 秒，原速。
- 输出：1080×1920，30 fps，H.264 + AAC。中心裁切约保留源画面的 926×1080；侧方环境会被裁掉，已抽检人物及主要障碍的可见性。
- 包装：中文开场、原游戏声音、最后三秒行动邀请，音量末尾 0.3 秒淡出。没有额外配音或虚构胜负。
- 制作：HyperFrames 0.8.58 / GSAP 3.14.2。可编辑项目位于 `runner-variants/`。
- AI 复核：实际调用 `doubao-seed-2-1-pro-260915`，输入 11 张每两秒抽取的有序静帧，审查内容与裁切；结果在 `seed-review.json`。这不是逐帧视频时序识别，也尚未接入 AutoClip 产品后端。
- 质量检查：HyperFrames 运行、布局、动画和对比度检查通过。两项非阻断警告建议把文字组拆成子合成；当前单场景无需拆分。另检查最终视频的编码、时长、完整解码、音轨和抽帧。

## 视频

- [A 直接展示](output/runner-A-direct.mp4)
- [B 悬念提问](output/runner-B-question.mp4)
- [C 挑战邀请](output/runner-C-challenge.mp4)

## 重渲染

进入 `runner-variants/` 后：

```sh
npx hyperframes@0.8.58 check --snapshots
npx hyperframes@0.8.58 render --output ../output/runner-A-direct.mp4 --quality looks --fps 30 --variables-file variant-A.json --strict-variables
npx hyperframes@0.8.58 render --output ../output/runner-B-question.mp4 --quality looks --fps 30 --variables-file variant-B.json --strict-variables
npx hyperframes@0.8.58 render --output ../output/runner-C-challenge.mp4 --quality looks --fps 30 --variables-file variant-C.json --strict-variables
```

使用本地系统字体子集，仅作本次样片评审。真实投放前替换为已获得相应用途许可的字体，并确认游戏画面、原声音轨的投放使用权。素材仍属于制作样片，不因渲染完成就升级为有效果证据的 golden case。
