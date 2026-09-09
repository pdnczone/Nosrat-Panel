<div align="center">

# Nosrat Panel
### پنل پیشرفته مدیریت تانل و ارتباطات امن شبکه

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-teal.svg)](https://fastapi.tiangolo.com/)
[![Svelte](https://img.shields.io/badge/Svelte-5-orange.svg)](https://svelte.dev/)
[![Docker](https://img.shields.io/badge/Docker-24.0%2B-blue.svg)](https://www.docker.com/)

**نصرت‌پنل** یک راه‌حل جامع، مدرن و متن‌باز برای مدیریت تانل‌های شبکه، ارتباطات سرور ایران و خارج، و عبور از محدودیت‌هاست. این پنل با معماری دو-نود (Client-Server) و رابط کاربری اختصاصی، پایداری و امنیت حداکثری را فراهم می‌کند.

</div>

---

## 🌟 ویژگی‌های کلیدی

- 🚀 **معماری مدرن دو-نود:** مدیریت همزمان نودهای ایران و خارج با ارتباط رمزنگاری شده
- ⚡ **پشتیبانی از پروتکل‌های قدرتمند:** GRE-over-IPsec، GOST، Backhaul، Rathole، Chisel و FRP
- 🎨 **رابط وب اختصاصی (Svelte 5):** طراحی مدرن، واکنش‌گرا با تم تاریک و تجربه کاربری روان
- 🛠️ **ابزار خط فرمان (CLI):** کنترل کامل سرور و نودها با دستورات ساده `nosrat` و `nosrat-node`
- 🤖 **ربات تلگرام:** مدیریت هشدارها، وضعیت نودها و گزارش‌ها
- 🐳 **مبتنی بر داکر:** استقرار کاملاً ایزوله، خودکار و بدون تداخل با سیستم‌عامل
- 🔒 **امنیت و پایداری:** مدیریت خودکار گواهی SSL، فایروال و بهینه‌سازی پارامترهای شبکه (BBR)

---

## 📋 پیش‌نیازهای سیستم

- **سیستم‌عامل:** Ubuntu 22.04+ یا Debian 12+
- **دسترسی:** Root
- **ابزارها:** Docker و Docker Compose (به‌صورت خودکار در نصب‌کننده بررسی و نصب می‌شوند)

---

## ⚙️ نصب و راه‌اندازی سریع

برای نصب پنل روی سرور اصلی، دستور زیر را اجرا کنید:

```bash
sudo bash -c "$(curl -sL https://raw.githubusercontent.com/pdnczone/Nosrat-Panel/main/setup.sh)"
```

این اسکریپت به‌صورت خودکار موارد زیر را انجام می‌دهد:
1. بررسی و نصب وابستگی‌های سیستم (Python, Docker, Nginx, Certbot)
2. راه‌اندازی دیتابیس و کانتینرهای بک‌اند
3. بیلد و آماده‌سازی فرانت‌اند اختصاصی نصرت
4. تنظیم سرویس‌های systemd و پایش خودکار

---

## 🖥️ نصب نود (Agent)

برای اتصال سرورهای دیگر (نودهای واسط یا خارج) به پنل مرکزی، از اسکریپت نصب نود استفاده کنید:

```bash
sudo bash -c "$(curl -sL https://raw.githubusercontent.com/pdnczone/Nosrat-Panel/main/scripts/nosrat-node.sh)"
```

---

## 🛠️ ابزارهای مدیریتی (CLI)

پس از نصب، دستورات زیر در دسترس شما خواهند بود:

### مدیریت پنل (`nosrat`)
- `nosrat status` — نمایش وضعیت سلامت و سرویس‌ها
- `nosrat admin create` — ایجاد یا بازیابی حساب مدیریت
- `nosrat restart` — راه‌اندازی مجدد سرویس‌ها
- `nosrat logs` — مشاهده لاگ‌های زنده

### مدیریت نود (`nosrat-node`)
- `nosrat-node status` — بررسی وضعیت اتصال نود
- `nosrat-node restart` — راه‌اندازی مجدد نود

---

## 🗑️ حذف کامل (Uninstall)

اگر نیاز به پاکسازی کامل پنل و سرویس‌ها داشتید:

```bash
sudo bash -c "$(curl -sL https://raw.githubusercontent.com/pdnczone/Nosrat-Panel/main/uninstall.sh)"
```

---

## 📜 لایسنس

این پروژه تحت لایسنس **MIT** منتشر شده است. اطلاعات بیشتر در فایل [LICENSE](LICENSE) موجود است.

---

<div align="center">

**توسعه‌یافته با ❤️ توسط تیم [PDNC](https://github.com/pdnczone)**

</div>
