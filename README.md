# Claura

**Plain English contract risk assessment for UK construction subcontractors.**

NEC4 and JCT subcontracts reviewed in under 2 minutes. Red, amber, green per clause. Suggested negotiation wording included.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML / CSS / Vanilla JS |
| Backend | FastAPI + Python 3.11 |
| Model | Mistral 7B Instruct + LoRA (HuggingFace) |
| Database | PostgreSQL (SQLAlchemy async) |
| Cache | Redis |
| PDF parsing | PyMuPDF |
| Auth | JWT (python-jose) |
| Deploy | Docker Compose (local) / GCP Cloud Run (prod) |

---

## Model

Fine-tuned Mistral 7B Instruct v0.3 using LoRA on the CUAD legal dataset.

- **HuggingFace:** `Govardhan12345/legal-risk-classifier-lora`
- **F1 (weighted):** 0.887
- **Accuracy:** 88.99%
- **JSON parse success:** 100%
- **Benchmark:** Exceeds best zero-shot result in ContractEval 2025

---

## Project Structure

```
claura/
├── frontend/
│   ├── login.html          ← Login portal
│   └── dashboard.html      ← Main dashboard
│
├── backend/
│   ├── main.py             ← FastAPI app entry
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── routes/
│   │   ├── auth.py         ← Register, login, JWT
│   │   ├── upload.py       ← PDF upload + extraction
│   │   ├── analyse.py      ← Model inference + HITL
│   │   └── results.py      ← Retrieve past analyses
│   ├── services/
│   │   ├── model.py        ← Load HF model, run inference
│   │   ├── pdf_parser.py   ← PyMuPDF clause extraction
│   │   └── database.py     ← SQLAlchemy tables + session
│   ├── models/
│   │   └── schemas.py      ← Pydantic request/response types
│   └── middleware/
│       └── auth.py         ← JWT creation + verification
│
├── docker-compose.yml      ← Local dev (API + PostgreSQL + Redis)
└── .env.example            ← Environment variable template
```

---

## Run Locally

```bash
# 1. Clone
git clone https://github.com/YOUR-USERNAME/claura.git
cd claura

# 2. Set up environment
cp .env.example .env
# Edit .env with your values

# 3. Start with Docker Compose
docker-compose up --build

# API runs at:   http://localhost:8000
# Frontend at:   http://localhost:8000
# API docs at:   http://localhost:8000/docs
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | /auth/register | Register new user |
| POST | /auth/login | Login → returns JWT |
| POST | /upload/ | Upload contract PDF |
| POST | /analyse/{contract_id} | Run risk analysis |
| GET | /results/ | All past analyses |
| GET | /results/{contract_id} | Single analysis |
| POST | /analyse/correct/{clause_id} | HITL correction |
| GET | /health | Uptime check |

---

## Data Privacy

- All customer contract data stored on UK servers only
- UK GDPR compliant
- No data used to train third-party models
- HITL corrections stored locally for periodic retraining

---

## Roadmap

- [ ] NEC4 deviation detection vs standard form
- [ ] Tender pack multi-document review
- [ ] Negotiation wording generator
- [ ] Stripe payment integration
- [ ] GCP Cloud Run deployment
- [ ] Per-tenant LoRA adapter fine-tuning
