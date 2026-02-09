# ElectroMart – System Architecture

This document describes the architecture of **ElectroMart**, an AI-powered conversational commerce backend built with FastAPI, LangGraph, and PostgreSQL (pgvector). The focus is on **deterministic agent behavior**, **strict domain boundaries**, and **persistent conversation state**.

---

## 1. High-Level Overview

ElectroMart processes user conversations through a **single conversational endpoint**, routes each message through an **intent router**, and delegates handling to one of several **domain-specific agents**. Each agent is backed by database tools and strict guardrails to avoid hallucinations or unintended side effects.

Key characteristics:
- Rules-first routing with LLM fallback
- One-response-per-message agents
- Persistent conversation memory
- Deterministic fallbacks when no OpenAI key is present

---

## 2. Main Components

### Client (Web / Mobile)
- Sends messages with a `conversation_id`
- Receives one complete response per request
- Supports text or voice input (tracked via metadata)

### FastAPI Backend
- Entry point for chat requests
- Loads conversation state and recent message history
- Executes the LangGraph workflow
- Persists messages and updated state

### LangGraph Orchestrator
- Controls the conversation flow
- Routes requests using a router node
- Ensures only one agent handles a request

Flow:
```
router → sales | marketing | support | orders → END
```

### Database (PostgreSQL + pgvector)
- Relational data for products, orders, tickets, returns, promotions, and leads
- JSON-based conversation memory
- Vector embeddings for FAQ semantic search

### External Services
- OpenAI (chat completions + embeddings, optional)
- SMTP (lead notification emails)

---

## 3. Intent Routing

The **Intent Router** determines which agent should handle a message.

Routing labels:
- `sales`
- `marketing`
- `support`
- `orders`

### Routing Strategy
- Keyword + regex rules first
- Sticky flows via `memory.active_flow`
- Safety overrides (e.g., pending return → orders)
- LLM fallback only if rules fail and API key exists

This ensures predictable routing even in multi-turn flows.

---

## 4. Agents

Each agent:
- Produces exactly one response per message
- Uses tools as the source of truth
- Writes only allowed data

### 4.1 Sales Agent

**Responsibilities**
- Product specifications and comparisons
- Share Pricing
- Stock availability
- Product recommendations (max 1–3)

**Key Rules**
- Recommends only in-stock products
- Asks one clarifying question if input is vague
- Does not handle checkout or payment

**Memory Used**
- `last_products`

**Tools**
- Product search service

---

### 4.2 Marketing Agent

**Responsibilities**
- Explain active promotions
- Suggest 1–3 deals when asked

**Key Rules**
- Uses DB-backed promotions only
- No assumptions if request is vague
- Asks one clarification with quick options

**Tools**
- Promotion listing service

---

### 4.3 Support Agent

**Responsibilities**
- Troubleshooting and setup guidance
- Warranty and repair assistance
- Support ticket creation (strictly gated)

**Ticket Rules**
- Ticket created only if user explicitly asks or confirms
- One active ticket per conversation unless user requests another

**Memory Used**
- `support_ticket_id`
- `ticket_pending`

**Tools**
- FAQ semantic search
- Support ticket creation

---

### 4.4 Orders & Logistics Agent

**Responsibilities**
- Order status and tracking
- Returns, refunds, cancellations, exchanges
- Return request lookup

**Return Flow Rules**
- Requires both order ID and valid reason
- No automatic return creation
- Multi-turn gated flow using memory

**Memory Used**
- `last_order_id`
- `return_pending`
- `last_return_request_id`

**Tools**
- Order lookup
- Return request creation
- FAQ semantic search

---

### 4.5 Purchase Agent

**Responsibilities**
- Capture user intent to purchase a product
- Collect required user details (product, name, phone number)
- Create a sales lead for follow-up by the sales team

**Purchase Flow Rules**
- Starts only when user types exactly: buy now
- Multi-turn gated flow: product → name → phone
- No payment processing or order creation
- Lead is created only after all required details are collected

**Memory Used**
- `buy_flow (active state, current step)`
- `last_lead_id`
- `last_lead_product`

**Tools**
- Product search (model/SKU lookup)
- Sales lead creation (with email notification)

---

## 5. Conversation Persistence

### Conversations
- One row per conversation/session
- Stores JSON `state` (agent memory)

### Messages
- Immutable chat log
- Stores role, content, route, and input type
- Used for routing and LLM context

This separation allows:
- Long-term memory via state
- Auditable chat history via messages

---

## 6. Data Model Summary

| Table | Purpose |
|-----|--------|
| products | Product catalog and pricing |
| orders | Existing customer orders |
| return_requests | Order return lifecycle |
| support_tickets | Technical support cases |
| promotions | Marketing campaigns |
| leads | Sales leads |
| conversations | Session state |
| messages | Chat history |
| faqs | FAQ knowledge base with embeddings |

---

## 7. RAG & Embeddings

- FAQs are embedded using a 1536-dim vector
- Uses pgvector `<->` similarity search
- Deterministic fake embeddings used when OpenAI key is missing

This guarantees functionality in offline/local environments.

---

## 8. Lead Creation

- Leads are created only via explicit logic (not implicit intent)
- Stored in DB, then email notification is sent
- Email is sent only after successful DB commit

---

## 9. Deployment

### Local Development
- PostgreSQL + pgvector via Docker
- FastAPI via Uvicorn
- `.env` for configuration

### Production (Recommended)
- Containerized services
- Background workers for email and heavy tasks
- Observability (structured logs, traces)

---

## 10. Design Principles

- Explicit over implicit
- Deterministic first, LLM second
- One agent, one responsibility
- Database as source of truth
- Memory-driven multi-turn safety

---

