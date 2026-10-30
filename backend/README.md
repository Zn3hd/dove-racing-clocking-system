# Dove Racing Backend

Prototype source import is underway. The pure calculation engine and unit tests are included here. The complete FastAPI API and database SQL from the earlier prototype have **not yet been pushed**.

Run calculation tests from `backend/`:

```bash
pip install -r requirements.txt
python -m pytest tests/test_calculations.py -q
```

Use `.env.example` as a template for local configuration; do not commit `.env`.

Security note: QR clocking must not be activated without authenticated guests, anti-replay controls and review. RFID simulator events must not be treated as verified official arrivals.
