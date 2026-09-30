# 安全政策

安全修复集中在当前 `main`，通过后续正式版本提供给安装包用户。旧版本没有独立维护分支；请查看 [Releases](https://github.com/zhouxiaoka/autoclip/releases) 与发布说明确认修复是否已进入你使用的版本。合入源码不代表已发布安装包。

## 报告问题

项目目前未开启 GitHub 私密漏洞报告。可使用维护者公开联系邮箱 [christine_zhouye@163.com](mailto:christine_zhouye@163.com)私下联系；如通过 Issue 联系，只描述需要建立安全联系，不公开漏洞利用步骤、API Key、Cookie、私人素材或含密钥的日志。建立私密渠道后，再提供影响版本、复现条件和脱敏证据。

本项目没有公布专用安全邮箱、响应时限或第三方审计承诺。已公开的安全信息以[安全公告](https://github.com/zhouxiaoka/autoclip/security/advisories)、发布说明及对应修复记录为准。

## 使用与更新

桌面客户端与默认 Docker 配置面向本机或可信网络。公网部署需自行配置认证、TLS 和网络访问控制；不要直接公开 Redis、Flower 或未经保护的后台接口。不要把提供商 API Key 当成应用访问密码。

升级前备份数据库、项目文件和配置。源码部署按 `requirements.txt` 安装 Python 依赖，在 `frontend/` 执行 `npm ci`；不要通过无约束升级或自动修复命令绕过项目的依赖版本。具体启动与备份步骤见 [DOCKER.md](DOCKER.md) 和 [STARTUP_GUIDE.md](STARTUP_GUIDE.md)。
