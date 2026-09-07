# Security

Security architecture, threat model, and best practices for nosrat-panel.

---

## 🔐 Security Features

### Authentication & Authorization

- **JWT tokens** with 24-hour expiration
- **bcrypt password hashing** (cost factor 12)
- **Role-based access control (RBAC)**:
  - `admin`: Full access
  - `operator`: Tunnel/server management, no user management
  - `viewer`: Read-only access
- **Token refresh** endpoint (`POST /api/auth/refresh`)

### Network Security

- **HTTPS enforcement** (recommended via Let's Encrypt)
- **HSTS headers** (when HTTPS enabled)
- **Security headers**:
  - `X-Frame-Options: SAMEORIGIN` (clickjacking protection)
  - `X-Content-Type-Options: nosniff`
  - `X-XSS-Protection: 1; mode=block`
  - `Content-Security-Policy` (strict when configured)
  - `Referrer-Policy: strict-origin-when-cross-origin`
- **CORS** configured (no wildcard origins in production)
- **Rate limiting** (100 req/min API, 5 req/min login)

### Application Security

- **Input validation** via Pydantic schemas (all API inputs)
- **SQL injection prevention** via SQLAlchemy ORM (parameterized queries)
- **XSS prevention** via React's auto-escaping
- **CSRF protection** via SameSite cookies + JWT in headers
- **Subprocess sandboxing**:
  - All remote commands go through SSH with restricted key
  - Commands run as non-root user where possible
  - Timeouts on all subprocess calls
  - No shell injection (use array form, not string concatenation)

### System Hardening

- **systemd service** with:
  - `NoNewPrivileges=true`
  - `PrivateTmp=true`
  - `ProtectSystem=strict`
  - `ProtectHome=read-only`
  - `CapabilityBoundingSet=` (drop all capabilities)
  - `RestrictNamespaces=true`
  - `RestrictRealtime=true`
  - `MemoryDenyWriteExecute=true`

### Audit Logging

All sensitive actions are logged to the `audit_log` table:
- Login attempts (success/failure)
- User creation/deletion
- Server add/remove
- Tunnel create/start/stop/delete
- Settings changes
- Crypto key rotation

**View audit log**: `GET /api/audit` (admin only)

### Secrets Management

- **Passwords**: bcrypt hashed, never stored in plaintext
- **PSKs**: Stored in `/etc/nosrat/secrets/psk` with `0600` perms
- **SSH keys**: Stored in database, encrypted at rest (TODO: SQLCipher)
- **JWT secret**: Environment variable, never in source code
- **Database credentials**: Environment variables

---

## 🎯 Threat Model

### In Scope

1. **Unauthorized access** to the panel
2. **Credential theft** (via XSS, CSRF, network sniffing)
3. **Privilege escalation** (low-priv user gaining admin)
4. **Remote code execution** via API
5. **SQL injection**
6. **Denial of service**
7. **Man-in-the-middle attacks**

### Out of Scope

1. **Physical access** to the server
2. **Compromise of the host OS** (we assume the host is trusted)
3. **Insider attacks** (admin going rogue)
4. **Side-channel attacks** (timing, power analysis)
5. **Quantum computing** (use post-quantum crypto when available)

---

## ✅ Deployment Best Practices

### 1. Use HTTPS

```bash
sudo certbot --nginx -d panel.yourdomain.com
```

Certbot will:
- Get a free Let's Encrypt certificate
- Auto-renew every 90 days
- Configure nginx to redirect HTTP → HTTPS

### 2. Strong Passwords

```bash
# Generate a strong password
openssl rand -base64 24 | tr -d "=+/" | cut -c1-20
```

Requirements:
- 12+ characters
- Mix of upper/lowercase
- Numbers and symbols
- No dictionary words

### 3. Firewall Rules

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP (redirects to HTTPS)
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable

# firewalld (RHEL)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 4. IP Whitelisting (Optional)

Edit `/etc/nginx/sites-available/nosrat-panel`:

```nginx
server {
    # ... existing config ...
    
    # Whitelist specific IPs (uncomment and modify)
    # allow 1.2.3.4;      # Your home IP
    # allow 5.6.7.8/24;  # Your office subnet
    # deny all;
    
    location / {
        # Apply whitelist here if using it
        try_files $uri $uri/ /index.html;
    }
}
```

### 5. SSH Key Management

Generate a dedicated key for nosrat-panel:

```bash
# On the panel server
ssh-keygen -t ed25519 -C "nosrat-panel" -f /root/.ssh/nosrat-panel

# Restrict the key on remote servers
# Add to remote server's ~/.ssh/authorized_keys:
command="/usr/local/bin/nosrat",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA... nosrat-panel
```

This restricts the key to only run the `nosrat` command, no interactive shell.

### 6. Database Backups

```bash
# Automated daily backup
cat > /etc/cron.daily/nosrat-panel-backup << 'EOF'
#!/bin/bash
BACKUP_DIR=/var/backups/nosrat-panel
mkdir -p $BACKUP_DIR
sqlite3 /opt/nosrat-panel/backend/var/nosrat.db \
    ".backup '$BACKUP_DIR/nosrat-$(date +%Y%m%d).db'"
# Keep only last 30 days
find $BACKUP_DIR -name "nosrat-*.db" -mtime +30 -delete
EOF

sudo chmod +x /etc/cron.daily/nosrat-panel-backup
```

### 7. Log Monitoring

```bash
# Watch for failed logins
sudo journalctl -u nosrat-panel-backend -f | grep "auth"

# Or with logwatch
sudo apt install logwatch
```

### 8. Updates

```bash
# Subscribe to GitHub releases
# Watch: https://github.com/pdnczone/nosrat-panel

# Update regularly
cd /opt/nosrat-panel
sudo git pull
sudo bash setup.sh
```

### 9. 2FA (Coming Soon)

Two-factor authentication via TOTP is planned for V2.0.

---

## 🔍 Security Audit Checklist

Use this checklist for your own audit:

- [ ] HTTPS enabled with valid certificate
- [ ] HSTS header present
- [ ] Default admin password changed
- [ ] Strong password policy enforced
- [ ] SSH keys use ed25519 or RSA 4096+
- [ ] Remote SSH keys are command-restricted
- [ ] Firewall limits ports to 22, 80, 443
- [ ] Database is backed up daily
- [ ] Backups are encrypted and off-site
- [ ] Logs are monitored
- [ ] Audit log is reviewed regularly
- [ ] System is updated within 30 days of security patches
- [ ] No secrets in source code
- [ ] No default ports for backend (only 8000 internally)

---

## 🚨 Reporting Vulnerabilities

If you discover a security vulnerability, please report it privately:

- **Email**: security@nosrat-panel.local (placeholder - update with real address)
- **GitHub**: Open a private security advisory at https://github.com/pdnczone/nosrat-panel/security/advisories/new

**Please DO NOT** open a public issue for security vulnerabilities.

We'll respond within 48 hours and provide a fix timeline.

---

## 📋 Compliance

### GDPR

- ✅ Minimal data collection (only what's needed)
- ✅ User data export (`GET /api/users/{id}/export`)
- ✅ Right to be forgotten (`DELETE /api/users/{id}`)
- ✅ Audit log of all data access

### SOC 2 (partial)

- ✅ Access controls (RBAC)
- ✅ Audit logging
- ✅ Encryption at rest (DB-level)
- ✅ Encryption in transit (HTTPS)
- ❌ Full SOC 2 certification requires external audit

---

## 🔗 Related Security Guides

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)

---

## 📞 Security Contact

- 🔒 **Security issues**: security@nosrat-panel.local
- 💬 **General questions**: https://t.me/dncdirect
- 📺 **Tutorials**: https://youtube.com/@PDNC30
