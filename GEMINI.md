## Conversational Banking Agent with LangGraph

### Overview
You are building a **stateful, agentic orchestration system** for conversational banking using **LangGraph**.  
The system executes banking operations (fund transfers, inquiries, deposits, etc.) through natural-language dialogue while enforcing **security, compliance, and auditability**.

LangGraph models each agent as a node in a directed graph.  
Shared state is carried across nodes and serialized as JSON for determinism, traceability, and recovery.

Please using uv as package manager, I usually using uv init and add the package using uv add ..
Then to run using uv run python

---

### 🖥️ Development Phases

**Phase 1 – CLI Chat Prototype**  
- The initial version will run entirely in the **command-line interface (CLI)**.  
- Purpose: test LangGraph orchestration, agent flow, and conversation logic before adding web or API layers.  
- Input/output handled via console (e.g., `prompt_toolkit` or `rich` UI).  
- CLI version supports:
  - Live conversation loop  
  - Context switching between intents  
  - State inspection and debugging  

**Phase 2 – API & Frontend Integration**  
- Once CLI logic stabilizes, expose the LangGraph runtime via REST or WebSocket API.  
- API will connect to front-end clients (web, mobile, etc.) and integrate authentication, persistence, and analytics layers.  
- The CLI and API will share the same agent core and configuration system.

---

## 1️⃣ General Architecture

### Core Pipeline
```
[User Input]
  ↓
[Guardrails] → [Intent Classifier]
  ↓
 ├── PAYMENT → [Payment Subgraph]
 ├── FAQ → [FAQ (RAG) Subgraph]
 ├── INQUIRY → [Inquiry Node]
 └── Clarification → [Loop → Intent]
        ↓
     [Audit / End]
```

### Agent Roles
| Agent | Purpose |
|--------|----------|
| **Guardrails** | Screen unsafe / non-compliant inputs. |
| **Intent Classifier** | Identify intent and route message. |
| **Action Agents** | Execute domain tasks (Payment, Inquiry, Deposit). |
| **FAQ / RAG** | Retrieve factual answers from knowledge base. |
| **Audit** | Record compliant, anonymized session logs. |

Each message re-enters the Guardrails → Intent pipeline to support context switching mid-conversation.

---

## 2️⃣ Memory and Clarification Handling

- System maintains **session-bound ephemeral memory** for conversational continuity.  
- The `State` object stores partial task data and recent history:

```json
{
  "conversation_history": [
    {"role": "user", "content": "I want to send money to Jane"},
    {"role": "assistant", "content": "How much would you like to send?"}
  ],
  "transaction_fields": {
    "recipient": "Jane",
    "amount": null
  }
}
```

- Agents use this to ask clarifying questions until required fields are complete.  
- After the session ends, sensitive data is discarded; only anonymized audit metadata persists.

---

## 3️⃣ Context Switching and Task Resumption

- Each new user message is **re-classified**; intent can change any time.  
- Partial workflows are stored as:

```json
{
  "pending_task": {
    "type": "PAYMENT",
    "fields": {"recipient": "Anna", "amount": null},
    "status": "WAITING_FOR_AMOUNT"
  },
  "current_intent": "INQUIRY"
}
```

- If the user diverts (e.g., asks a balance question), system handles the inquiry, then **resumes the pending task** automatically.  
- This enables natural mid-dialogue transitions such as:

> “Transfer to Anna → What’s my balance? → What’s transfer limit? → Okay transfer 10 → Confirm.”

---

## 4️⃣ Task Definitions and Required Fields

Each intent corresponds to a **task schema** defining:
- Required and optional fields  
- Validation rules  
- Whether confirmation is needed  
- The backend endpoint (if any)

```json
{
  "PAYMENT": {
    "required_fields": ["recipient_name", "bank_name", "account_number", "amount"],
    "optional_fields": ["reference"],
    "confirmation_required": true
  },
  "INQUIRY": {
    "required_fields": ["inquiry_type"],
    "confirmation_required": false
  },
  "DEPOSIT": {
    "required_fields": ["amount", "source_account", "destination_account"],
    "confirmation_required": true
  }
}
```

---

## 5️⃣ Dynamic Task Derivation from API Specification

- The system can **auto-derive** task schemas from backend API specs (OpenAPI / Swagger).  
- It extracts endpoints, methods, and parameter schemas to populate the registry dynamically.

```json
{
  "PAYMENT": {
    "endpoint": "/transfer",
    "method": "POST",
    "required_fields": ["recipient_name", "bank_name", "account_number", "amount"],
    "optional_fields": ["reference"],
    "confirmation_required": true
  }
}
```

- Keeps LLM task logic synchronized with backend changes, reducing manual upkeep.  
- Implemented by parsing `openapi.json` at startup.

---

## 6️⃣ Hybrid Task Definitions: API-Derived + Custom Extensions

- At runtime, merge **auto-derived tasks** with **custom definitions** for capabilities not handled by the backend (e.g., insights, small talk, FAQs).  
- Custom entries include optional `pre_hook` and `post_hook` functions.

```json
{
  "PAYMENT": {
    "endpoint": "/transfer",
    "method": "POST",
    "required_fields": ["recipient_name", "amount"],
    "pre_hook": "check_user_balance",
    "post_hook": "log_audit_trail",
    "confirmation_required": true
  },
  "INSIGHT": {
    "description": "Summarize weekly spending trends",
    "endpoint": null,
    "required_fields": ["time_range"],
    "confirmation_required": false
  },
  "FAQ": {
    "description": "Answer general banking questions",
    "endpoint": null
  }
}
```

Routing rules:
- If `endpoint` exists → call backend API.  
- If not → invoke custom LangGraph node/subgraph.

---

## 7️⃣ Configuration and Environment Variables

All operational and compliance parameters are externalized for safety and portability.

**Directory Layout**
```
config/
  openapi.json
  config.yaml
.env
```

### `.env`
```bash
ENVIRONMENT=production
API_BASE_URL=https://api.bank.com
OPENAPI_SPEC_PATH=./config/openapi.json
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0
SESSION_TIMEOUT_MINUTES=10
ENABLE_CUSTOM_TASKS=true
LOG_LEVEL=INFO
```

### `config.yaml`
```yaml
banking:
  transfer_limit_daily: 10000
  aml_threshold: 250
compliance:
  require_confirmation_above: 250
hooks:
  pre:
    - check_user_balance
  post:
    - log_audit_trail
```

### Usage
- Load `.env` via `dotenv` and `config.yaml` via `yaml.safe_load`.  
- Nodes read values from a shared `APP_CONFIG` dictionary.  
- Sensitive data (keys, DB URIs) stays in `.env` only.  
- Feature flags (`ENABLE_CUSTOM_TASKS`, `ENABLE_API_AUTODERIVE`, etc.) control optional modules.  
- Compliance and AML thresholds adjustable via config for regulator updates.

---

## 8️⃣ RAG Integration for FAQ Agent

- The FAQ Agent uses a **Retrieval-Augmented Generation** pipeline:
  ```
  [RetrieverNode] → [AnswerNode] → [AuditNode]
  ```
- Retrieves top-K FAQ documents from vector store and generates fact-grounded answers.

```json
{
  "answer": "Your daily transfer limit is RM1000.",
  "source_urls": ["https://bank.com/policies/limits"]
}
```

- Configurable RAG parameters:
  - `RAG_TOP_K` (default = 3)
  - `VECTORSTORE_PATH`
  - `FAQ_VECTOR_COLLECTION`

---

## 9️⃣ Node JSON Schemas (Summary)

| Node | Key Output Fields |
|-------|-------------------|
| **Guardrails** | `isSafe`, `guardrailViolation` |
| **Intent Classifier** | `intent`, `clarificationNeeded`, `message` |
| **Payment Agent** | `transaction_fields`, `status`, `transaction_id` |
| **FAQ Agent** | `answer`, `source_urls` |
| **Audit Node** | `timestamp`, `node_path`, `status` |

---

## 🔟 Testing & Validation

- **Unit Tests:** Verify each node updates state as expected.  
- **Integration Tests:** Simulate full flows (Payment, FAQ, mixed-intent).  
- **Safety Tests:** Ensure unsafe inputs are blocked.  
- **RAG Tests:** Confirm retrieved context relevance.  
- **Config Tests:** Swap `.env` / `config.yaml` for environment validation.  

---

## ✅ Summary of Key Design Principles

| Principle | Description |
|------------|--------------|
| **Stateless per session** | Memory flushed after session; only audit metadata retained. |
| **Re-evaluate intent every turn** | Supports mid-conversation topic shifts. |
| **Task schema registry** | Defines or derives operation requirements. |
| **Hybrid extensibility** | Combine backend APIs with LLM-only custom tasks. |
| **Config-driven architecture** | No hard-coded constants; everything adjustable via `.env` / YAML. |
| **Compliance first** | Guardrails, 2FA thresholds, audit logging enforced at all layers. |

---

---

## 🏆 Implementation Summary

This section summarizes how the final implementation of the conversational agent successfully fulfills the key design principles outlined in this document.

| Principle | Implementation Details |
|---|---|
| **Stateless per session** | The final CLI application maintains state in-memory for the duration of a single session. The architecture is designed to easily transition to an external state store (like Redis) for a scalable, stateless API deployment, where each turn would fetch and save the state. |
| **Re-evaluate intent every turn** | This was fully implemented. The LangGraph workflow begins every turn by passing the user's input to the `intent_classifier`, ensuring the agent can gracefully handle interruptions and context switches at any point in the conversation. |
| **Task schema registry** | This was a core focus of the implementation. The `TaskRegistry` (`src/task_registry.py`) was created to act as a central, dynamic source of truth for all agent capabilities, perfectly aligning with this principle. |
| **Hybrid extensibility** | The `TaskRegistry` is fully hybrid. It dynamically loads and merges task definitions from two sources at startup: the backend API specification (`config/openapi.json`) and the custom task configuration (`config/tasks.yaml`), making the system highly extensible. |
| **Config-driven architecture** | The agent's logic is almost entirely driven by external configuration. Hardcoded logic was systematically removed from the agents and replaced with dynamic lookups to the `TaskRegistry`. Even the `intent_classifier`'s prompt is dynamically generated based on the registered tasks, making the entire system highly configurable. |
| **Compliance first** | The foundational `guardrails` node was implemented to check every incoming message for safety. While the current checks are simple, the framework is in place to enforce compliance and safety rules at the entry point of every turn. |

The final architecture is a robust and scalable implementation of the original vision, with a clear separation of concerns between the state, the graph orchestration, the agent logic, and the dynamic configuration.