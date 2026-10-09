# pig_maimai 🐷🎵

一个基于 [落雪咖啡屋 API](https://maimai.lxns.net) 的 AstrBot 舞萌 DX 查分插件。

支持按 QQ 号查询玩家信息与 B50 成绩，自带水鱼风格 B50 图片渲染（HTML + Playwright），以及基于官方曲库的查歌功能。

![B50 效果图](docs/screenshot_b50.png)

## 功能

| 指令 | 说明 | 是否需要令牌 |
|---|---|---|
| `/rating [QQ号]` | 查询玩家 DX Rating、段位、数据同步时间 | ✅ |
| `/b50 [QQ号]` | 生成 B50 成绩图片（5 列 × 10 排水鱼经典排版） | ✅ |
| `/查歌 <关键词>` | 按官方曲名或**曲名别名**搜索曲库（内置 1000+ 首歌的社区别名数据） | ❌ 公开接口 |
| `/歌曲 <编号>` | 查看单曲详情卡（曲师/分类/BPM/各难度定数/谱师/物量） | ❌ 公开接口 |
| `/来首 [谱面][难度]` | 随机抽一首歌，支持 `/来首`、`/来首 13`、`/来首 13+`、`/来首 mas13` | ❌ 公开接口 |
| `/吃分 [QQ号]` | B50 挖潜：按「当前 RA → 满档 RA」差值推荐涨分最快的谱 | ✅ |

- 不带 QQ 号时默认查询发消息者本人（需玩家在落雪网页端绑定 QQ）
- B50 渲染失败时自动回退为文字版摘要，功能不瘫痪
- 曲库数据内存缓存 24 小时，曲绘本地缓存（首次渲染后二次出图极快）

## 安装

1. 将本仓库克隆/下载到 AstrBot 的插件目录：

```bash
cd /AstrBot/data/plugins   # 或你的插件目录
git clone https://github.com/你的用户名/pig_maimai.git
```

2. 复制配置模板并填入你的落雪开发者令牌：

```bash
cd pig_maimai
cp config.example.json config.json
# 编辑 config.json，填入 developer_token
```

3. B50 图片渲染需要 Playwright + Chromium（仅渲染图片时需要）：

```bash
pip install playwright
playwright install --with-deps chromium
```

> 容器部署（如本插件的开发环境）建议将上述步骤写入自定义镜像；
> 国内环境请设置 `PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright` 加速下载。

4. 重启 AstrBot，日志中出现 `pig_maimai 已加载` 即成功。

## 获取落雪开发者令牌

1. 注册/登录 [落雪咖啡屋](https://maimai.lxns.net) 并完成邮箱验证
2. 前往开发者面板（`/developer`）提交开发者申请
3. 审核通过后在开发者面板生成令牌
4. （查询的前提）在落雪网页设置的账号绑定中填写你的 QQ 号

详细 API 文档见 [maimai.lxns.net/docs](https://maimai.lxns.net/docs)。

## 注意事项

- **开发者令牌是敏感信息**，`config.json` 已被 `.gitignore` 排除，请勿提交或分享
- 查询依赖玩家在落雪侧主动绑定 QQ 并导入成绩（微信代理导入，落雪有教程）
- 落雪 API 有频率限制（触发返回 429），本插件已做曲库缓存，请勿高频刷分

## 已知限制 / TODO

- [x] ~~曲名别名系统~~（v0.2.0 已支持：落雪官方别名接口，本地缓存 7 天）
- [x] ~~随机选曲~~（v0.4.0 已支持：`/来首`，按难度/谱面类型随机）
- [x] ~~吃分推荐~~（v0.5.0 已支持：`/吃分` B50 内挖潜；拟合定数/开新谱推荐规划中）
- [ ] 单曲 RA 计算器（公式已实现于 `ra.py`，待定交互形态）
- [ ] /猜歌 等曲库玩法

## 开发与测试

插件逻辑可以脱离框架和 QQ 登录做 mock 测试（框架桩 + 模拟事件，曲库数据本地缓存）：

```bash
python3 -m venv .venv
.venv/bin/pip install requests
.venv/bin/python tests/test_mock.py
```

## 致谢

- [落雪咖啡屋](https://maimai.lxns.net) — 查分数据与 API
- [水鱼查分器](https://www.diving-fish.com/maimaidx/prober/) — B50 排版设计参考
- [AstrBot](https://github.com/AstrBotDevs/AstrBot) — 机器人框架

## License

MIT
