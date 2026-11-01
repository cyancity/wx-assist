# wx-assist（mac 移植 fork）

upstream: https://github.com/MaleleStudySpace/wx-assist（MIT）。本 fork 承载 macOS 适配；Windows 主线功能不在这里改。

## Why
- 为什么：让 macOS 上的微信本地数据能被本地助手读取和回复，数据不出本机；复用上游 Windows 版的产品能力和本机 wx-cli 的解密读取能力，不自己实现协议。
- 怎么做：读路径走 wx-cli daemon（`wx new-messages`），写路径沿用上游 mac_ui_backend 的 Accessibility 自动化；密钥提取交给 `sudo wx init`，本仓库不实现密钥提取；不引入注入式方案。
- 做什么：mac_wxcli 后端、真机联调、mac 打包文档；不做收藏/朋友圈/语音等媒体功能移植，不碰 Windows 路线。

## 阶段：快速迭代

## 环境
- 开发机：macOS（Apple Silicon），微信 4.x 登录测试小号（wxid_v82fmaxkfkzg22_d297）
- 依赖：wx CLI（本机 ~/workspace/github/wx-cli-again），`sudo wx init` 后 `~/.wx-cli/config.json` 指向目标账号
- 后端开关：`WECHAT_BACKEND=mac_wxcli`；wx 可执行文件用 `MAC_WXCLI_BIN` 覆盖，超时用 `MAC_WXCLI_TIMEOUT`
- 运行入口：`python desktop_mac.py`（Web 控制台端口 17327）

## 高风险路径：凭据与鉴权（密钥文件、.env）、对外服务（Web 控制台）

## 审查要点
- 消息去重和 self 过滤错了会造成重复回复或自问自答；改 `_normalize_message` 或轮询状态时重点看。
- 发送目标的群名解析（`_resolve_chat_title` 系列）错了会发错群，宁可拒发。
