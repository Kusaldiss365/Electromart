# ⚡ ElectroMart – AI-Powered Multi-Agent Customer Support System

ElectroMart is a full-stack AI-powered e-commerce assistant designed to handle **product inquiries, recommendations, promotions, order tracking, returns, and technical support** using a multi-agent architecture.

The project is structured as a **monorepo** with separate frontend and backend applications, each having its own setup and documentation.

<br>

<p align="center">
  <a href="https://youtu.be/RGqzeBq9rMs" target="_blank" rel="noopener noreferrer">
    <img 
      src="https://img.youtube.com/vi/RGqzeBq9rMs/maxresdefault.jpg" 
      alt="ElectroMart Demo Video" 
      width="640" 
      style="border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);"
    />
    <br><br>
    <strong style="font-size: 1.3em;">▶️ Watch Demo Video</strong>
  </a>
</p>

---

## 📂 Repository Structure

```
electromart/
├─ frontend/            # Frontend application (UI)
│  └─ README.md         # Frontend-specific documentation
│
├─ backend/             # Backend application (API + AI agents)
│  ├─ ARCHITECTURE.md   # System architecture documentation
│  └─ README.md         # Backend-specific documentation
│
└─ README.md            # This file (project overview)
```

---

## 🧠 System Overview

ElectroMart uses an **agent-based AI architecture** where user messages are routed to specialized agents based on intent:

- **Sales Agent** – product specs, pricing (LKR), availability, recommendations
- **Marketing Agent** – promotions, discounts, campaigns
- **Orders Agent** – order tracking, delivery, returns, refunds
- **Support Agent** – troubleshooting, warranty, setup, support tickets
- **Purchase Agent** - Creates sales leads by capturing user purchase intent in chat

Intent routing is **deterministic, memory-aware**, and protected by automated accuracy tests.

---

## 🎯 Key Features

- AI-driven conversational shopping experience
- Deterministic intent routing with ≥85% accuracy enforcement
- PostgreSQL + pgvector for product and order data
- Clear separation of concerns using multiple AI agents
- Fully testable and reproducible backend logic
- Frontend and backend developed and deployed independently

---

## 🖥 Frontend

The **frontend** provides the user interface for interacting with the ElectroMart assistant.

**Location:**  
📁 `frontend/`

**Setup & usage:**  
👉 See **[`frontend/README.md`](./frontend/README.md)** for:
- Tech stack details
- Installation steps
- Development & build commands
- UI behavior

---

## ⚙️ Backend

The **backend** powers the AI agents, intent routing, database access, and APIs.

**Location:**  
📁 `backend/`

**Setup & usage:**  
👉 See **[`backend/README.md`](./backend/README.md)** for:
- Environment configuration
- Docker & database setup
- Running the API server
- Intent routing evaluation & tests
- Architecture details

---

## 🧪 Quality & Testing

- Intent routing accuracy is evaluated using a labeled dataset
- Automated tests enforce a **minimum accuracy threshold**
- Regression-safe design for AI routing logic

(Full testing instructions are available in the backend README.)

---

## 👤 Maintainer

**Kusal Dissanayake**  
Software Engineer | AI & Backend Systems

---

## 📌 Notes

- Each folder (`frontend`, `backend`) is independently runnable
- Please follow the README inside each folder for setup
- Backend tests demonstrate deterministic AI behavior and measurable quality guarantees
