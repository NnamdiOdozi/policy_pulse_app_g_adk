# Policy Pulse AI-Aware Implementation Functional Specification

## Executive Summary

This document defines a three-tier approach to enhancing the Policy Pulse document management system with AI capabilities. Each tier (Basic, Intermediate, Advanced) incrementally builds on proven patterns from industry leaders (Notion, Linear, Slack) to overcome context limitations. The strategy balances retrieval-augmented generation (RAG) from a knowledge base with dynamic user-specific context. By progressively introducing AI features, we aim to improve policy generation accuracy, user satisfaction, and workflow efficiency while addressing privacy, tenancy (Appendix A), security architecture, and performance considerations (Appendix C).

## Current System Foundation

### Existing Capabilities

**Multi-agent Framework:** Supervisor agent orchestrates specialized agents.

**Retrieval-Augmented Generation (RAG):** zilliz vector database for semantic search.

**Dynamic Template Engine:** Generates policy docs via questionnaire workflow.

**Session Management:** Supabase (PostgreSQL) with Row-Level Security (RLS) [Appendix B].

**User Interface:** Streamlit front-end with doc uploads + AI chat.

### Authentication & Authorization Flow

**Unified Auth & User Data Architecture**

Policy Pulse uses Supabase for both authentication and user data storage. This unified approach provides several key advantages:

- **Seamless Integration**: Auth tokens directly link to user profiles and company data
- **Row Level Security (RLS)**: Automatic enforcement of multi-tenant isolation at the database layer
- **Single Source of Truth**: One connection pool, one backup system, consistent data model
- **Transaction Safety**: Atomic operations across auth and user data

**Authentication Flow**

```
User Login
    ↓
Supabase Auth validates credentials
    ↓
Returns JWT token + user_id
    ↓
API validates JWT on each request
    ↓
Queries user profile to get company_id
    ↓
All subsequent queries filter by company_id
    ↓
Zilliz search includes: filter='company_id == "abc123"'
```

**Separation of Concerns**

The architecture maintains clear boundaries between different types of data:

- **Supabase (Auth + User DB)**: User credentials (hashed passwords), profiles, company metadata, document metadata, audit logs
- **Zilliz (Vector DB)**: Document chunks, embeddings, searchable content, company_id for filtering
- **Redis/Upstash (Optional)**: Session tokens, rate limiting counters, ephemeral cache

**Why This Works**

Using Supabase for both auth and user data is industry standard and provides superior developer experience compared to separating them. The security comes from proper RLS policies and access controls, not from database separation.

**Key Security Principle**: Never store PII (emails, phone numbers, passwords) in the vector database. These belong in Supabase where RLS and encryption at rest protect them appropriately.

### Current Performance

- Processes ~5 document chunks/query
- Questionnaire-driven draft generation
- Session-based conversation history
- Simple citation format (`[DOC X]`)

## Architectural Strategy: RAG vs. Context

### The Distinction

```
User Query → Context Assembly → RAG Search → Response Generation

Immediate Context:
  - Current Page: Dashboard
  - User: David (Manager)
  - Active Doc: Policy #123
  - Recent Edit: Section 1.2

RAG Store:
  - Company Policies
  - UI Workflows
  - Regulatory Guidance
  - Training Content
```

| Component | RAG Store (Knowledge Base) | Message Context (Session State) |
|-----------|---------------------------|--------------------------------|
| **Purpose** | Long-term searchable knowledge | Real-time user-specific state |
| **Persistence** | Permanent | Ephemeral (session) |
| **Size** | Scales with docs | Token-limited |
| **Update Frequency** | On document changes | Every interaction |
| **Access Method** | Semantic search | Direct injection |

### Implications

| Aspect | RAG Store | Message Context |
|--------|-----------|----------------|
| Speed | ~100-500 ms search | 0 ms (direct injection) |
| Accuracy | Semantic relevance | Exact user state |
| Privacy | Company-shared (isolated by tenant - Appendix A) | User-specific |
| Scalability | Thousands of docs | 4-8 context items |

### Multi-collection Knowledge Organization

```
policy_pulse_knowledge
├── company_policies
├── ui_workflows
├── regulatory_guidance
└── training_content
```

- **collections for corpora/domains** (Appendix A clarifies "tenant vs. domain" use of zilliz)
- **Tenant isolation**: Each company gets its own collection family

## AI Chat Integration & Document Workflow

### Single Chat Interface

One unified AI chat window is accessible across all pages:
- **Dashboard context**: summary, navigation help
- **Policy Editor context**: compliance suggestions, editing
- **Training context**: progress-based guidance

**Why single chat?**
- Consistent user experience
- Maintains context across navigation
- Simpler implementation and ops

### Document Generation Workflow

1. **User request via chat** (e.g., "Create maternity leave policy")
2. **AI questionnaire** gathers requirements
3. **Draft generation**:
   - Inserted into DB (policies table, with `company_id` for RLS - Appendix B)
   - File saved to Supabase storage
   - Upserted into zilliz tenant collection (Appendix A)
   - UI updates triggered
4. **Cross-page sync**: Dashboard stats increment, My Policies list updates, Chat shows confirmation

### Document Lifecycle Integration

**States**: Draft → In Review → Approved → Published → Archived

**AI role**: Suggest edits, summarize, ensure compliance, insert regulatory requirements (from `regulatory_guidance`)

Lifecycle state transitions are tracked in DB; RAG updated on publish. See Appendix B for RBAC and access-control handling across states.

## Multi-Tenancy Architecture Strategy

### Isolation Mechanisms

**Database Layer**
- PostgreSQL RLS (Row Level Security) with `company_id`
- Automatic filtering via Supabase policies
- No manual WHERE clauses needed in application code

**Zilliz Multi-Tenancy Options:**

1. **Single Collection with company_id Filtering (Recommended for most)**
   - All tenants share one collection
   - Every query includes: filter='company_id == "abc123"'
   - Simplest to manage, most cost-effective
   - What we currently use

2. **Collection-per-Tenant (Enterprise)**
   - Dedicated collection for each company
   - Strongest isolation at vector DB layer
   - Higher operational overhead
   - Used for very large customers or specific compliance needs

**Storage Layer**
- Company-specific buckets or folder prefixes
- Supabase Storage RLS policies

**Prompt Layer**
- System context always includes company metadata
- Prevents cross-tenant information leakage

### Data Isolation Patterns

**Three-Layer Defense**

1. **Database Layer (Supabase RLS)**
```sql
-- Automatic policy enforcement
CREATE POLICY "Users see own company documents"
ON documents FOR SELECT
USING (
  company_id IN (
    SELECT company_id FROM profiles WHERE user_id = auth.uid()
  )
);
```

2. **Vector Layer (Zilliz/zilliz)**
```python
# Every search query includes company filter
results = zilliz_client.search(
    query=user_query,
    filter=f'company_id == "{user_company_id}"'
)
```

3. **Application Layer**
```python
# JWT validation before every request
@app.post("/api/search")
async def search(query: str, user: User = Depends(get_current_user)):
    company_id = get_user_company(user.id)  # From Supabase
    return search_documents(query, company_id)  # Filtered search
```

**Why company_id and user_id Don't Need Encryption**

These are non-sensitive identifiers used for filtering and relationships:
- `company_id`: "company_abc123" - meaningless without context
- `user_id`: "user_xyz789" - just a foreign key
- They're not PII - they don't reveal personal information
- Encrypting them would break filtering and queries

**Common Anti-Pattern to Avoid**

❌ **Wrong**: Storing user emails in vector DB metadata "for convenience"
```python
# DON'T DO THIS
chunk = {
    "text": "policy content...",
    "uploaded_by_email": "john@company.com",  # PII in vector DB!
    "contact": "+44-7700-900123"  # Phone number exposed!
}
```

✅ **Correct**: Store only non-sensitive identifiers
```python
# DO THIS
chunk = {
    "text": "policy content...",
    "uploaded_by": "user_xyz789",  # Just an ID
    "company_id": "company_abc123"  # Just an ID
}

# Look up email separately in Supabase when needed
user_email = supabase.table('profiles').select('email').eq('user_id', 'user_xyz789')
```

**Audit Trail Requirements**

What to log:
- ✅ `user_id`, `company_id`, `action`, `timestamp`, `ip_address`
- ✅ Query type (search, upload, delete) and result counts
- ✅ Document IDs accessed

What NOT to log:
- ❌ Passwords or password hashes
- ❌ Full query text (may contain PII)
- ❌ Complete document content
- ❌ Session tokens or API keys

### Migration Strategy

**Pooled → Silo Runbook**: See Appendix A

**Data Residency & KMS**: Per-tenant encryption keys supported (Appendix B)

**Observability**: Per-tenant dashboards, noisy-neighbor guardrails (Appendix C)

## Data Security & Encryption Architecture

### Encryption at Rest: What It Really Means

**Common Misconception**

Many customers ask: "Is our data encrypted?" and expect that encryption means "no one can read it." This is a misunderstanding of how encryption at rest works.

**The Reality**

"Encrypted at rest" refers to encryption at the storage layer (physical disks, backup files). It protects against:
- ✅ Physical hard drive theft
- ✅ Leaked database backups
- ✅ Misconfigured cloud storage buckets
- ✅ Unauthorized direct disk access

It does NOT protect against:
- ❌ Authorized users reading data through the console/API
- ❌ Anyone with valid API keys accessing data
- ❌ Platform administrators with proper access credentials

**How It Works**

```
User logs into Zilliz Console
    ↓
API call authenticated with valid credentials
    ↓
Zilliz Application Layer decrypts data for authorized user
    ↓
Data displayed in plaintext in console
    ↓
(But on disk, data is encrypted with AES-256)
```

**Banking Analogy**

Your bank encrypts data at rest, but:
- You can log in and see your balance (plaintext)
- Bank employees with proper access can see your data
- If someone steals your login credentials, they can access your account

The encryption protects against someone stealing backup tapes or decommissioned hard drives - not against authorized access.

### PII Handling & Data Classification

**Data Classification Matrix**

| Data Type | Storage Location | Encryption Method | Accessible Via |
|-----------|-----------------|-------------------|----------------|
| **Passwords** | Supabase Auth | Bcrypt hash + salt | Never retrievable |
| **Email addresses** | Supabase profiles table | AES-256 at rest | Admin API only |
| **Phone numbers** | Supabase profiles table | AES-256 at rest | Admin API only |
| **User names** | Supabase profiles table | AES-256 at rest | User profile API |
| **Document content** | Zilliz vector DB | AES-256 at rest | Search API |
| **company_id** | Both Supabase & Zilliz | AES-256 at rest | Filtering/queries |
| **user_id** | Both Supabase & Zilliz | AES-256 at rest | Audit logs |
| **API keys** | Environment variables | Never stored in DB | Server runtime only |
| **Session tokens** | Redis/memory | Ephemeral (expire quickly) | Not persisted |

**Critical Rule: What NEVER Goes in Vector Database**

❌ **Never store in Zilliz/zilliz:**
- Passwords (even hashed)
- Email addresses
- Phone numbers
- Physical addresses
- Social Security Numbers / National Insurance Numbers
- Credit card numbers
- Medical records
- Passport numbers
- Any field marked as PII in GDPR/CCPA

✅ **Safe to store in Zilliz:**
- Document text content (policies, guidelines, procedures)
- Document metadata (filename, file_type, indexed_at)
- Non-sensitive identifiers (company_id, user_id, document_id)
- Semantic embeddings (vectors)
- Search metadata (chunk_summary, keywords)

### Storage Decision Framework

**Decision Tree: Where Should This Data Live?**

```
Is it authentication data (password, email)?
├─ YES → Supabase Auth table (hashed, RLS protected)
└─ NO → Continue

Is it PII (phone, address, SSN)?
├─ YES → Supabase user table (encrypted at rest, RLS)
└─ NO → Continue

Is it document content meant to be searchable?
├─ YES → Vector DB (Zilliz/zilliz)
└─ NO → Continue

Is it metadata about documents?
├─ YES → Supabase metadata table + Vector DB
└─ NO → Continue

Is it temporary state (session, cache)?
├─ YES → Redis/memory (ephemeral)
└─ Store in appropriate table with RLS
```

### Trade-offs of Additional Encryption

**When Standard Encryption is Sufficient**

For 99% of B2B SaaS applications (including Policy Pulse):
- Zilliz/zilliz provide AES-256 encryption at rest (industry standard)
- Supabase provides bcrypt password hashing and AES-256 at rest
- TLS 1.3 encrypts data in transit
- **This is what OpenAI, zilliz, Notion, and Linear all use**

**When to Consider Application-Layer Encryption**

Only if customer contracts explicitly require:
- **HIPAA compliance** (healthcare data)
- **PCI-DSS Level 1** (handling credit card data directly)
- **Customer-managed keys (BYOK)** - Enterprise feature where customer controls encryption keys
- **Zero-knowledge architecture** - Customer requires that even the platform provider cannot read data

**Trade-offs of App-Layer Encryption**

| Approach | Security Level | Search Functionality | Complexity | Customer Perception |
|----------|---------------|---------------------|------------|-------------------|
| Standard (Zilliz AES-256) | ⭐⭐⭐⭐ High | ⭐⭐⭐⭐⭐ Full | ⭐⭐⭐⭐⭐ None | ⭐⭐⭐⭐⭐ Expected |
| + Encrypt text chunks | ⭐⭐⭐⭐⭐ Very High | ⭐⭐ Limited | ⭐⭐ Moderate | ⭐⭐⭐ Overkill |
| + Encrypt metadata | ⭐⭐⭐⭐⭐ Very High | ⭐⭐⭐ Good | ⭐⭐ Moderate | ⭐⭐⭐⭐ Strong |
| Self-host + own keys | ⭐⭐⭐⭐⭐ Maximum | ⭐⭐⭐⭐⭐ Full | ⭐ High effort | ⭐⭐⭐ Enterprise only |

**Example: Application-Layer Encryption**

If required for compliance:
```python
from cryptography.fernet import Fernet

# Encryption key stored in environment variable
cipher = Fernet(os.getenv("ENCRYPTION_KEY"))

def store_chunk(text, metadata):
    # Encrypt text before storing in Zilliz
    encrypted_text = cipher.encrypt(text.encode()).decode()
    
    # Generate embedding from ORIGINAL text (not encrypted)
    embedding = voyage_client.embed([text])
    
    # Store encrypted text with unencrypted vector
    chunk = {
        "text": encrypted_text,  # Unreadable in Zilliz console
        "vector": embedding,      # Searchable
        "company_id": metadata["company_id"]
    }
    
    zilliz_client.insert(chunk)

def retrieve_chunk(chunk_id):
    chunk = zilliz_client.get(chunk_id)
    # Decrypt on retrieval
    decrypted_text = cipher.decrypt(chunk["text"].encode()).decode()
    return decrypted_text
```

**Cost of This Approach:**
- ❌ Cannot use TEXT_MATCH or keyword search on encrypted text
- ❌ Must decrypt every result client-side (adds latency)
- ❌ If encryption key is lost, all data is permanently unrecoverable
- ❌ Additional infrastructure for key management
- ✅ Text truly unreadable even to Zilliz/platform administrators

### Customer Compliance Messaging

**Script for "Is our data encrypted?" Questions**

Standard response for most customers:
> "Yes, all data is encrypted at rest using AES-256 encryption through our infrastructure providers (Zilliz Cloud and Supabase), both of which are SOC 2 Type II certified. Data in transit uses TLS 1.3 encryption. We implement strict access controls via Row Level Security and API key management. Our architecture follows industry best practices used by companies like Notion, Linear, and Slack."

If customer pushes for "customer-managed keys":
> "For enterprise customers with specific compliance requirements, we can provide customer-managed encryption keys (BYOK) or explore application-layer encryption options. However, this may impact search functionality and requires additional key management infrastructure. Can you share your specific compliance requirements so we can recommend the appropriate approach?"

**Common Customer Questions & Answers**

| Question | Answer |
|----------|--------|
| "Can your employees read our data?" | "Our infrastructure providers (Zilliz, Supabase) have strict access controls. Our team does not access customer data except for debugging with explicit customer permission and audit logging." |
| "What happens if Zilliz is breached?" | "Data is encrypted at rest with keys managed separately from data storage. Additionally, all data is filtered by company_id, so tenant isolation prevents cross-customer access." |
| "Is this GDPR compliant?" | "Yes. Both Zilliz and Supabase are GDPR compliant. We support data subject access requests (DSAR) and right to erasure workflows. See Appendix B for our data retention policies." |
| "Do you store passwords?" | "No. We use Supabase Auth which implements bcrypt hashing with per-user salts. Passwords are never stored in plaintext or reversible format." |
| "What about PCI compliance?" | "We don't store credit card data. Payment processing is handled by Stripe, which is PCI DSS Level 1 certified." |

### Key Management Best Practices

**API Key Rotation Policy**
- Production API keys rotated every 90 days
- Development/staging keys rotated every 180 days
- Immediate rotation on any suspected compromise
- Old keys deprecated with 30-day grace period

**Environment Variable Security**
- Never commit API keys to git repositories
- Use secret management services (AWS Secrets Manager, HashiCorp Vault)
- Different keys per environment (dev, staging, production)
- Audit logs for all secret access

**Real Security Priorities (Ranked by Impact)**

1. **Access Controls & API Key Management** (🔥 Highest Impact)
   - Proper authentication on all endpoints
   - API key rotation and secure storage
   - Principle of least privilege

2. **Multi-Tenant Isolation** (🔥 High Impact)
   - RLS policies enforced at database layer
   - company_id filtering in all vector searches
   - Prevent cross-tenant data leakage

3. **Network Security & Rate Limiting** (🔥 High Impact)
   - IP whitelisting for admin endpoints
   - Rate limiting to prevent abuse
   - DDoS protection

4. **Infrastructure Encryption at Rest** (✅ Provided by Zilliz/Supabase)
   - AES-256 for storage layer
   - Handled automatically by platform

5. **Application-Layer Encryption** (💡 Nice to Have)
   - Only if required by specific compliance
   - Adds complexity, reduces functionality
   - Use sparingly for truly sensitive data

## BASIC Implementation (Months 1-2)

**Enhancements:**
- Context assembly (inject page-specific state)
- RAG upgrades: 8-10 chunks (vs. 5), collection-targeted, context-enriched queries
- Accuracy target: ~30% (vs. 15% baseline)

See Appendix D for evaluation harness (precision@k, groundedness).

## INTERMEDIATE Implementation (Months 3-6)

**New capabilities:**
- **Memory-enhanced AI**: Learns writing style, workflows, org facts (Appendix D covers memory governance)
- **Training integration**: AI adapts responses based on LMS data (Appendix F covers integration contracts)
- **User personalization**: Stored in `user_memory` table with RLS (Appendix B)

Goal: Contextual, adaptive assistance while respecting tenancy and privacy.

## ADVANCED Implementation (Months 7-12)

**Capabilities:**
- **Multi-modal ingestion**: OCR (scanned PDFs), speech-to-text (recordings), structured HR data
- **Enterprise features**: Real-time regulatory monitoring, cross-doc consistency analysis, organizational intelligence dashboards

Requires separate multi-modal services integrated with main pipeline (Appendix C, RTO/RPO considerations for new services).

## Implementation Considerations

**Infra per tier (see Appendix C for SLOs & DR):**
- Basic: <500 ms target, simple schema extensions
- Intermediate: <1s responses, memory tables, nightly jobs
- Advanced: <2s responses, async OCR/STT queues, external API hooks

**Integration Strategy Matrix**: covers Thinkific (LMS), Supabase Storage, approval workflows, and external APIs (Appendix F outlines contracts).

## Success Measurement Framework

**KPIs:**
- Policy generation accuracy
- User satisfaction
- Time-to-completion
- First-draft acceptance

**Expected Performance Improvements by Tier:**

| Metric | Basic | Intermediate | Advanced |
|--------|-------|--------------|----------|
| Policy Generation Accuracy | 15% → 35% | 35% → 60% | 60% → 85% |
| User Satisfaction | +20% | +45% | +90% |
| Time to Completion | -20% | -40% | -60% |
| First-Draft Acceptance | +25% | +50% | +75% |

**ROI metrics:**
- Time per policy: 8h → 6.5h (Basic) → 5h (Intermediate) → 3h (Advanced)
- Compliance score: 65% → 75% → 85% → 95%

**Risk mitigation**: Prompt injection, RAG poisoning, cross-tenant leakage (see Appendix B for threat model & controls).

## Common Challenges

- **Context length management**: Summarization, relevance ranking
- **Memory quality vs. quantity**: Prune low-signal memories (Appendix D)
- **Consistency across sessions**: Versioned prompts/memory resets

## Success Factors

- **Adoption**: Trust via citations; transparent memory; low learning curve
- **Technical**: Error handling, graceful degradation (Appendix C)
- **Change management**: Clear comms; feedback loops; compliance/legal oversight

---

# Appendices

## Appendix A. Tenancy Patterns & Migration

### Tenancy Models Supported

**Pooled Multi-Tenant (Default)**
- Shared database with Row Level Security (RLS)
- Shared Supabase instance with company_id filtering
- zilliz collection-per-tenant or metadata filtering
- Cost-effective for majority of customers

**Silo / Single-Tenant (Enterprise Tier)**
- Dedicated database instance per customer
- Optional dedicated zilliz project
- Optional dedicated storage bucket
- Strongest isolation, higher operational cost

**Hybrid Approach**
- Shared application layer and storage
- Dedicated database and/or vector store for high-security tenants
- Flexible for mixed customer base

### Authentication Architecture by Tenant Type

**Pooled Tenants**
- Single Supabase Auth instance
- RLS policies automatically enforce company_id separation
- Users from different companies share same auth infrastructure
- Completely isolated at data layer via RLS

**Silo Tenants**
- Can provision dedicated Supabase project if required
- Separate auth database per customer
- Used for customers with strict data residency requirements
- Higher cost, higher isolation

**SSO Integration**
- Enterprise customers can use Okta, Azure AD, Google Workspace
- Supabase supports SAML 2.0 and OAuth 2.0
- SSO users still stored in Supabase with external_id mapping
- RLS policies work identically for SSO and native users

**Migration Impact on Auth**

When moving tenant from pooled → silo:
1. Export user records from shared Supabase
2. Provision new dedicated Supabase project
3. Import users with password hashes preserved
4. Update application config to point to new instance
5. Rotate API keys and update secrets
6. Short downtime window (typically <15 minutes)

### Migration Path (Pooled → Silo)

1. **Export tenant data**: DB dump, storage files, vector data
2. **Provision infrastructure**: New DB instance, dedicated zilliz index, storage bucket
3. **Import and rebuild**: Load data, rebuild vector index
4. **Rotate secrets**: New API keys, update application config
5. **Cutover**: DNS/routing update with short downtime

**Downtime**: Typically 15-30 minutes

### When to Recommend Silo

- Regulatory requirement (HIPAA, specific data residency laws)
- Very high scale (>10M documents or >1000 QPS)
- Customer-managed encryption keys required
- Network isolation requirements (VPC peering, private endpoints)

## Appendix B. Security & Compliance

### Threat Model

**Primary Threats:**
- Cross-tenant data leakage
- Prompt injection attacks
- RAG poisoning (malicious documents in knowledge base)
- Data exfiltration via LLM responses
- Stolen API keys / credential compromise

### Data Classification & Storage Policies

**Critical Data (Maximum Protection)**
- **What**: Passwords, API keys, payment tokens
- **Storage**: Hashed/encrypted, never logged
- **Access**: Extremely restricted, audit logged
- **Retention**: Passwords never stored reversibly; API keys rotated regularly

**Sensitive Data (High Protection)**
- **What**: Email addresses, phone numbers, user profiles, company information
- **Storage**: Supabase with RLS, AES-256 at rest
- **Access**: User can access own data via RLS; admin access logged
- **Retention**: Until account deletion; GDPR right to erasure supported

**Internal Data (Standard Protection)**
- **What**: Document content, company policies, generated summaries
- **Storage**: Vector DB with tenant isolation (company_id filtering)
- **Access**: Filtered by company_id; users can only access own company's data
- **Retention**: Until document deletion; soft-deletes for 30 days

**Public Data (Minimal Protection)**
- **What**: Regulatory guidance, public policy templates
- **Storage**: Can be cached, CDN, shared collections
- **Access**: Available to all authenticated users
- **Retention**: Indefinite

**Storage Decision Examples**

| Data Element | Classification | Store In | Why |
|--------------|---------------|----------|-----|
| User password | Critical | Supabase Auth (bcrypt) | Must be hashed, never retrievable |
| User email | Sensitive | Supabase profiles table | PII, needed for communication |
| user_id | Non-sensitive identifier | Both Supabase & Zilliz | Just a foreign key for filtering |
| company_id | Non-sensitive identifier | Both Supabase & Zilliz | Used for tenant isolation filtering |
| Document text | Internal | Zilliz (searchable) | Business content, needs semantic search |
| Policy filename | Internal | Both Supabase & Zilliz | Metadata for display and filtering |
| Session token | Critical | Redis/memory (ephemeral) | Short-lived, never persisted to disk |

### Controls

**Database Layer**
- Row Level Security (RLS) enforced on all tables
- Role-based access control (RBAC) for admin operations
- Prepared statements to prevent SQL injection

**Vector Database Layer**
- collection-per-tenant in zilliz
- OR company_id filtering in all queries
- API keys scoped to specific collections

**Prompt Engineering**
- Company_id injected into every system prompt
- Validation of user inputs to prevent prompt injection
- Output filtering to prevent data leakage

**Encryption**
- AES-256 at rest (Zilliz, Supabase)
- TLS 1.3 in transit
- Per-tenant KMS keys available for Enterprise tier

**Audit Logging**
- All data access logged with user_id, company_id, timestamp
- Tenant-scoped log access via dashboard
- Immutable logs for compliance

### Privacy Compliance

**GDPR Compliance**
- Right to access: Users can export their data
- Right to erasure: Account deletion removes all associated data
- Right to rectification: Users can update their profile information
- Data portability: Export in machine-readable format (JSON)

**DSAR (Data Subject Access Request) Workflow**
1. User submits request via UI or support
2. System generates report of all data associated with user_id
3. Report includes: profile data, documents uploaded, search history
4. Report excludes: passwords, other users' data
5. Delivered securely within 30 days

**Data Retention Policies**
- Active user data: Retained while account is active
- Deleted user data: Soft-deleted for 30 days, then hard-deleted
- Audit logs: Retained for 7 years for compliance
- Backup data: Encrypted backups retained for 90 days

### Real Security Priorities

**Ranked by Impact on Customer Data Protection:**

1. **API Key Management & Access Controls** (🔥🔥🔥 Critical)
   - Immediate impact: Compromised keys = full data breach
   - Actions: 90-day rotation, secure storage, principle of least privilege
   - Monitoring: Alert on unusual API key usage patterns

2. **Multi-Tenant Isolation via RLS** (🔥🔥🔥 Critical)
   - Immediate impact: Broken RLS = cross-tenant data leakage
   - Actions: Comprehensive RLS policies, automated testing
   - Monitoring: Query patterns to detect missing filters

3. **Network Security & Rate Limiting** (🔥🔥 High)
   - Impact: Prevents brute force, DDoS, credential stuffing
   - Actions: IP whitelisting, rate limits, WAF
   - Monitoring: Traffic anomalies, failed auth attempts

4. **Infrastructure Encryption** (🔥 Medium - Handled by Platform)
   - Impact: Protects against storage breaches
   - Actions: Verify Zilliz/Supabase compliance certifications
   - Monitoring: Compliance audit reports

5. **Application-Layer Encryption** (💡 Low Priority - Only if Required)
   - Impact: Adds complexity, reduces functionality
   - When needed: Healthcare, finance, specific compliance mandates
   - Trade-off: Security gain vs. search functionality loss

## Appendix C. SLOs, Disaster Recovery & Observability

**Service Level Objectives (SLOs):**
- **Latency**: Basic <500 ms; Intermediate <1s; Advanced <2s
- **Availability**: 99.9% uptime
- **Error budget**: ≤0.1% failed requests per month

**Disaster Recovery:**
- **RTO (Recovery Time Objective)**: <2 hours
- **RPO (Recovery Point Objective)**: <15 minutes
- Database: WAL (Write-Ahead Logging) + nightly snapshots
- Storage: Cross-region snapshots every 6 hours
- Vector index: Rebuild capability from source documents + logs

**Observability:**
- **Metrics**: Latency per stage (RAG search, LLM generation), per-tenant QPS
- **Tracing**: Request-level distributed tracing with OpenTelemetry
- **Dashboards**: Tenant-specific performance views
- **Noisy neighbor protection**: Per-tenant quotas and rate limits

**Resource Requirements Timeline:**

```
Basic Tier (Months 1-2):
├─ Context Enhancement (Jan 1 - Feb 15)
├─ RAG Optimization (Jan 15 - Feb 28)
└─ Testing & Refinement (Feb 15 - Mar 1)

Intermediate Tier (Months 3-6):
├─ Memory System (Mar 1 - Apr 15)
├─ Learning Integration (Apr 1 - May 15)
└─ Training Portal Sync (May 1 - Jun 1)

Advanced Tier (Months 7-12):
├─ Multi-Modal Processing (Jul 1 - Sep 1)
├─ Enterprise Features (Sep 1 - Nov 1)
└─ Organizational Intelligence (Oct 1 - Dec 1)
```

## Appendix D. RAG Evaluation & Model Governance

**Data Lifecycle Management:**
- Chunking strategy: ~500 tokens per chunk with 50-token overlap
- Embedding version tags to track model changes
- Re-embedding schedule: Every 6-12 months or on major model updates
- Deduplication at ingestion to prevent redundant storage

**Evaluation Framework:**
- Offline test sets with known query-answer pairs
- Metrics tracked:
  - Precision@k: Percentage of top-k results that are relevant
  - Groundedness: Percentage of LLM responses supported by retrieved chunks
  - Edit distance: Similarity between generated policy and approved template
- Regression testing: All tests must pass before deployment

**Model Governance:**
- Model registry with versioning and rollback capability
- Canary deployments (5% traffic, monitor for 24 hours)
- Human-in-the-loop review for compliance-critical changes
- Feedback integration: User corrections feed back into evaluation sets

**Citation Policy:**
- Every compliance-related answer must cite source documents
- Citation format includes document name and chunk identifier
- Clickable citations link back to source document location

**Memory Governance:**
- User memories stored with timestamp and confidence score
- Low-confidence memories pruned after 90 days
- Users can view and delete their stored memories
- Memory storage capped at 1000 items per user

## Appendix E. Database Schema

**Core Tables:**

```sql
-- Users and authentication (managed by Supabase Auth)
auth.users (
  id uuid PRIMARY KEY,
  email varchar UNIQUE,
  encrypted_password varchar,
  created_at timestamptz
)

-- Extended user profiles
profiles (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id),
  full_name varchar,
  company_id uuid REFERENCES companies(id),
  role varchar CHECK (role IN ('admin', 'manager', 'employee')),
  created_at timestamptz
)

-- RLS Policy Example
CREATE POLICY "Users can view own profile"
ON profiles FOR SELECT
USING (auth.uid() = user_id);

-- Companies
companies (
  id uuid PRIMARY KEY,
  company_name varchar NOT NULL,
  subscription_tier varchar DEFAULT 'free',
  settings jsonb,
  created_at timestamptz
)

-- Document metadata (NOT the chunks - those are in Zilliz)
documents (
  id uuid PRIMARY KEY,
  company_id uuid REFERENCES companies(id),
  filename varchar NOT NULL,
  file_path varchar,
  file_hash varchar(64),  -- SHA-256 for change detection
  file_size bigint,
  status varchar CHECK (status IN ('draft', 'in_review', 'approved', 'published', 'archived')),
  uploaded_by uuid REFERENCES auth.users(id),
  zilliz_chunk_count int,
  created_at timestamptz,
  updated_at timestamptz
)

-- RLS Policy for documents
CREATE POLICY "Users see own company documents"
ON documents FOR SELECT
USING (
  company_id IN (
    SELECT company_id FROM profiles WHERE user_id = auth.uid()
  )
);

-- Audit logs
audit_logs (
  id uuid PRIMARY KEY,
  user_id uuid REFERENCES auth.users(id),
  company_id uuid REFERENCES companies(id),
  action varchar,  -- 'search', 'upload', 'delete', 'edit'
  resource_type varchar,  -- 'document', 'policy', 'user'
  resource_id uuid,
  details jsonb,
  ip_address inet,
  created_at timestamptz
)

-- User memories (Intermediate tier)
user_memories (
  id uuid PRIMARY KEY,
  user_id uuid REFERENCES auth.users(id),
  company_id uuid REFERENCES companies(id),
  memory_type varchar,  -- 'preference', 'workflow', 'fact'
  content text,
  confidence_score float,
  created_at timestamptz,
  last_accessed timestamptz
)

-- RLS for memories
CREATE POLICY "Users can only access own memories"
ON user_memories FOR ALL
USING (auth.uid() = user_id);
```

**Zilliz Collection Schema:**

```python
# Document chunks collection
{
  "id": "VARCHAR(200)",  # Primary key: "filename_chunk_0"
  "text": "VARCHAR(65535)",  # Main chunk content
  "vector": "FLOAT_VECTOR[1024]",  # Voyage AI embedding
  
  # Metadata for filtering and display
  "filename": "VARCHAR(256)",
  "file_type": "VARCHAR(20)",
  "file_path": "VARCHAR(512)",
  "file_hash": "VARCHAR(64)",  # SHA-256 for change detection
  "file_size": "INT64",
  "company_id": "VARCHAR(100)",  # For tenant isolation
  "indexed_at": "VARCHAR(30)",
  
  # Enrichment metadata
  "chunk_id": "VARCHAR(200)",
  "section_title": "VARCHAR(256)",
  "chunk_summary": "VARCHAR(512)",
  "document_summary": "VARCHAR(256)",
  "semantic_keywords": "JSON",  # Array of strings
  "keywords_text": "VARCHAR(1000)"  # Flattened for TEXT_MATCH
}
```

## Appendix F. Integration Contracts

**Thinkific LMS Integration:**
- **Endpoint**: `/api/v1/training/progress`
- **Authentication**: Bearer token
- **Data Retrieved**: 
  - User completion status per course
  - Assessment scores
  - Time spent on modules
- **Sync Frequency**: Real-time webhook + nightly batch
- **Use Case**: AI adapts guidance based on training completion

**Supabase Storage Integration:**
- **Bucket Structure**: `company_{id}/documents/{year}/{month}/`
- **Access Control**: RLS policies on storage buckets
- **File Processing**: 
  1. Upload triggers webhook
  2. File watcher detects change
  3. Document processor extracts text
  4. Chunks indexed to Zilliz
  5. Metadata updated in Supabase

**Document Approval Workflow:**
- **States**: draft → in_review → approved → published
- **State Transitions**: Tracked in `documents.status`
- **Triggers**: 
  - Email notifications on state change
  - RAG index updated only on 'published' state
  - Version control for edits during review

**External API Integrations (Advanced Tier):**
- **Regulatory Monitoring**: 
  - Gov.uk API for UK policy updates
  - EU legislation database
  - Webhook-based change notifications
- **HR System Integration**:
  - Employee data sync (roles, departments)
  - Used for policy personalization
  - Never stored in vector DB (stays in Supabase)

**Integration Security:**
- All external API calls use OAuth 2.0 or API keys
- API keys stored in environment variables, never in code
- Rate limiting on all outbound calls
- Circuit breaker pattern for failing APIs
- Timeout limits: 30 seconds maximum

## Appendix G. Change Detection & File Watching

**File Watching Strategy:**

Policy Pulse implements intelligent file watching to automatically detect and process document changes without unnecessary reprocessing.

**Hash-Based Change Detection:**

Every file is tracked with a SHA-256 hash stored in both:
1. Supabase `documents` table (`file_hash` field)
2. Zilliz chunks (duplicated across all chunks from same file)

**Event Handling:**

```python
# File created or modified
if file_event == 'created' or file_event == 'modified':
    current_hash = calculate_sha256(file)
    stored_hash = get_hash_from_zilliz(file_path)
    
    if current_hash == stored_hash:
        # Content unchanged - skip processing
        log("No changes detected, skipping")
    else:
        # Content changed - full reprocess
        process_file_and_index(file)

# File renamed (content unchanged)
if file_event == 'renamed':
    current_hash = calculate_sha256(new_file)
    stored_hash = get_hash_from_zilliz(old_file_path)
    
    if current_hash == stored_hash:
        # Just update metadata (filename, file_path)
        update_chunk_metadata_only(old_path, new_path)
    else:
        # Content also changed - full reprocess
        delete_old_chunks(old_path)
        process_file_and_index(new_path)

# File deleted
if file_event == 'deleted':
    delete_all_chunks(file_path)
    delete_metadata_from_supabase(file_path)
```

**Cost Savings:**

- Metadata-only change (e.g., file properties): 0 API calls
- Rename without content change: ~10ms metadata update vs. ~30s full reprocess
- Actual content change: Full reprocessing as needed

**Implementation Details:**

- Watchdog library monitors filesystem events
- 2-second debounce period to avoid processing multiple rapid events
- Windows compatibility: Handles spurious modify events after renames
- Idempotent: Upsert operations prevent duplicates

**Benefits:**

- Reduces unnecessary API costs (OpenAI, Voyage AI)
- Faster response times for metadata-only changes
- Prevents vector DB bloat from duplicate chunks
- User sees immediate updates for actual changes

## Conclusion

This specification provides a comprehensive roadmap for implementing AI-aware capabilities in Policy Pulse across three progressive tiers. The architecture prioritizes:

1. **Security First**: Clear separation between PII (Supabase) and searchable content (Zilliz), with proper encryption and access controls at each layer
2. **Multi-Tenancy**: RLS-based isolation in database, company_id filtering in vector searches, with clear migration paths for enterprise customers
3. **Practical Encryption**: Industry-standard encryption at rest without over-engineering, with clear guidance on when additional encryption is needed
4. **Incremental Value**: Each tier delivers measurable improvements while building foundation for next tier
5. **Compliance Ready**: GDPR support, audit logging, and data retention policies built in from the start

**Key Architectural Decisions:**

- Unified Supabase for auth and user data (simpler, more secure via RLS)
- Hash-based change detection to minimize unnecessary reprocessing
- company_id as non-sensitive identifier used consistently for filtering
- Clear boundaries: Authentication (Supabase) vs. Search (Zilliz) vs. Cache (Redis)

**Success Metrics:**

By Advanced tier completion, expect:
- 85% policy generation accuracy (vs. 15% baseline)
- 60% reduction in time-to-completion
- 90% user satisfaction improvement
- 95% compliance score
- Zero cross-tenant data leakage incidents

**Next Steps:**

1. Review and approve specification with stakeholders
2. Set up development environment with proper secrets management
3. Implement Basic tier (Months 1-2) with focus on RLS policies and hash-based file watching
4. Establish evaluation framework before moving to Intermediate tier
5. Gather user feedback continuously to inform Advanced tier priorities

---

**Document Version**: 2.0 (Enhanced with Security Architecture)  
**Last Updated**: 5 October 2025  
**Authors**: Policy Pulse Engineering Team  
**Review Cycle**: Quarterly or on major architectural changes


