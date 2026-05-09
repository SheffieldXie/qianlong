# 乾六爻交易系统 | Qian Liu Yao Trading System

> XAU/USD 15分钟量化交易系统 — 基于I Ching哲学的分形博弈框架

## 快速开始

```bash
cd qianlong
pip install -r requirements.txt
python server.py
```

访问: http://127.0.0.1:5048

## 核心策略

| 相位 | 条件 | 操作 |
|------|------|------|
| ① 三维共振 | 价格穿EMA144 + SAR翻号 + DEA穿0 + RSI突破 | 建立底仓4份 |
| ② 趋势主导 | MACD慢线 >+6.5 / <-6.5 | 加仓4份(火上浇油) |
| ③ 混沌套利 | MACD∈[-6.5,+6.5], RSI≤30/≥70 | 套利4份(高抛低吸) |

## 部署到 Render.com

1. 创建GitHub仓库并推送代码:
```bash
git init && git add . && git commit -m "乾六爻"
# 然后连接GitHub远程仓库
git remote add origin <your-repo-url>
git push -u origin main
```

2. 登录 https://render.com

3. 点击 **New +** → **Web Service**

4. 连接你的GitHub仓库

5. 配置:
   - **Name**: qianlong-trading
   - **Region**: Oregon (免费)
   - **Branch**: main
   - **Root Directory**: (留空)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --timeout 120 --workers 1 wsgi:app`

6. 选择 **Free** tier

7. 点击 **Create Web Service**

部署成功后访问: `https://qianlong-trading-xxx.onrender.com`

> ⚠️ 免费实例15分钟无访问自动休眠，下次访问需等待约30秒唤醒。

## 目录结构

```
qianlong/
├── server.py              # Flask 主服务
├── wsgi.py                # 生产环境入口 (gunicorn)
├── render.yaml            # Render部署配置
├── requirements.txt       # Python依赖
├── engine/
│   ├── core.py            # 指标计算 + 信号检测
│   └── paper_trading.py   # 模拟盘引擎
├── data/
│   └── fetcher.py         # 数据获取 (yfinance)
├── strategy/
│   └── position.py        # 12份仓位管理
├── risk/
│   └── manager.py         # 风控 (Kill Switch)
└── web/
    ├── templates/         # HTML模板
    └── static/            # CSS + JS
```
