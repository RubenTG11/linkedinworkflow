# LinkedIn Post Creation System

Ein Multi-Agent AI System für die automatisierte Erstellung von LinkedIn Posts mit umfassender Profilanalyse und iterativem Writer-Critic Workflow.

## 🚀 Features

- **LinkedIn Profil Scraping** via Apify
- **AI-gestützte Profilanalyse** mit Stil- und Tonalitätserkennung
- **Automatische Themenextraktion** aus bestehenden Posts
- **Research Agent** für neue Content-Themen (Perplexity)
- **Writer-Critic Multi-Agent System** für Post-Erstellung
- **Schickes TUI** (Terminal User Interface) mit Textual
- **Supabase Datenbank** für persistente Speicherung
- **OpenAI & Perplexity Integration**

## 📋 Voraussetzungen

- Python 3.12+
- Supabase Account
- OpenAI API Key
- Perplexity API Key
- Apify Account

## 🛠️ Installation

### 1. Repository klonen und Setup

```bash
cd LinkedInWorkflow
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# oder
.venv\Scripts\activate  # Windows
```

### 2. Dependencies installieren

```bash
pip install -r requirements.txt
```

### 3. Umgebungsvariablen konfigurieren

Erstelle eine `.env` Datei basierend auf `.env.example`:

```bash
cp .env.example .env
```

Fülle die `.env` Datei mit deinen API Keys:

```env
# API Keys
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...
APIFY_API_KEY=apify_api_...

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...

# Apify
APIFY_ACTOR_ID=apify/linkedin-profile-scraper

# Development
DEBUG=true
LOG_LEVEL=INFO
```

### 4. Supabase Datenbank Setup

1. Gehe zu [Supabase](https://supabase.com) und erstelle ein neues Projekt
2. Öffne den SQL Editor
3. Führe das Schema aus: `config/supabase_schema.sql`

```sql
-- Kopiere den Inhalt von config/supabase_schema.sql
-- und führe ihn im Supabase SQL Editor aus
```

## 🎯 Nutzung

### TUI Starten

```bash
python main.py
```

### Workflow

#### 1. **New Customer Setup** 🚀
   - LinkedIn Profil wird gescraped
   - Alle Posts werden analysiert
   - Schreibstil wird extrahiert
   - Themen werden identifiziert
   - UUID wird generiert und gespeichert

#### 2. **Research Topics** 🔍
   - Neue Themen werden recherchiert (Perplexity)
   - Basierend auf Branche und Zielgruppe
   - Bereits behandelte Themen werden vermieden
   - 5-7 aktuelle Topic-Vorschläge

#### 3. **Create Post** ✍️
   - Thema auswählen
   - Writer erstellt initialen Post
   - Critic reviewed und gibt Feedback
   - Bis zu 10 Iterationen
   - Finaler Post wird gespeichert

#### 4. **View Status** 📊
   - Übersicht aller Kunden
   - Anzahl Posts, Topics, etc.
   - Status der Analysen

## 📁 Projektstruktur

```
LinkedInWorkflow/
├── src/
│   ├── agents/              # AI Agents
│   │   ├── base.py          # Base Agent Klasse
│   │   ├── profile_analyzer.py
│   │   ├── topic_extractor.py
│   │   ├── researcher.py
│   │   ├── writer.py
│   │   └── critic.py
│   ├── database/            # Datenbank
│   │   ├── client.py        # Supabase Client
│   │   └── models.py        # Pydantic Models
│   ├── scraper/             # LinkedIn Scraper
│   │   └── apify_scraper.py
│   ├── tui/                 # Terminal UI
│   │   └── app.py
│   ├── config.py            # Konfiguration
│   └── orchestrator.py      # Workflow Orchestrator
├── config/
│   └── supabase_schema.sql  # DB Schema
├── logs/                    # Log Files
├── main.py                  # Entry Point
├── requirements.txt
├── .env.example
└── README.md
```

## 🤖 AI Agents

### ProfileAnalyzerAgent
- Analysiert LinkedIn Profil und Posts
- Extrahiert Schreibstil, Tonalität, Perspektive
- Identifiziert linguistische Fingerabdrücke
- Erkennt Zielgruppe und Content-Strategie

### TopicExtractorAgent
- Extrahiert Themen aus bestehenden Posts
- Kategorisiert und clustert ähnliche Themen
- Speichert Topics mit Konfidenz-Score

### ResearchAgent
- Recherchiert aktuelle Themen (Perplexity)
- Filtert basierend auf Branche und Zielgruppe
- Vermeidet bereits behandelte Themen
- Liefert 5-7 konkrete Topic-Vorschläge

### WriterAgent
- Schreibt Posts im Stil der Person
- Nutzt Profil-Analyse für Authentizität
- Unterstützt Revisionen basierend auf Feedback

### CriticAgent
- Reviewed Posts auf Qualität und Authentizität
- Vergibt Scores (0-100)
- Gibt konkrete Verbesserungsvorschläge
- Genehmigt oder fordert Revision

## 🔧 Technologie-Stack

- **Python 3.12**
- **Textual** - Modernes TUI Framework
- **OpenAI GPT-4o** - Profil-Analyse, Writing, Critic
- **Perplexity** - Research & Topic Discovery
- **Apify** - LinkedIn Scraping
- **Supabase** - PostgreSQL Datenbank
- **Pydantic** - Data Validation
- **Loguru** - Logging

## 📊 Datenbank-Schema

Das System nutzt folgende Tabellen:

- `customers` - Kundendaten und LinkedIn URLs
- `linkedin_profiles` - Gescrapte Profildaten
- `linkedin_posts` - Gescrapte Posts
- `topics` - Extrahierte und recherchierte Themen
- `profile_analyses` - AI-generierte Profilanalysen
- `research_results` - Research-Ergebnisse
- `generated_posts` - Erstellte Posts mit Iterationen

## 🎨 TUI Navigation

- **Arrow Keys / Tab** - Navigation zwischen Elementen
- **Enter** - Button/Option auswählen
- **Escape** - Zurück zum Hauptmenü
- **Q** - Quit Application

## 📝 Logging

Logs werden automatisch in `logs/` gespeichert:
- Tägliche Rotation
- 7 Tage Retention
- Detaillierte Error-Tracking

## 🔒 Sicherheit

- API Keys niemals committen (`.env` ist in `.gitignore`)
- Supabase Row Level Security aktivieren
- Apify Proxy für LinkedIn Scraping nutzen

## 🐛 Troubleshooting

### "Supabase connection failed"
- Prüfe `SUPABASE_URL` und `SUPABASE_KEY` in `.env`
- Stelle sicher, dass das Schema ausgeführt wurde

### "Apify scraping failed"
- Prüfe `APIFY_API_KEY`
- Stelle sicher, dass der Actor `apify/linkedin-profile-scraper` verfügbar ist
- LinkedIn URLs müssen öffentlich zugänglich sein

### "OpenAI rate limit"
- Warte kurz und versuche es erneut
- Erhöhe Rate Limits in deinem OpenAI Account

## 🚧 TODO / Roadmap

- [ ] Multi-Customer Selection in TUI
- [ ] Topic Selection Interface
- [ ] Export zu n8n Workflow
- [ ] LinkedIn Publishing Integration
- [ ] Analytics Dashboard
- [ ] Batch-Processing für mehrere Posts

## 📄 Lizenz

Proprietary - Alle Rechte vorbehalten

## 👥 Author

Entwickelt als AI-Automatisierungs-Projekt für LinkedIn Content Creation.

## 🙏 Credits

- OpenAI für GPT-4o
- Perplexity für Research
- Apify für LinkedIn Scraping
- Textualize für Textual Framework
# linkedinworkflow
