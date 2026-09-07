# User Guide

Bilingual guide (فارسی + English) for using nosrat-panel.

---

## 🇮🇷 فارسی

### ورود به سیستم

1. مرورگر را باز کنید و به آدرس پنل بروید: `http://YOUR_SERVER_IP/`
2. با اطلاعات پیش‌فرض وارد شوید: `admin` / `admin`
3. **فوراً رمز عبور را تغییر دهید** (Settings → Users)

### ایجاد اولین سرور

1. از منوی کناری روی **Servers** کلیک کنید
2. دکمه **+ Add Server** را بزنید
3. اطلاعات را وارد کنید:
   - **Name**: نام دلخواه (مثلاً "Iran-1")
   - **Host**: آی‌پی سرور
   - **SSH Port**: 22
   - **SSH User**: root
   - **SSH Key**: کلید خصوصی SSH
4. روی **Test Connection** بزنید تا اتصال تست شود
5. **Save** کنید

### ایجاد اولین تونل

1. به **Tunnels** بروید
2. روی **+ Create Tunnel** کلیک کنید
3. **Step 1**: نوع تونل را انتخاب کنید (مثلاً GRE-over-IPsec)
4. **Step 2**: سرور را انتخاب کنید
5. **Step 3**: فرم wizard را پر کنید (IP ها، PSK، و...)
6. **Step 4**: تأیید و ساخت
7. پس از ساخت، روی **Start** بزنید تا تونل فعال شود

### مشاهده وضعیت تونل

- در صفحه **Tunnels** لیست همه تونل‌ها با badge وضعیت نمایش داده می‌شود
- کلیک روی هر تونل جزئیات کامل را نشان می‌دهد
- تب **Status**: وضعیت real-time از WebSocket
- تب **Logs**: لاگ‌های real-time

### اجرای Health Check

1. به صفحه جزئیات تونل بروید
2. تب **Health** را باز کنید
3. یکی از گزینه‌ها را انتخاب کنید:
   - **Quick**: بررسی سریع
   - **Detailed**: بررسی کامل با diagnostic
   - **Monitoring**: نظارت مداوم (10 ثانیه)

### اجرای Speed Test

1. به صفحه جزئیات تونل بروید
2. تب **Speed** را باز کنید
3. نوع تست را انتخاب کنید:
   - **Ping**: تست latency
   - **Full**: تست کامل (ping + throughput)
   - **iperf3**: تست پهنای باند

### مدیریت کاربران (Admin)

1. به **Users** بروید (فقط admin)
2. می‌توانید:
   - کاربر جدید اضافه کنید
   - رمز عبور را عوض کنید
   - نقش‌ها را تغییر دهید (admin/operator/viewer)
   - کاربر را حذف/غیرفعال کنید

### مدیریت Crypto

1. به **Crypto** بروید
2. **Generate PSK**: کلید جدید 256 یا 512 بیتی بسازید
3. **Rotate**: کلید فعلی را عوض کنید
4. **Algorithm**: الگوریتم رمزنگاری را تغییر دهید (AES128/256, ChaCha20)
5. **View**: کلید فعلی را ببینید (masked)

---

## 🇬🇧 English

### Logging In

1. Open your browser and navigate to: `http://YOUR_SERVER_IP/`
2. Login with default credentials: `admin` / `admin`
3. **Change the password immediately** (Settings → Users)

### Creating Your First Server

1. Click **Servers** in the sidebar
2. Click **+ Add Server**
3. Fill in the details:
   - **Name**: A friendly name (e.g., "Iran-1")
   - **Host**: Server IP address
   - **SSH Port**: 22
   - **SSH User**: root
   - **SSH Key**: Your SSH private key
4. Click **Test Connection** to verify
5. Click **Save**

### Creating Your First Tunnel

1. Go to **Tunnels**
2. Click **+ Create Tunnel**
3. **Step 1**: Select tunnel type (e.g., GRE-over-IPsec)
4. **Step 2**: Select a server
5. **Step 3**: Fill the wizard form (IPs, PSK, etc.)
6. **Step 4**: Review and create
7. After creation, click **Start** to activate the tunnel

### Viewing Tunnel Status

- The **Tunnels** page shows all tunnels with status badges
- Click on any tunnel to see full details
- **Status** tab: Real-time status via WebSocket
- **Logs** tab: Real-time logs

### Running Health Check

1. Go to a tunnel's detail page
2. Open the **Health** tab
3. Choose:
   - **Quick**: Fast check
   - **Detailed**: Full diagnostic
   - **Monitoring**: Continuous monitoring (10s loop)

### Running Speed Test

1. Go to a tunnel's detail page
2. Open the **Speed** tab
3. Choose:
   - **Ping**: Latency test
   - **Full**: Full test (ping + throughput)
   - **iperf3**: Bandwidth test

### Managing Users (Admin)

1. Go to **Users** (admin only)
2. You can:
   - Add new users
   - Change passwords
   - Change roles (admin/operator/viewer)
   - Delete/deactivate users

### Managing Crypto

1. Go to **Crypto**
2. **Generate PSK**: New 256 or 512-bit key
3. **Rotate**: Replace current key
4. **Algorithm**: Change encryption algorithm (AES128/256, ChaCha20)
5. **View**: View current key (masked)

---

## 💡 Tips

### Performance
- Use **Dark mode** for better night-time viewing
- Pin frequently used tunnels to the dashboard (coming soon)
- Use the **search** in the topbar to quickly find tunnels

### Security
- Always use **HTTPS** in production (see [INSTALLATION.md](INSTALLATION.md))
- Use **strong passwords** (12+ characters, mixed case, numbers, symbols)
- **Restrict access** to the panel by IP (nginx allow/deny)
- **Audit logs** are available in Settings → Audit Log
- **Enable 2FA** (coming soon)

### Troubleshooting
- **Backend not responding?** Check `journalctl -u nosrat-panel-backend -n 50`
- **Nginx 502?** Check if backend is running: `systemctl status nosrat-panel-backend`
- **Can't login?** Reset password via CLI (see [INSTALLATION.md](INSTALLATION.md#cannot-login))

---

## 🆘 Need Help?

- 📚 [Installation Guide](INSTALLATION.md)
- 🔌 [Plugin Development](PLUGIN_DEVELOPMENT.md)
- 🔐 [Security](SECURITY.md)
- 📖 [API Reference](API.md)
- 💬 [Telegram Support](https://t.me/dncdirect)
- 📺 [YouTube Tutorials](https://youtube.com/@PDNC30)
