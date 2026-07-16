# LDXP 店铺发现任务

本任务通过 GitHub Actions 低频验证 `pay.ldxp.cn` 的公开店铺 Token。

## 运行方式

进入仓库的 **Actions → Discover LDXP shops → Run workflow**，选择本轮验证数量后执行。

工作流也会每天自动运行一次，定时任务默认验证 100 个候选 Token。

## Token 规则

- 长度：3～8 个字符
- 字符：`A-Z`、`a-z`、`0-9`、`_`、`-`
- 单线程请求
- 每次请求随机等待 2～5 秒
- 每轮最多验证 300 个 Token
- 遇到 HTTP 403、429 或风控 HTML 时立即停止

## 输出文件

运行结果保存在 `data/ldxp_results/`：

- `checked_tokens.txt`：已经验证过的候选 Token
- `valid_shop_urls.txt`：验证成功的店铺地址
- `valid_shops.csv`：店铺 Token、名称、商品数和检查时间

每次运行结束后，结果会：

1. 上传为 GitHub Actions Artifact，保留 30 天；
2. 自动提交回当前仓库，避免后续重复验证。

## 本地运行

```bash
python -m pip install "requests>=2.32,<3"
python scripts/ldxp_shop_discover.py \
  --attempts 100 \
  --min-delay 2 \
  --max-delay 5 \
  --output-dir data/ldxp_results
```

该脚本只读取公开接口，不包含登录、下单、验证码绕过、代理池或高并发逻辑。
