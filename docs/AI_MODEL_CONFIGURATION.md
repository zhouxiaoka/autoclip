# AI 模型配置

设置 → AI 模型默认只需选择预置供应商、填写 API Key。供应商列表区分赞助伙伴、官方服务、自定义兼容接口和本地服务；赞助伙伴展示合作说明。

- 高光分析：获取可用模型后自动预选，也可手动更换。
- 画面理解：默认复用高光分析模型；高级设置中可指定另一个连接和模型。
- 封面生成：默认复用供应商和密钥，预选已适配的生图模型；没有适合的型号时使用视频截帧。高级设置中可以配置其他供应商。
- 字幕转写：可选择 Whisper 或 SenseVoiceSmall 本地转写，也可单独绑定云端服务。一次“准备模型”操作完成必要组件安装及模型下载；安装下载即时执行，选择随设置保存。新导入任务使用所选型号，本地服务不自动回退到云端。

普通配置不需要命名或创建连接，也不使用配置弹窗。内部通过连接引用共享地址和密钥，并保留各供应商已填写的配置。按用途提供封面供应商切换与可选的补充画面模型；预置服务不显示接口地址，地址仅在自定义或本地服务中出现。只有未知的自定义模型显示能力选择。分析方式自动判断，原有显式偏好保留，重新选择分析模型后恢复自动方式。改变服务地址时必须重新填写已保存的密钥，避免把旧密钥自动发送给新地址。空输入保留已保存密钥。

自动预选只从本次返回的模型列表中选择。刷新不会替换用户已选型号，也不会将用户选择的视频截帧重新切换成生图；需要时由用户主动更换模型。

## 持久化与兼容

新配置保存在数据目录的 `ai-model-settings.json`，包括 connections、analysis、vision、cover、分析偏好和切片参数。保存前整体校验，通过临时文件和原子替换一次写入，密钥不返回到前端。API 进程和 worker 在下次调用时读取新配置。

第一次打开页面时，读取原 settings.json、vision-settings.json、cover.json 及其环境变量生成草稿；只有保存时才启用新格式。原文件保留。新格式存在后具有优先级；旧文件及环境变量的更改不覆盖已保存的新配置。独立视觉接口、独立封面接口和显式 OCR 型号均保留。

## 动态模型目录

未填写 Key 时也展示模型预览，并明确标为公开目录。无限星河实时读取公开模型广场 `https://infistar.cc/api/pricing`，按 `supported_endpoint_types` 区分分析、图片生成和图片编辑；其他预置供应商展示参考目录及能力目录。预览不会自动写入模型推荐，填 Key 后才按账号列表自动预选。

无限星河的账号 `/v1/models` 列表与公开目录按精确 ID 关联，补充接口类型与图像理解标签，不将公开但账号不可用的型号混入账号列表。公开目录缓存 1 小时，手动刷新可更新；网络失败保留缓存，首次离线使用随版本提供的精简快照并显示提示。快照只包含公开型号、接口类型和能力，不包含密钥或账号数据。

`POST /settings/ai-models/discover` 接受连接草稿，返回模型 ID、用途和能力。供应商列表成功时以其结果为准，不混入未经该服务列出的预置型号；刷新失败保留上次列表，第一次失败才展示内置参考目录。无论目录是否收录，均可手动输入模型 ID。

能力信息依次采用：用户显式设置、当前服务的模态元数据、经过核实的精确型号修正、models.dev 的精确供应商/型号资料。未知模型不会标记为“仅文字”；可手动声明能力或做图片理解测试。网关任意别名不会按字符串猜测原模型。

- 模型列表缓存 5 分钟，支持手动刷新，按供应商、地址和密钥的完整哈希隔离。
- models.dev 公共能力目录缓存 24 小时，失败保留旧版本；只拉取公开资料，不发送用户密钥或配置。
- Ollama 通过 `/api/show` 读取本地模型的 vision 能力。
- 已选模型不会被新版本、新型号或失败的刷新自动替换。
- 客户端与后端视觉路由共用模型能力资料。仅文字或能力未知的自动模式使用字幕分析。

公开数据源：https://models.dev/api.json 。Qwen3.8 Max/Flash 的多模态修正依据：https://www.alibabacloud.com/help/en/model-studio/text-generation （2026-09-29 核实）。

## 调用协议边界

模型连接使用 OpenAI Chat Completions 兼容接口；Gemini 官方列表使用原生 Models API。生图按供应商适配 OpenAI Images、Seedream、千问同步/万相异步接口、Gemini 原生图片输出、Grok Images 和智谱 Images。预置供应商自动选择生图协议；兼容服务可填写自己的地址。

官方生图参考目录位于 `backend/core/image_model_catalog.py`，保留核对日期和各官方文档链接，与 models.dev 的动态能力元数据及账号实时列表共同使用。Seed 官方 ID 与聚合站别名分别管理；已下线型号不作为无 Key 预览推荐。仅编辑模型不列入文生图列表。模型目录不等同于账号权限，也不代表已经做过真实付费生成验证。

发现一个型号不保证账号有调用权限，也不代表 AutoClip 已适配该模型的所有专有协议。自定义模型可手动选择，但服务必须兼容选定协议。图片测试会产生少量调用，列表刷新不执行生成式测试。此改动不增加云端语音转写协议。

## ASR 与分析方式（2026-09-29）

页面按「AI 服务 → 字幕转写 → 封面 → 高级」排列（`frontend/src/features/settings/AIModelSettings.tsx`，纯逻辑在 `modelSettingsLogic.ts`）。AI 服务一节只有供应商、密钥、分析模型和「画面识别」开关；转写单独绑定供应商和模型，选择已配置的供应商可复用凭证。本地 Whisper 不上传音频；云端转写只在缺少字幕时上传提取的音频。协议验证使用 HTTP mock。

画面识别是一个开关，首次配置默认开启（`allow_send_frame=true`），提示写明游戏画面、口播较少的内容推荐开启。开启映射 `analysis_mode=auto`，抽样几张画面结合字幕分析；关闭映射 `subtitle`，只发送字幕。所选分析模型仅文字时开关自动失效并说明原因。高级里可为画面理解和封面分别指定其他连接。

### 核查来源与接入边界

| 提供商 | 核查到的 ASR | 本次可生成带时间戳字幕 |
| --- | --- | --- |
| 本地 | Whisper tiny/base/small/medium/large-v3 | 是，沿用本地运行时 |
| 本地 FunASR | SenseVoiceSmall | 是，消费 CTC 词级时间戳；按需安装，独立进程运行 |
| OpenAI | whisper-1、gpt-4o-transcribe-diarize、gpt-4o-transcribe、gpt-4o-mini-transcribe | 前两项；普通 transcribe 的纯文字输出不能替代字幕时间轴 |
| 阿里云百炼 | Qwen-Audio-3.1/3.0-ASR-Flash、Fun-ASR-Flash、Qwen-ASR-Filetrans、Fun-ASR、Paraformer | 同步 Flash 系列；SSE 收集所有已完成句子，毫秒转秒。Filetrans 需公网音频地址，暂不代建对象存储 |
| 无限星河 | 公开目录当前列出 qwen-audio-3.0-asr-flash-streaming / filetrans | 目录可预览，但其具体上传/时间戳协议尚未确认，标为未接入，不能选为可用默认值 |
| 智谱 | GLM-ASR-2512 | 目录可预览，字幕时间戳适配尚未完成 |
| 火山引擎 | 豆包录音识别（大模型） | 独立语音产品的 App/Token/资源 ID，与方舟 Seed API Key 不同，暂未接入 |
| 自定义兼容服务 | 用户输入模型 ID | `/audio/transcriptions` + `verbose_json.segments`，缺少时间戳直接报错，不猜时间轴 |

来源：
- [OpenAI 文件转写](https://developers.openai.com/api/docs/guides/speech-to-text)：Whisper verbose_json 与 diarized_json 的时间戳格式不同。
- [阿里云 ASR 模型总览](https://help.aliyun.com/zh/model-studio/asr-model)
- [阿里云同步 Flash HTTP 接口](https://www.alibabacloud.com/help/zh/model-studio/fun-asr-flash-recorded-speech-recognition-http-api)：原 DashScope 域名仍可使用；Base64 音频与 SSE 句级时间戳。
- [无限星河公开模型目录](https://infistar.cc/api/pricing)、[公开 API 入口](https://doc.infistar.cc/api-overview)
- [智谱 GLM-ASR](https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-asr-2512)
- [火山引擎录音文件识别](https://docs.volcengine.com/docs/DoubaoVoice/AudioFileRecognitionStandardEdition?lang=zh)

实现使用 `asr_model_catalog.py` 定义明确适配的协议；模型发现附加 `asr/asr_supported/asr_note`，账号列表不会被公开目录扩大。未知 ASR 只出现在预览中，不能自动选用。新增厂商须补充请求协议和真实时间戳映射，不能仅填一个模型名。

云端任务以 16 kHz 单声道 PCM 每 180 秒分块（原始 5.76 MB，Base64 后低于 10 MB），用准确样本偏移合并时间轴。固定分块边界可能截断词语，是当前分段方式的限制。只有全任务成功才发布 SRT；请求失败不偷偷切换供应商或本地模型，不把凭证或服务端原始错误体写入日志。

新手流程：没有任何可用连接时，首页弹出一次性的「连接 AI 服务」对话框（`FirstRunSetup.tsx`，本会话内「稍后再说」后不再弹），内容与设置页 AI 服务一节完全相同，也可点「更多选项」进入设置页。首次空白配置默认：画面识别开、封面「AI 生成」且「参考视频画面」开，供应商分组把赞助伙伴放在「推荐」并保留合作说明；已有配置不强制改动。未连接 AI 服务时导入视频会被拦下并提示先连接。封面模型缺失时回落到视频截帧。模型使用单选，搜索无匹配时允许显式选择自定义型号。关闭画面识别后的连接测试也不发送图片。

## 本地 SenseVoice（#67）

设置 → 字幕转写 → 转写方式选择 **SenseVoice · 本地**，点击“准备模型”，就绪后保存设置。首次需联网下载 FunASR/PyTorch 组件和 SenseVoiceSmall/FSMN-VAD 模型，请预留至少 8 GB 磁盘空间（Windows 的真实安装验收约 5.8 GB，另需安装临时空间）。转写时使用已下载的本地路径，不上传音频、不请求云端转写、不需要 API Key。默认 Whisper 和已有选择保持原样。

这是 FunASR 1.3.14 的 SenseVoiceSmall 适配器，不是把 FunASR 工具箱中的所有模型都加入列表。支持中文、粤语、英语、日语、韩语及自动语言检测。首版使用 CPU，限制为两条计算线程；不加载 CAM++ 说话人分离或额外标点模型，也不承诺 issue 中的通用速度数字。模型产生的空格和标点会保留。高光分析仍使用另行配置的分析模型。

运行时位于数据目录 `sensevoice/runtime`，模型缓存位于 `sensevoice/models`。独立 Python 子进程导入这些组件，避免 PyTorch/NumPy 与 Whisper、API 后端依赖冲突。后台准备失败后可以重试；重启后可识别中断的准备操作。安装、删除和转写共享跨进程锁，忙碌时禁止修改组件。高级项可以删除组件及模型。

显式请求 `output_timestamp=True`，严格配对 `words` 与毫秒 `timestamp`，先恢复原文空格和标点，再按标点、42 字符、8 秒上限以及停顿生成字幕。词级信息写入带 SRT 内容校验的 `.words.json`，用于已有字幕对齐流程。缺失、不完整、倒退、重叠或明显超出音频的时间戳会中断任务并显示 SenseVoice 的处理建议；不会按文字比例伪造时间轴，也不会把一条粗 VAD 段当作精确字幕。失败不会覆盖已存在的字幕。

接入参考 [#67 讨论](https://github.com/zhouxiaoka/autoclip/issues/67)、[123mlly 的 feature/dev 分支](https://github.com/123mlly/autoclip/tree/feature/dev) 和 [LauraGPT 的时间戳修复 PR](https://github.com/123mlly/autoclip/pull/1)。词级聚合思路依据该 MIT 许可实现改写，保留项目 [MIT 许可证](../LICENSE)；不搬入 fork 的其他改动和比例铺字幕兜底。

FunASR/SenseVoice 源码 MIT 与模型权重许可不同。权重使用前请阅读 [SenseVoiceSmall 模型卡及其许可链接](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)；安装包不内置或重新分发这些权重。硅基流动的云端 SenseVoice 型号仍需独立的云端时间戳适配，不能与这个本地实现混用。

结构化输出回归测试：`backend/tests/test_sensevoice.py`。真实语音验收：`.github/workflows/sensevoice.yml` 在三种系统的 Python 3.13 环境中实际安装、下载模型，然后在阻断网络的子进程内转写仓库公开访谈前 45 秒，检查完整词级信息、字幕顺序和边界、依赖隔离及卸载。该测试属于真实 ASR 验收，不代表长视频质量对照或桌面安装包真机验收。
