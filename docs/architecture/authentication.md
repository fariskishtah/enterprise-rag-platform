# Authentication & Authorization Architecture

EnterpriseRAG implements secure local JWT authentication with user-scoped resource ownership and role-based access control.

---

## Auth & Resource Ownership Flow

```mermaid
sequenceDiagram
    autonumber
    actor Client as React Client
    participant AuthAPI as Auth Routes (/api/v1/auth)
    participant JWT as JWT Security Core
    participant DB as SQLite DB
    participant Resource as KB / Document Services

    Client->>AuthAPI: POST /login (email, password)
    AuthAPI->>DB: Fetch User & Check bcrypt Password Hash
    DB-->>AuthAPI: User Validated
    AuthAPI->>JWT: Generate JWT Access Token (user_id, role)
    JWT-->>Client: Return Bearer Token

    Client->>Resource: GET /knowledge-bases (Authorization: Bearer <token>)
    Resource->>JWT: Verify Token Signature & Expiration
    JWT-->>Resource: Validated (user_id=123, role=user)
    Resource->>DB: Query KnowledgeBases WHERE user_id = 123
    DB-->>Client: User-Scoped Knowledge Bases
```

---

## Security Features
- **Password Hashing**: `passlib` with `bcrypt`.
- **Stateless Tokens**: HS256 JWT tokens with configurable expiration (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **IDOR Protection**: Access verification on every resource endpoint (Knowledge Base, Document, Chat Session, Report, Feedback).
- **Admin Role**: System health, queue monitoring, and aggregate metrics endpoint access.
