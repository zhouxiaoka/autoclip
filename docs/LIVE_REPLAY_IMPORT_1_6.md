# 1.6.0 游戏高光 · 直播回放导入

## 目标和入口

主播从首页「从直播回放选择」找到一场直播，生成高光后回到已有的项目详情、预览、编辑和导出流程。来源决定如何取得录像，用户选择的发布平台决定成片规格。现有本地文件、视频链接和非游戏项目继续使用各自的导入流程。

| 用户动作 | 产品行为 | 验收条件 |
|---|---|---|
| 初次连接 OBS | 在首页回放面板打开已有 OBS 连接设置，也可以从设置页管理同一连接 | 展示实测连接状态。连接和允许下播后自动出片独立，默认关闭自动制作 |
| 手动选择 OBS 场次 | 正在直播或仍在录制时展示状态；两者已结束、场次归属明确、看到落盘文件后提供手动生成 | 仅浏览列表不调用模型。用户点击后验证文件身份、稳定性、音视频可读性和区间，再建一个项目 |
| 离开后返回 | 重开列表时从数据库恢复场次和已有项目 | 双击、刷新和重启均复用场次领取记录。目录外文件、被替换的录像、分卷、独立录屏和跨断线归属不明的场次均不自动剪 |
| 选择 Twitch、YouTube 或 Kick 录像文件 | 从 Twitch 创作者后台、YouTube Studio 或 Kick Studio 下载自己已归档的回放，在回放面板选择文件，回到首页选择输出设置并生成 | 文件选择本身不启动生成；项目保留来源，使用现有游戏高光链路和项目页 |
| 选择 Discord 或其他工具的本地录像 | Discord 可选择已保存的片段或直播时自行录制的视频。「其他」可选择其他工具保存或导出的录像 | 显示选择文件按钮，确认生成后记录所选来源并打开已有项目详情 |
| 连接 Twitch 频道 | 在回放面板绑定自己的频道，按频道列出已发布的整场归档。未开启保存、回放过期或列表为空时，提供选择本地录像入口 | 按频道 ID 和归档视频 ID 标识场次，用真实频道核对归属和分页。观看地址只用于预览 |
| 连接 YouTube 频道 | 目标流程为系统浏览器只读授权，返回此前正在选择场次的面板，显示频道名及回放列表 | 使用真实频道校对标题、广播 ID、归档和权限状态。授权成功与取得录像分别验收 |
| 选中尚无录像的 YouTube 场次 | 保存场次选择，提供「选择录像文件」和 YouTube Studio 入口 | 归档处理中显示等待；禁止仅凭观看页或 OAuth 授权开始付费任务 |
| 已有作品 | 「打开项目」回到现有游戏高光详情页 | 继续使用原有「回看游戏高光」「预览与修改」「下载成片」。同一场次已有项目时避免重复制作 |

当前桌面回放面板开放全部 6 个渠道入口（OBS Studio、Twitch、YouTube、Kick、Discord 及其他）：已配置 OAuth 应用的桌面版可在 Twitch / YouTube 内直接连接频道并列出已结束回放；Kick、Discord 以及未配置 OAuth 时的 Twitch / YouTube 均支持打开创作者后台指引并直接选择本地录像文件，保留来源归因。OBS 手动选场后与所有渠道一致，统一回到首页确认发布平台与成片规格，提交后在项目页后台异步准备录像。

## 开发顺序

1. **首页和 OBS 手动路径。** 复用 OBS 连续观察和入库记录。自动开关关闭时保存可手选场次与文件身份，用户点击后才排队。原自动任务继续执行原有费用同意、模型预算和去重检查。列表展示最近 100 场，使用本机保存时间和直播区间长度。
2. **手动导入录像文件。** 已导出录像直接走现有导入预检、平台选择和项目详情。这个入口可独立验收，在 AutoClip 内无需授权平台账号。
3. **Twitch 和 YouTube 频道和场次。** 分别验证各平台面向桌面应用的授权流程。Twitch 从已验证的主播身份取得频道 ID，使用 Helix Get Videos 的 archive 类型按频道分页。YouTube 注册桌面 OAuth 客户端并验证所需授权，使用系统浏览器、只读权限、PKCE 和系统凭据存储。实现频道切换、断开、撤销授权、分页和错误恢复。按平台、频道及回放 ID 保存场次与项目关联。用户确认「这就是该场录像」，跨来源归属不明时显式关联。
4. **平台自动取文件的可行性验证。** 用真实账号核验受平台支持的取回方式、适用账号、画质、耗时和失败恢复。在指定场次可取得完整录像且可解码前，Twitch 和 YouTube 的剪辑输入由用户提供录像文件。已连接、能列回放、能自动剪辑分别记录证据。
5. **发版验收。** 隔离数据验证真实 OBS 下播继续录制、自动关闭与开启、应用重启和重复事件。在 macOS arm64 和 Windows x64 安装包上分别导入 Twitch、YouTube 和 Kick 的自有归档，完成项目预览和实际导出。按版本验收清单执行源码、安装包、真实账号和媒体检查。

## 选中场次后的导入体验

对能取得整场录像的来源，用户选中场次后点「导入这场回放」。AutoClip 保存平台、频道、场次 ID 和导入进度。已持有可确认归属的本地录像时直接校验；平台提供授权导出时显示「准备录像」「下载中」，支持取消和失败后重试。文件完整、可读且归属确认后，回到首页确认输出设置，用户点「生成游戏高光」才提交剪辑。重试沿用同一场次；已有项目直接打开。仅有观看地址时不显示可自动下载。

- Twitch 首先验证创作者在 Video Producer 发起官方整场下载后，桌面端能否可靠接收到与所选 VOD 对应的下载结果。不能仅凭下载目录中的最新文件或相似标题自动归属。若需用户确认，让其核对候选录像；「选择本地录像」始终作为备用入口。Helix 列出回放与下载 Clips 是两个不同的能力。[Twitch VOD 管理](https://help.twitch.tv/s/article/video-on-demand?language=en_US) · [Twitch API](https://dev.twitch.tv/docs/api/reference/)
- YouTube 单独评估 Google Data Portability API 的授权、地区与应用审核要求。用自有真实直播归档验证能否导出媒体、与所选视频 ID 匹配，以及耗时。其请求按数据类别和可选时间范围发起，并非指定视频 ID 的下载接口。[视频媒体导出范围](https://developers.google.com/data-portability/schema-reference/youtube) · [归档请求参数](https://developers.google.com/data-portability/reference/rest/v1/portabilityArchive/initiate)
- 验收至少覆盖同名场次、同时下载其他文件、下载中断、重复点击，以及无媒体时模型调用为零。分别记录全自动导入、用户在平台确认导出后自动接收、手选文件三条路径中已实测通过的能力。

### Twitch 整场直导（异步下载）

已连接频道的公开已结束归档默认提供「使用这场回放」入口（可通过 `AUTOCLIP_TWITCH_REPLAY_PILOT=0` 关闭）。用户回到首页选择发布平台，点「生成游戏高光」后原子领取场次并立即进入项目页，由 Studio 后台异步执行下载与校验（支持实时进度展示与取消/删除中断），沿用游戏高光的模型设置和项目详情；创作者后台导出与本地文件导入继续保留为备用入口。

场次目录来自 Helix。用户点生成后，通过 Get Videos 核对归档 ID、频道、可见性和原始 stream ID，通过 Get Streams 排除同一场仍在直播。内置 yt-dlp 只接收从该场次构造的 Twitch URL，使用公开媒体流，不传频道 OAuth 令牌或浏览器 Cookie。整场临时下载成功后，核对平台时长、音视频轨与首尾解码，再核对当前账号和选择。通过预检后才创建项目并分派模型任务。缺失分片、下载失败或归属变化可重新选择；已有项目复用原记录。

实测公开的 Twitch 长回放可解析至 1080p60，首尾分片可读取。隔离桌面浏览器采用模拟频道和 HLS 服务，145 秒游戏样本经过实际下载、云端转写、模型选段和渲染，得到可播放的竖屏 MP4。真实账号绑定与空列表已验证，仍需同一位授权主播用自己的真实归档完成一次全流程。多小时下载的进度、取消、重启续传和双平台安装包验收仍待完成。

Helix 文档提供视频列表及 Clips 下载。整场下载实验使用第三方播放器解析，面向用户开放前应向 Twitch 确认产品的分发和使用条件。备选工具 TwitchDownloaderCLI 同样支持按 VOD ID 下载 MP4。 [Twitch API](https://dev.twitch.tv/docs/api/reference/) · [Twitch 开发者支持](https://dev.twitch.tv/support/) · [Twitch 使用条款](https://www.twitch.tv/p/en/terms-of-service/) · [TwitchDownloaderCLI](https://github.com/lay295/TwitchDownloader/blob/master/TwitchDownloaderCLI/README.md)

可通过 Twitch 开发者支持提交以下问题，并附开发版流程截图。支持团队确认前保持实验开关默认关闭。

> AutoClip is a desktop video editor. A broadcaster authorizes their own channel, selects one of their published, completed VODs, and explicitly starts a highlight project. We use Helix to check ownership and stream status. We want to retrieve the full recording onto the broadcaster’s device. If they choose cloud processing, audio segments, transcripts, or sampled frames may be sent to their configured model provider. Which supported VOD export interface, if any, may a distributed desktop app use? Is retrieval of the broadcaster’s public playback stream for this workflow permitted, and does it require written approval or a partner agreement?

### YouTube 媒体导出权限

现有 `youtube.readonly` 可读取场次。Google Data Portability API 提供用户自有视频的原始媒体或 MP4。要试验这条路径，先核对测试账号所属地区、年龄和资格，然后由项目管理员启用结算与 API，单独请求对应可见性的视频导出授权。先用一条普通自有上传验证媒体传输，再用真实直播归档验证视频 ID 与文件能否可靠对应。导出按数据类别创建异步任务，可能包括多条视频；产品须明确所请数据范围。对使用 YouTube Data API 的客户端，直接复制站内音视频另有事先书面许可要求。 [可用地区](https://support.google.com/accounts/answer/14452558?hl=en) · [启用 API](https://developers.google.com/data-portability/user-guide/overview) · [单独授权](https://developers.google.com/data-portability/user-guide/configure-oauth) · [媒体格式](https://developers.google.com/data-portability/schema-reference/youtube) · [YouTube 开发者政策](https://developers.google.com/youtube/terms/developer-policies/) · [向 YouTube 提交申请](https://support.google.com/youtube/contact/yt_api_form)

## 本轮开发验证

首页入口、OBS 手动选择和 Twitch、YouTube 导出文件导入已在开发分支实现。隔离浏览器验证了从首页进入、查看 OBS 连接配置、分别选取 Twitch、YouTube 来源的测试录像并回到首页等待确认。Twitch 路径已核对确认前项目数为零。Kick 的隔离浏览器测试使用 40 秒合成 MP4，确认前项目数为零，确认后创建一个来源为 Kick 的项目并进入共用详情页。三种文件来源的后端回归均校验了来源记录和游戏高光计划。OBS 接口回归覆盖并发双击、文件被替换、两路输出的结束顺序，以及截取直播与录像的重叠部分后只提交一次。普通项目和直播项目共用原有详情页。

桌面端已实现 Twitch 设备码授权和 YouTube 系统浏览器授权（PKCE 与本机回调）。频道列表只保留该账号已结束的直播或已发布的整场归档。选择场次后在平台后台导出录像，回到面板关联本地文件，确认后打开同一个项目。重新授权同一频道可找回原项目，断开不删除已导入的录像。已使用隔离的 OAuth 与平台 API 响应，在实际前端及桌面后端验证两家的授权、分页、重开面板恢复所选场次、关联本地 MP4、导入和重新打开同一项目。接口回归另行覆盖并发提交只派发一次、切换身份后拒绝旧场次和文件复制失败可重试。YouTube 已使用真实测试账号完成只读授权并核对频道身份。已在开发版回放面板用未启用直播的真实频道验证专用提示、选择本地录像和进入生成确认；另通过同一文件导入接口验证游戏录像可生成可播放的成片。Twitch 已使用真实测试账号完成设备码授权，确认回放接口返回零条归档，界面显示空列表且可选择本地录像。含真实归档场次的选择与项目重开仍待验收。安装包、真实归档场次以及本轮新增的 OBS 手动入口在真实直播环境中的验收仍待执行。

平台授权和自动出片分别征得用户同意。首次开启自动出片时展示数据类型、模型接收方和可能费用。

## 其他平台的接入优先级

- **Kick 优先验证。** 创作者可从网页后台 Studio → VODs 下载自己频道中仍可用的整场录像，开发版回放面板提供 Kick Studio 的 VODs 页面入口，用户下载后回到面板选择录像。真实导出样本和成片质量待验收。应用内按频道自动列场次和取文件需要单独核验接口及账号权限。[Kick 官方下载说明](https://help.kick.com/en/articles/7832538-how-to-download-your-kick-vod)
- **TikTok LIVE 走创作者端导出。** 优先验证手机导出的录像能否在桌面导入，并检查竖屏画面、游戏 HUD 与主播反应的保留情况。[TikTok LIVE 回放](https://support.tiktok.com/en/live-gifts-wallet/tiktok-live/tiktok-live-replay)
- **B 站、抖音先覆盖本机 OBS 录像。** 前提是 OBS 实际负责推流并同时录像，AutoClip 能确认直播结束和文件归属。主机或手机直接开播时走自有录像文件。公开的互动或开播接口还不足以确认可读取普通游戏主播的历史整场文件，平台账号接入另行验证。[B 站直播开放平台](https://open-live.bilibili.com/) · [抖音直播 SDK](https://open.douyin.com/platform/resource/docs/ability/douyin-live-sdk/solution/)

[OBS 下播后出片设计](OBS_POST_STREAM_DESIGN.md) · [Twitch 频道回放列表](https://dev.twitch.tv/docs/api/videos/) · [Twitch 归档和导出](https://help.twitch.tv/s/article/video-on-demand?language=en_US) · [Google 桌面 OAuth](https://developers.google.com/identity/protocols/oauth2/native-app) · [YouTube 直播列表](https://developers.google.com/youtube/data/live/reference/rest/v3/liveBroadcasts/list) · [YouTube 导出说明](https://support.google.com/youtube/answer/56100)


## 为 AutoClip 注册频道应用

以下由 AutoClip 维护者为产品办理一次。主播使用已配置的安装包，仅需在回放面板选择平台并连接自己的频道。

1. **Twitch**：维护者验证邮箱、启用双重验证，在开发者后台的 Applications → Register Your Application 填唯一应用名和分类，Client Type 选 Public。表单要求回调地址时可填写本机开发地址 `http://localhost` 并点 Add，设备码授权使用 Twitch 展示的验证地址。创建后在 Manage 内复制 Client ID。[Twitch 应用控制台](https://dev.twitch.tv/console/apps) · [注册步骤](https://dev.twitch.tv/docs/authentication/register-app/) · [设备码授权](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#device-code-grant-flow)
2. **Google**：在 AutoClip 的 Cloud 项目启用 YouTube Data API v3，进入 Google Auth Platform。Branding 填产品名和联系邮箱，Audience 选 External / Testing 并添加测试账号，Data Access 选择 `https://www.googleapis.com/auth/youtube.readonly`。在 Clients 创建 Desktop app 并下载客户端 JSON。公开分发前完成适用的品牌、敏感权限审查和发布设置。[启用 YouTube Data API](https://console.cloud.google.com/apis/library/youtube.googleapis.com) · [Google Auth Platform](https://console.cloud.google.com/auth/overview) · [桌面应用回调与 PKCE](https://developers.google.com/identity/protocols/oauth2/native-app)
3. **开发联调**：给桌面后端设置 `AUTOCLIP_TWITCH_CLIENT_ID` 和 `AUTOCLIP_YOUTUBE_DESKTOP_JSON`（Google 下载的 JSON 的绝对路径）。也可使用 AutoClip 数据目录的 `replay-oauth.json`，键为 `twitch.client_id`、`youtube.client_id`、`youtube.client_secret`，或用 `AUTOCLIP_REPLAY_OAUTH_CONFIG` 指向该文件。桌面 OAuth 客户端信息与主播授权令牌分开；主播令牌仅保存在系统凭据库。不要提交私人配置或测试账号资料。
4. **打包**：Desktop Build 使用仓库变量 `AUTOCLIP_TWITCH_CLIENT_ID`、`AUTOCLIP_YOUTUBE_CLIENT_ID` 和构建 secret `AUTOCLIP_YOUTUBE_DESKTOP_CLIENT_SECRET`。这里只能使用 Desktop app 的客户端信息（原生应用信息可被安装者读取），不得使用服务端 OAuth 密钥。
5. **产品验收**：每个平台使用有归档的自有频道，核对频道名、回放标题与日期、下一页、空频道和撤销授权。导入一场录像，关闭重开 AutoClip，再从同一场次打开原项目。追加验证切换到另一个账号、取消授权、服务限流、录像尚在处理，以及断开后继续使用本地文件入口。
