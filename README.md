# Nosrat Panel

<div align="center">

**پنل مدیریت تانل‌های امن و مقاوم به سانسور — معماری مدرن دو-نود، رابط وب سفارشی، و آزادی متن‌باز**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)
[![Svelte](https://img.shields.io/badge/Svelte-5-FF3E00.svg)](https://svelte.dev/)
[![Docker](https://img.shields.io/badge/Docker-24.0+-2496ED.svg)](https://www.docker.com/)
[![Nginx](https://img.shields.io/badge/Nginx-1.25+-009639.svg)](https://www.nginx.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3.42+-003B57.svg)](https://www.sqlite.org/)

</div>

---

## 🚀 امکانات

- **۵ نوع تانل:** TCP، UDP، WebSocket، gRPC، TCPMux از طریق **GOST, Backhaul, Rathole, Chisel, FRP**
- **مدیریت یکپارچه نودها:** نودهای ایران و خارج از یک پنل واحد قابل مدیریت هستند
- **رابط وب مدرن:** Svelte 5 + Tailwind CSS با طراحی تاریک حرفه‌ای و نورون آبی/بنفش
- **CLI Tools:** ابزارهای خط فرمان `nosrat` و `nosrat-node`
- **Telegram Bot:** آمار پنل و بکاپ خودکار از طریق تلگرام
- **SSH Management:** تست اتصال، ترمینال زنده و نصب خودکار نود
- **مقایسه عددی نسخه Node.js:** نصب ایمن با پشتیبانی NVM
- **Docker-native:** استقرار با Docker Compose و شبکه‌ی Host
- **BBR + Sysctl:** بهینه‌سازی خودکار شبکه برای پایداری تانل‌ها

---

## 📋 پیش‌نیازها

- **سرور:** Ubuntu 22.04+ یا Debian 12+
- **Docker & Docker Compose** (به‌صورت خودکار نصب می‌شود)
- **Node.js 22+** (برای بیلد فرانت‌اند — اگر NVM نصب باشد، خودکار استفاده می‌شود)
- برای سرورهای ایرانی:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/manageitir/docker/main/install-ubuntu.sh | sh
  ```

---

## 🔧 نصب پنل

### نصب سریع

```bash
sudo bash -c "$(curl -sL https://raw.githubusercontent.com/pdnczone/Nosrat-Panel/main/setup.sh)"
```

### نصب دستی

<details>
<summary><strong>مراحل نصب دستی</strong></summary>

1. کلون مخزن:
```bash
git clone https://github.com/pdnczone/Nosrat-Panel.git
cd Nosrat-Panel
```

2. نصب سرویس‌ها با Docker:
```bash
sudo bash setup.sh
```

3. نصب CLI ابزارها:
```bash
sudo bash cli/install_cli.sh
```

4. ساخت ادمین:
```bash
nosrat admin create
```

5. دسترسی به پنل:
```
http://localhost:8000
```

</details>

---

## 🖥️ نصب نود

### معماری

- **نودهای ایران:** مدیریت تانل‌های معکوس (Rathole, Backhaul, Chisel, FRP) و اجرای GOST Forwarder
- **نودهای خارج:** مشارکت در تانل‌های معکوس و دریافت ترافیک از نودهای ایران

### نصب سریع نود

```bash
sudo bash -c "$(curl -sL https://raw.githubusercontent.com/pdnczone/Nosrat-Panel/main/scripts/nosrat-node.sh)"
```

### نصب دستی نود

<details>
<summary><strong>مراحل نصب دستی نود</strong></summary>

1. وارد شدن به دایرکتوری نود:
```bash
cd node
```

2. کپی گواهی CA پنل:
```bash
mkdir -p certs
# برای نودهای ایران:
cp /path/to/panel/certs/ca.crt certs/ca.crt
# برای سرورهای خارج:
# cp /path/to/panel/certs/ca-server.crt certs/ca.crt
```

3. ایجاد فایل `.env`:
```bash
cat > .env << EOF
NODE_API_PORT=8888
NODE_NAME=node-1
PANEL_CA_PATH=/etc/nosrat-node/certs/ca.crt
PANEL_ADDRESS=panel.example.com:443
EOF
```

4. اجرای نود:
```bash
docker compose up -d
```

> **نکته:** پنل نقش نودها (ایران یا خارج) را هنگام ثبت‌نام اعتبارسنجی می‌کند.

</details>

---

## 🛠️ ابزارهای CLI

### پنل CLI (`nosrat`)

**مدیریت ادمین:**
```bash
nosrat admin create      # ساخت ادمین
nosrat admin update      # بروزرسانی رمز عبور
```

**مدیریت پنل:**
```bash
nosrat status            # نمایش وضعیت سیستم
nosrat update            # بروزرسانی پنل (pull + recreate)
nosrat restart           # ری‌استارت پنل
nosrat logs              # نمایش لاگ‌ها
```

### نود CLI (`nosrat-node`)

```bash
nosrat-node status       # وضعیت نود
nosrat-node update       # بروزرسانی نود
nosrat-node restart      # ری‌استارت نود
nosrat-node logs         # نمایش لاگ نود
```

---

## 📖 انواع تانل

### GOST (فورواردینگ نود ایران)
- **TCP**: فورواردینگ ساده TCP
- **UDP**: فورواردینگ پکت‌های UDP
- **WebSocket (WS)**: فورواردینگ پروتکل WebSocket
- **gRPC**: فورواردینگ پروتکل gRPC
- **TCPMux**: مالتی‌پلکسینگ TCP برای اتصالات همزمان

تانل‌های GOST روی نودهای ایران اجرا می‌شوند و ترافیک را به سرورهای خارج فوروارد می‌کنند.

### Backhaul (تانل معکوس)
- **TCP / UDP**: تانل معکوس کم‌تأخیر با گزینه UDP-over-TCP
- **WS / WSMux**: WebSocket برای استقرار پس‌زمینه CDN
- **TCPMux**: مالتی‌پلکسینگ TCP
- **کنترل‌های پیشرفته:** تنظیم keepalive، sniffer، و پورت‌های سفارشی

### Rathole (تانل معکوس)
- **TCP**: تانل معکوس استاندارد TCP
- **WebSocket (WS)**: پشتیبانی از WebSocket

### Chisel (تانل معکوس)
تانل معکوس TCP پرسرعت برای اجرای سرویس‌ها از طریق نود ایران.

### FRP (تانل معکوس)
فورواردینگ معکوس قابل اعتماد TCP/UDP با پشتیبانی از IPv6.

---

## 🏗️ ساختار پروژه

```
Nosrat-Panel/
├── frontend/            # رابط وب Svelte 5 + Vite + Tailwind
├── panel/               # بک‌اند FastAPI + موتورهای تانل
│   ├── app/
│   │   ├── routers/     # API endpoints
│   │   ├── gost_forwarder.py
│   │   ├── backhaul_manager.py
│   │   ├── rathole_server.py
│   │   ├── chisel_server.py
│   │   ├── frp_server.py
│   │   ├── node_server.py
│   │   └── telegram_bot.py
│   └── Dockerfile
├── node/                # ایجنت نود (Docker)
├── scripts/             # اسکریپت‌های نصب
├── cli/                 # ابزارهای خط فرمان
├── nginx/               # کانفیگ Nginx
├── setup.sh             # اسکریپت نصب اصلی
└── docker-compose.yml   # استقرار سرویس‌ها
```

---

## 📝 لایسنس

این پروژه تحت لایسنس MIT منتشر شده است — [LICENSE](LICENSE)

---

## 📺 ارتباط با ما

- **YouTube:** [PDNC](https://youtube.com/@PDNC30)
- **Telegram:** [PDNCzone](https://t.me/PDNCzone)

---

<div align="center">

**ساخته شده با ❤️ توسط [PDNC](https://github.com/pdnczone)**

*امنیت دیجیتال، یک خط کد در یک زمان!*

</div>
