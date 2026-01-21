# Deployment Guide - LinkedIn Post Creation System

Diese Anleitung erklärt, wie du die LinkedIn Post App auf deinem Server mit Docker deployen kannst.

## Voraussetzungen

- Ein Server (VPS/Cloud) mit:
  - Ubuntu 20.04+ oder Debian 11+
  - Mindestens 1GB RAM
  - Docker & Docker Compose installiert
- Domain (optional, für HTTPS)
- API Keys:
  - OpenAI API Key
  - Perplexity API Key
  - Apify API Key
  - Supabase URL & Key

---

## Schritt 1: Server vorbereiten

### Docker installieren (falls nicht vorhanden)

```bash
# System aktualisieren
sudo apt update && sudo apt upgrade -y

# Docker installieren
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose installieren
sudo apt install docker-compose-plugin -y

# Aktuellen User zur Docker-Gruppe hinzufügen
sudo usermod -aG docker $USER

# Neu einloggen oder:
newgrp docker

# Testen
docker --version
docker compose version
```

---

## Schritt 2: Projekt auf den Server laden

### Option A: Mit Git (empfohlen)

```bash
# Repository klonen
git clone https://github.com/dein-username/LinkedInWorkflow.git
cd LinkedInWorkflow
```

### Option B: Mit SCP (von deinem lokalen Rechner)

```bash
# Auf deinem lokalen Rechner:
scp -r /pfad/zu/LinkedInWorkflow user@dein-server:/home/user/
```

### Option C: Mit rsync

```bash
# Auf deinem lokalen Rechner:
rsync -avz --exclude '.env' --exclude '__pycache__' --exclude '.git' \
  /pfad/zu/LinkedInWorkflow/ user@dein-server:/home/user/LinkedInWorkflow/
```

---

## Schritt 3: Umgebungsvariablen konfigurieren

```bash
cd LinkedInWorkflow

# .env Datei aus Vorlage erstellen
cp .env.example .env

# .env bearbeiten
nano .env
```

### Wichtige Einstellungen in der `.env`:

```env
# Web-Passwort (UNBEDINGT ÄNDERN!)
WEB_PASSWORD=dein-sicheres-passwort-hier

# API Keys (deine echten Keys eintragen)
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...
APIFY_API_KEY=apify_api_...

# Supabase
SUPABASE_URL=https://dein-projekt.supabase.co
SUPABASE_KEY=dein-supabase-key

# Production Settings
DEBUG=false
LOG_LEVEL=INFO
```

**Wichtig:** Die `.env` Datei sollte NIEMALS committed werden!

---

## Schritt 4: Docker Container starten

```bash
# Im Projektverzeichnis:
cd LinkedInWorkflow

# Container bauen und starten
docker compose up -d --build

# Logs ansehen
docker compose logs -f

# Status prüfen
docker compose ps
```

Die App ist jetzt unter `http://dein-server:8000` erreichbar.

---

## Schritt 5: Firewall konfigurieren (optional aber empfohlen)

```bash
# UFW installieren (falls nicht vorhanden)
sudo apt install ufw -y

# SSH erlauben (WICHTIG - sonst sperrst du dich aus!)
sudo ufw allow ssh

# Port 8000 erlauben
sudo ufw allow 8000

# Firewall aktivieren
sudo ufw enable

# Status prüfen
sudo ufw status
```

---

## Schritt 6: Reverse Proxy mit Nginx & SSL (empfohlen für Production)

### Nginx installieren

```bash
sudo apt install nginx -y
```

### Nginx Konfiguration erstellen

```bash
sudo nano /etc/nginx/sites-available/linkedin-posts
```

Inhalt:

```nginx
server {
    listen 80;
    server_name deine-domain.de;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
}
```

### Nginx aktivieren

```bash
# Symlink erstellen
sudo ln -s /etc/nginx/sites-available/linkedin-posts /etc/nginx/sites-enabled/

# Default-Site entfernen
sudo rm /etc/nginx/sites-enabled/default

# Konfiguration testen
sudo nginx -t

# Nginx neu starten
sudo systemctl restart nginx
```

### SSL mit Let's Encrypt (kostenlos)

```bash
# Certbot installieren
sudo apt install certbot python3-certbot-nginx -y

# SSL-Zertifikat beantragen
sudo certbot --nginx -d deine-domain.de

# Auto-Renewal testen
sudo certbot renew --dry-run
```

---

## Nützliche Befehle

### Container Management

```bash
# Container stoppen
docker compose down

# Container neu starten
docker compose restart

# Container neu bauen (nach Code-Änderungen)
docker compose up -d --build

# In Container einloggen
docker compose exec linkedin-posts bash

# Logs ansehen (live)
docker compose logs -f

# Logs der letzten 100 Zeilen
docker compose logs --tail=100
```

### Updates einspielen

```bash
# Code aktualisieren (mit Git)
git pull

# Container neu bauen
docker compose up -d --build
```

### Backup

```bash
# .env sichern (enthält alle Secrets!)
cp .env .env.backup

# Alle Daten sind in Supabase - kein lokales Backup nötig
```

---

## Troubleshooting

### Container startet nicht

```bash
# Logs ansehen
docker compose logs linkedin-posts

# Container-Status prüfen
docker compose ps -a

# Neustart erzwingen
docker compose down && docker compose up -d --build
```

### Port bereits belegt

```bash
# Prüfen was auf Port 8000 läuft
sudo lsof -i :8000

# Prozess beenden
sudo kill -9 <PID>
```

### Keine Verbindung zu Supabase

1. Prüfe ob SUPABASE_URL und SUPABASE_KEY korrekt sind
2. Prüfe ob der Server ausgehende Verbindungen erlaubt
3. Teste: `curl -I https://dein-projekt.supabase.co`

### Passwort vergessen

```bash
# .env bearbeiten
nano .env

# WEB_PASSWORD ändern

# Container neu starten
docker compose restart
```

---

## Sicherheitsempfehlungen

1. **Starkes Passwort verwenden** - Mindestens 16 Zeichen, Sonderzeichen
2. **HTTPS aktivieren** - Mit Nginx + Let's Encrypt (siehe Schritt 6)
3. **Firewall konfigurieren** - Nur nötige Ports öffnen
4. **Server aktuell halten** - `sudo apt update && sudo apt upgrade`
5. **Docker aktuell halten** - `sudo apt upgrade docker-ce`
6. **Keine API Keys committen** - .env in .gitignore

---

## Monitoring (optional)

### Einfaches Health-Check Script

```bash
# health-check.sh erstellen
cat > health-check.sh << 'EOF'
#!/bin/bash
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/login | grep -q "200"; then
    echo "$(date): OK"
else
    echo "$(date): FEHLER - Neustart..."
    docker compose restart
fi
EOF

chmod +x health-check.sh

# Als Cron-Job (alle 5 Minuten)
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/user/LinkedInWorkflow/health-check.sh >> /var/log/linkedin-health.log 2>&1") | crontab -
```

---

## Architektur

```
┌─────────────────────────────────────────────────────────┐
│                        Internet                          │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 Nginx (Port 80/443)                      │
│                 - SSL Termination                        │
│                 - Reverse Proxy                          │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Docker Container (Port 8000)                │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │              FastAPI Application                    │ │
│  │                                                     │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │ │
│  │  │   Web UI    │  │    API      │  │  Agents    │ │ │
│  │  │  (Jinja2)   │  │  Endpoints  │  │ (AI Logic) │ │ │
│  │  └─────────────┘  └─────────────┘  └────────────┘ │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Supabase │    │  OpenAI  │    │ Perplexity│
    │    DB    │    │   API    │    │    API    │
    └──────────┘    └──────────┘    └──────────┘
```

---

## Support

Bei Problemen:
1. Logs prüfen: `docker compose logs -f`
2. GitHub Issues öffnen
3. Container neu bauen: `docker compose up -d --build`
