# Policy Pulse Frontend Documentation

Essential guide for Policy Pulse Streamlit frontend.

---

## 1. Architecture Overview

**Dual Session System**
- ADK Sessions: Actual conversation messages (sessions + events tables)
- Chat Sessions: UI metadata like titles (chat_sessions table)
- Why? Separation of concerns - ADK handles state, we handle UI

**Async/Sync Bridge**: ADK is async, Streamlit is sync. Bridge with asyncio.run() wrapper.

**Multi-Tenancy**: All queries filtered by user_id.

---

## 2. Core Files

### pulse_streamlit_app.py - Main UI

**Key Functions**:
- `init_session_state()` - Initialize ALL session vars upfront. Miss one = KeyError.
- `get_agent_response()` - Bridge to ADK. Must use asyncio.run(). Streams responses.
- `show_document_uploader()` - Handles uploads. Docs >20K chars MUST be summarized.
- `detect_complete_policy_document()` - Regex-based (not LLM). Checks 4 criteria, needs 3/4.
- `check_policy_request()` - Detects policy requests, triggers questionnaire.
- `generate_and_send_template()` - Creates JSON template, sends to ReportWriting agent.

**Gotchas**: Landing page height must be explicit. Questionnaire needs 5 state vars.

### auth.py - Authentication

**Key Functions**:
- `hash_password()` / `verify_password()` - PBKDF2 with 100K iterations, salted.
- `create_user_tables()` - Idempotent table creation.
- `create_user()` - Returns boolean.
- `authenticate_user()` - Returns dict or None. Always check None first.

**Security**: NEVER store plain passwords. users table = credentials, chat_sessions = UI metadata.

### session_utils.py - Session Bridge

**Key Functions**:
- `create_new_session()` - Wraps async ADK call. Session IDs: "session_{16_hex}".
- `get_user_conversations()` - Fetches sidebar list from chat_sessions.
- `get_conversation_messages()` - COMPLEX. Extracts from ADK nested structure. Handles old (string) and new (dict) formats.
- `save_conversation()` - Upsert pattern.
- `delete_conversation()` - Deletes UI metadata only, NOT ADK tables (audit trail).

**ADK Event Structure**: Messages nested as content.parts[].text. Some events empty (tool calls).

---

## 3. Critical Patterns & Gotchas

**Async/Sync Boundary**
- Problem: ADK async, Streamlit sync
- Solution: Always asyncio.run(async_wrapper())

**Session State Management**
- Problem: Streamlit reruns script on every action
- Solution: Store EVERYTHING in st.session_state. Init ALL vars upfront.
- Critical vars: authenticated, user_id, current_session_id, messages, conversations, in_questionnaire, questionnaire_data, uploaded_docs

**Connection Pooling**
- Problem: New connection per query = 10x slower
- Solution: SQLAlchemy pool (pool_size=10, max_overflow=20, pool_pre_ping=True)

**Document Context**
- Problem: Large uploads exceed context
- Solution: Truncate at 20K chars

**Policy Detection**
- Problem: Distinguish complete vs partial
- Solution: Multi-criteria (length + no meta + sections + structure). Need 3/4 pass.

**Questionnaire State**: 5 dedicated vars needed - in_questionnaire, questionnaire_step, questionnaire_data, uploaded_docs, questionnaire_complete

**ADK Event Parsing**: Check if content is dict before accessing .parts. Graceful fallback.

---

## 4. API Integration

**Authentication** (/api/routes/auth.py):
- POST /api/v1/auth/login
- POST /api/v1/auth/signup

**Chat** (/api/routes/chat.py):
- POST /api/v1/chat (requires message, session_id, user_id)

**Sessions** (/api/routes/sessions.py):
- POST /api/v1/sessions/new
- GET /api/v1/sessions
- GET /api/v1/sessions/{session_id}
- PUT /api/v1/sessions/{session_id}
- DELETE /api/v1/sessions/{session_id}

**Main** (/api/main.py):
- All routes prefixed /api/v1
- CORS enabled for port 3000
- Health check at /api/v1/health

**Pattern**: All routes include user_id for multi-tenancy.

---

## 5. Environment Variables

Required: DATABASE_URL, GOOGLE_API_KEY, VOYAGE_API_KEY, ZILLIZ_CLOUD_URI, ZILLIZ_API_KEY
Optional: OPENAI_API_KEY (for summarization)

---

## 6. Quick Deployment

**Local**: cd front_end && streamlit run pulse_streamlit_app.py
**Docker**: Use docker-compose.yml
**Streamlit Cloud**: Connect GitHub, add secrets, deploy

---

## 7. Common Mistakes

1. ❌ Calling async ADK directly → Use asyncio.run()
2. ❌ Accessing session_state without init → Check first
3. ❌ Single-criteria policy detection → Use multiple checks
4. ❌ Assuming ADK content is dict → Check type first
5. ❌ New DB connection per query → Use pooling
6. ❌ Large docs unsummarized → Truncate >20K
7. ❌ Deleting from ADK tables → Only delete UI metadata

---


**Reference docs**: Policy Pulse AI Spec, Policy_Pulse_Database_Schemas.xlsx, System Architecture.mermaid