# AIcontent — short drama сату боты

Қазақ тіліндегі Telegram бот: қысқа метражды сериалдарды сатады.
Алғашқы бөлімдер тегін, толық нұсқа — Kaspi арқылы төлем, содан кейін
жабық арнаға автоматты қолжетімділік.

Python 3.12 + aiogram 3. Төлем — [Arzan Pay](https://pay.arzan.cloud/docs).

## Орнату

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env      # токен мен API кілтті қойыңыз
```

## Іске қосу

```bash
.venv/bin/python -m bot
```

## Тесттер

```bash
.venv/bin/pytest
```

## Құжаттар

- Дизайн: `docs/superpowers/specs/2026-11-22-shortdrama-bot-design.md`
- Жоспар: `docs/superpowers/plans/2026-11-22-shortdrama-bot.md`
