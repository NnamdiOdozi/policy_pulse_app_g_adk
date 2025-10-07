# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import sys
import subprocess
import time




# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import logging
# Configure detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

import agentops
# Initialize AgentOps before defining agents
agentops.init(
    api_key=os.getenv("AGENTOPS_API_KEY"),
    trace_name="policy-pulse-debug"
)

from google.adk.agents import Agent
from google.adk.sessions import DatabaseSessionService
import asyncio
from google.adk.runners import Runner
from google.adk.models.lite_llm import LiteLlm
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.tools import FunctionTool, agent_tool, google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.plugins.base_plugin import BasePlugin 
from google.adk.agents.invocation_context import InvocationContext


from google.genai import types

import psycopg2
from psycopg2.extras import RealDictCursor

import re
from typing import Optional

# Add this path manipulation
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..' , '..')
sys.path.insert(0, os.path.abspath(project_root))

from sqlalchemy import create_engine  # This will work - SQLAlchemy is already installed
from sqlalchemy.pool import QueuePool

#
from agents.policy_pulse_agent.FAQ_agent import FAQ_agent
from agents.policy_pulse_agent.ReportWriting_agent import ReportWriting_agent
from agents.policy_pulse_agent.ReportWriting_OpenAI_agent import ReportWriting_OpenAI_agent

APP_NAME = "policy_pulse_app"
USER_ID = "default_user"

# # Start MCP server as subprocess
# mcp_proc = subprocess.Popen(
#     ["python", "maps_mcp_server.py"],  # or absolute path
#     env={**os.environ, "GOOGLE_MAPS_API_KEY": os.environ["GOOGLE_MAPS_API_KEY"]},
# )

# # Give it a few seconds to boot up
# time.sleep(3)


# Read your DB URL from env
db_url = os.environ.get("DATABASE_URL")  # e.g. "postgresql://user:pass@host:5432/dbname"
if not db_url:
    raise RuntimeError("Please set DATABASE_URL in your .env")

# Shared database connection function for use in auth.py and session_utils.py
def get_db_connection_old():
    """Get database connection with robust configuration"""
    return psycopg2.connect(
        db_url, 
        cursor_factory=RealDictCursor,
        sslmode="require",
        keepalives_idle=60,
        keepalives_interval=15,
        keepalives_count=5
    )

# Create pool once at module level
_engine = None

class PooledConnection:
    """Wrapper to make SQLAlchemy connection work with 'with' statements"""
    def __init__(self, raw_conn):
        self.raw_conn = raw_conn
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.raw_conn.close()
    
    def cursor(self):
        # Force RealDictCursor when creating cursor
        return self.raw_conn.cursor(cursor_factory=RealDictCursor)
    
    def commit(self):
        return self.raw_conn.commit()

def get_db_connection():
    """Get database connection with pooling"""
    global _engine
    if _engine is None:
        _engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=5,                    # 5 connections in pool
            max_overflow=10,                # Up to 15 total connections
            pool_recycle=240,               # Match your ADK settings
            pool_pre_ping=True,             # Test connections before use
            connect_args={
                "sslmode": "require",
                "keepalives_idle": 60,
                "keepalives_interval": 15,
                "keepalives_count": 5,
            }
        )
   
    # Return wrapped connection that supports context manager
    raw_conn = _engine.raw_connection()
    return PooledConnection(raw_conn)

# Instantiate the persistent session service
from google.adk.sessions import DatabaseSessionService

session_service = DatabaseSessionService(
    db_url=db_url,               # your full supabase://…5432/postgres URL
    # 1) test every checkout:
    pool_pre_ping=True,
    # 2) proactively recycle before 5 min idle:
    pool_recycle=240,            # seconds (4 min)
    # 3) preserve SSL + keepalives for the socket itself:
    connect_args={
      "sslmode": "require",      # Supabase needs SSL
      "keepalives_idle": 60,
      "keepalives_interval": 15,
      "keepalives_count": 5,
    },
)

# (Optional) Artifact service—keeps artifacts in memory; swap for a DB-based store if you need
artifact_service = InMemoryArtifactService()

# The 4 functions below are to achieve query routing so as to speed up response times for short answer questions
def classify_query_intent(query: str) -> dict:
    """Classify query intent and complexity for routing hints"""
    query_lower = query.lower().strip()
    
    # Report creation patterns
    report_patterns = [
        r'\b(write|create|draft|generate|develop|build)\b.*\b(policy|document|report|guide)\b',
        r'\b(comprehensive|detailed|complete)\b.*\b(policy|analysis)\b',
        r'\bhow many (pages|words|sections)\b',
        r'\bwhat (topics|areas|sections)\b.*\binclude\b'
    ]
    
    # Simple FAQ patterns  
    faq_patterns = [
        r'^\s*(what|how|when|where|who|why)\b.*\?$',
        r'\b(tell me about|explain|define|mean)\b',
        r'\bwhat.*\b(companies|benefits|entitlements)\b.*\b(provide|offer)\b'
    ]
    
    # Complexity indicators
    complexity_indicators = [
        'comprehensive', 'detailed', 'analyze', 'compare', 'multiple', 
        'various', 'different', 'across', 'trends', 'typically'
    ]
    
    # Domain confidence indicators
    domain_terms = [
        'maternity', 'paternity', 'fertility', 'menopause', 'pregnancy',
        'benefits', 'policy', 'workplace', 'employer', 'leave', 'uk'
    ]
    
    # Classification logic
    intent = "general"
    if any(re.search(pattern, query_lower) for pattern in report_patterns):
        intent = "report_creation"
    elif any(re.search(pattern, query_lower) for pattern in faq_patterns):
        intent = "faq"
    
    # Calculate scores
    complexity_score = sum(1 for indicator in complexity_indicators if indicator in query_lower) / len(complexity_indicators)
    domain_score = sum(1 for term in domain_terms if term in query_lower) / 3
    logger.info(f"Query: {query} | Intent: {intent} | Complexity: {complexity_score:.2f} | Domain Confidence: {domain_score:.2f}")
    return {
        "intent": intent,
        "complexity_score": complexity_score,
        "domain_confidence": min(domain_score, 1.0),
        "has_question_mark": '?' in query,
        "word_count": len(query.split())
    }

def generate_routing_hints(query_analysis: dict, conversation_state: dict) -> dict:
    """Generate routing hints for the root agent"""
    
    # Never route during active conversations
    if conversation_state.get("writing_mode", False):
        return {"route": "root_agent", "priority": "conversational_flow"}
    
    if conversation_state.get("last_delegation") == "ReportWriting":
        return {"route": "root_agent", "priority": "conversation_continuity"}
    
    # Routing decision logic - FIXED THRESHOLDS
    intent = query_analysis["intent"]
    complexity = query_analysis["complexity_score"]
    domain_conf = query_analysis["domain_confidence"]
    has_question = query_analysis["has_question_mark"]
    
    # More lenient FAQ routing conditions
    if (has_question and domain_conf > 0.2 and complexity < 0.4) or \
       (intent == "faq" and complexity < 0.5):
        return {
            "route": "FAQ_agent", 
            "priority": "fast_response",
            "hint": "Simple domain question - delegate quickly to FAQ_agent"
        }
    
    if intent == "report_creation":
        return {
            "route": "root_agent",
            "priority": "conversation_management", 
            "hint": "This appears to be report creation - handle conversation flow"
        }
    
    return {
        "route": "root_agent",
        "priority": "default",
        "hint": "Complex or unclear query - use full reasoning"
    }

class RoutingPlugin(BasePlugin):
    def __init__(self):
        print("[RoutingPlugin] __init__")
        super().__init__(name="routing_plugin")

    async def on_user_message_callback(
        self, *,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> Optional[types.Content]:
        # -- visible in `adk web` logs --
        print("[RoutingPlugin] on_user_message_callback fired")
        # Extract raw text
        text_parts = [getattr(p, "text", "") for p in (user_message.parts or [])]
        user_text = " ".join([t for t in text_parts if t]).strip()
        print(f"[RoutingPlugin] user_text: {user_text[:120]}")

        session = invocation_context.session
        state = session.state or {}
        qa = classify_query_intent(user_text)
        hints = generate_routing_hints(qa, state.get("conversation_state", {}))
        state.update({"routing_analysis": qa, "routing_hints": hints, "last_query": user_text})
        print(f"[RoutingPlugin] analysis={qa} | hints={hints}")

        # FAST PATH → run FAQ, then prepare a review task for root
        # Inside on_user_message_callback
        if hints.get("priority") == "fast_response" and hints.get("route") == "FAQ_agent":
            print("[RoutingPlugin] FAST PATH → calling FAQ_agent directly")

            faq_runner = Runner(
                session_service=session_service,
                artifact_service=artifact_service,
                app_name=APP_NAME,
                agent=FAQ_agent,
            )
            faq_draft = await faq_runner.run(
                user_id=invocation_context.session.user_id,
                session_id=invocation_context.session.id,
                new_message=user_message,
            )

            review_prompt = (
                "The FAQ_agent has produced a draft answer. "
                "As the supervisor agent, your role now is to critically review this draft "
                "according to your standing instructions:\n"
                "- Check for accuracy, formatting, layout, presentation, and professional tone.\n"
                "- Remove any profanity, inappropriate language, or unverified claims.\n"
                "- Ensure PII is masked and compliance nuances are preserved.\n"
                "- Apply correct [DOC X] citation format, ensuring numbering is sequential.\n\n"
                f"FAQ_agent draft:\n{faq_draft.output_text}"
            )

            review_runner = Runner(
                session_service=session_service,
                artifact_service=artifact_service,
                app_name=APP_NAME,
                agent=root_agent,
            )
            reviewed = await review_runner.run(
                user_id=invocation_context.session.user_id,
                session_id=invocation_context.session.id,
                new_message=types.Content(role="user", parts=[types.Part(text=review_prompt)]),
            )

            print("[RoutingPlugin] returning reviewed answer directly (short-circuit)")
            return reviewed   # 👈 EARLY EXIT here

class TripwirePlugin(BasePlugin): # this is just for testing if plugins are working with the adk
    def __init__(self):
        super().__init__(name="tripwire")
        print("[TripwirePlugin] initialized")

    async def on_user_message_callback(
        self, *,
        invocation_context,
        user_message: types.Content
    ):
        print("[TripwirePlugin] fired with:", user_message)
        return None

# --- helpers ---
def _content_to_text(msg: types.Content | str) -> str:
    if isinstance(msg, str):
        return msg.strip()
    out = []
    for p in getattr(msg, "parts", []) or []:
        t = getattr(p, "text", None)
        if t:
            out.append(t)
    return " ".join(out).strip()

def _drain_run_and_get_assistant_content(runner, *, user_id: str, session_id: str, new_message: types.Content) -> types.Content:
    last_assistant = None
    for ev in runner.run(user_id=user_id, session_id=session_id, new_message=new_message):
        content = getattr(ev, "content", None)
        if content is None:
            data = getattr(ev, "data", None) or getattr(ev, "payload", None) or {}
            content = data.get("content")
        if isinstance(content, types.Content) and getattr(content, "role", None) == "assistant":
            last_assistant = content
    if last_assistant is None:
        last_assistant = types.Content(role="assistant", parts=[types.Part(text="")])
    return last_assistant

def _make_review_prompt(faq_text: str) -> str:
    return (
        "The FAQ_agent has produced a draft answer. "
        "As the supervisor agent, your role now is to critically review this draft "
        "according to your standing instructions:\n"
        "- Check for accuracy, formatting, layout, presentation, and professional tone.\n"
        "- Remove any profanity, inappropriate language, or unverified claims.\n"
        "- Ensure PII is masked and compliance nuances are preserved.\n"
        "- Apply correct [DOC X] citation format, ensuring numbering is sequential.\n\n"
        f"FAQ_agent draft:\n{faq_text}"
    )

def _get_ids_from_ctx(callback_context: CallbackContext):
    """Try several shapes to recover user_id and session_id across ADK builds."""
    inv = getattr(callback_context, "_invocation_context", None)
    user_id = session_id = None

    if inv:
        # The session object can be called session / _session / session_ref
        sess = getattr(inv, "session", None) or getattr(inv, "_session", None) or getattr(inv, "session_ref", None)
        # Direct fields can also exist
        user_id = getattr(inv, "user_id", None) or (getattr(sess, "user_id", None) if sess else None)
        session_id = getattr(inv, "session_id", None) or (getattr(sess, "id", None) if sess else None)

        if not (user_id and session_id):
            print(f"[fast-route] inv present but IDs missing. inv dir={dir(inv)} sess dir={dir(sess) if sess else None}")

    # As a last resort, try state (if you stash them there in your app)
    st = callback_context.state
    user_id = user_id or st.get("user_id") or st.get("_user_id")
    session_id = session_id or st.get("session_id") or st.get("_session_id")

    return user_id, session_id

# --- the fast-route hook ---
def fast_route_before_agent_callback(callback_context: CallbackContext, **kwargs):
    print("[fast-route] before_agent_callback fired")

    state = callback_context.state
    user_msg: types.Content | str = callback_context.user_content
    user_text = _content_to_text(user_msg)
    print(f"[fast-route] extracted user_text: {user_text[:160]!r}")

    # Classify + store hints for observability
    qa = classify_query_intent(user_text)
    hints = generate_routing_hints(qa, state.get("conversation_state", {}))
    state.update({"routing_analysis": qa, "routing_hints": hints, "last_query": user_text})
    print(f"[fast-route] analysis={qa} | hints={hints}")

    # Only attempt fast-path if it's a simple FAQ
    if not (hints.get("priority") == "fast_response" and hints.get("route") == "FAQ_agent"):
        print("[fast-route] normal path (no bypass)")
        return None

    # We need user_id/session_id to run sub-agents within the same session
    user_id, session_id = _get_ids_from_ctx(callback_context)
    if not (user_id and session_id):
        print("[fast-route] could not recover user_id/session_id → normal path")
        return None

    print(f"[fast-route] FAST PATH → FAQ_agent (user_id={user_id}, session_id={session_id})")

    # 1) FAQ run (sync). Use the exact user content we received.
    faq_runner = Runner(
        session_service=session_service,
        artifact_service=artifact_service,
        app_name=APP_NAME,
        agent=FAQ_agent,
    )
    faq_content = _drain_run_and_get_assistant_content(
        faq_runner,
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg if isinstance(user_msg, types.Content) else types.Content(role="user", parts=[types.Part(text=user_text)]),
    )
    faq_text = _content_to_text(faq_content)

    # 2) Review run (sync) as a single, short turn
    review_runner = Runner(
        session_service=session_service,
        artifact_service=artifact_service,
        app_name=APP_NAME,
        agent=root_agent,  # same agent; this turn is "review"
    )
    review_prompt = _make_review_prompt(faq_text)
    reviewed_content = _drain_run_and_get_assistant_content(
        review_runner,
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=review_prompt)]),
    )

    print("[fast-route] returning reviewed answer (root planning skipped)")
    # Returning Content here makes ADK skip the first heavy root LLM call
    return reviewed_content



INSTRUCTION = (
    "You are the supervisor agent for the Policy Pulse App which is a compliance assistant specializing in workplace reproductive and fertility health.\n\n"
    
    "SMART ROUTING OPTIMIZATION:\n"
    "FIRST ACTION: Check session state for 'routing_hints':\n"
    "- Log what you find: 'Found routing hints: [details]'\n"
    "- If routing_hints['priority'] == 'fast_response' and route == 'FAQ_agent':\n"
    "  Immediately respond: 'I'll get that information for you.'\n"
    "  • Then CALL THE TOOL: FAQ_agent with the original user message (no summaries, no extra planning).\n"
    "  • DO NOT reflect, chain-of-thought, or produce multi-step plans on this turn.\n"
    "- If routing_hints['route'] == 'root_agent' and priority == 'conversation_management':\n"
    "  → Handle the full conversational workflow yourself\n"
    "- Use routing_hints['hint'] for context about the query type\n\n"

    "CONVERSATION STATE MANAGEMENT:\n"
    "Always update conversation_state in session state:\n"
    "- Set 'writing_mode: true' when starting policy/report discussions\n"
    "- Set 'last_delegation: FAQ' or 'last_delegation: ReportWriting' after delegating\n"
    "- Check 'conversation_state' before making routing decisions\n\n"
    
    "POLICY GENERATION WORKFLOW:\n"
    "When a user requests a policy, guide, or guidelines, this should be handled by your report writing agent and you should follow this process:\n\n"
    
    "1. QUESTIONNAIRE PHASE:\n"
    "Ask these questions ONE AT A TIME (wait for each response):\n"
    "- 'What type of document do you need: Policy (formal rules), Guidelines (recommendations), or Guide (procedures)?'\n"
    "- 'What's the main focus: Fertility support, Pregnancy/maternity, Menopause, Miscarriage/bereavement, Parental leave, or Comprehensive coverage?'\n"
    "- 'Which specific areas should be covered?' (present checklist based on focus area)\n"
    "- 'What detail level: Brief (2-3 pages), Standard (5-7 pages), or Comprehensive (10+ pages)?'\n"
    "- 'Do you have any existing policies or documents to upload for reference or refinement?'\n\n"
    
    "2. VALIDATION PHASE:\n"
    "Review responses for consistency:\n"
    "- If brief length requested but many areas selected, suggest standard length\n"
    "- If conflicting requirements, ask for clarification\n"
    "- Ensure focus area matches selected coverage areas\n\n"
    
    "3. REFINEMENT REQUESTS HANDLING:\n"
    "If user asks to modify an existing policy (longer, shorter, add sections, etc.):\n"
    "- DO NOT ask for template modifications\n"
    "- DO NOT ask them to provide a revised DYNAMIC_TEMPLATE\n"
    "- Instead, generate a new dynamic template based on their refinement request\n"
    "- For length changes: adjust word counts and send new template to ReportWriting agent\n"
    "- For content changes: modify sections and send new template to ReportWriting agent\n\n"
    
    "REFINEMENT EXAMPLES:\n"
    "User: 'Make it standard length instead of brief'\n"
    "You: Generate new template with standard length word counts and delegate to ReportWriting agent\n\n"
    
    "User: 'Add a section on fertility support'\n"
    "You: Generate new template including fertility support section and delegate to ReportWriting agent\n\n"
    
    "4. GENERATION PHASE:\n"
    "When you receive a DYNAMIC_TEMPLATE from the system, OR when you need to generate/refine a policy:\n"
    "Immediately delegate to ReportWriting_OpenAI_agent with:\n\n"
    
    "'Generate a complete policy document following this exact template structure:\n"
    "[Include the full dynamic template here]\n\n"
    
    "CRITICAL REQUIREMENTS:\n"
    "- Use the EXACT title from the template policyTitle.text field\n"
    "- Follow ALL section titles exactly as specified\n"
    "- Meet the word count requirements (minWords to maxWords) for each section\n"
    "- Write complete, professional policy content\n"
    "- Do not write meta-commentary or descriptions\n"
    "- Start directly with the policy title and content'\n\n"
    "- Clearly LIST the primary sources used if they are referenced in the body of the document. You must include details like [DOC number] authors, publication year and direct URL if available. The [DOC] numbers should be in order eg 1,2,3 and you should not skip over any numbers. If these details are not available you should not speculate as to the reasons for this and should simply say unvailable. You should not say if the documents are traninig documents or internal documents\n"
    
    "5. DOCUMENT UPLOAD HANDLING:\n"
    "If user uploads documents, acknowledge and include context in the delegation to ReportWriting agent.\n\n"
    
    "DELEGATION RULES:\n"
    "- Policy generation/refinement: ReportWriting_OpenAI_agent (always include complete template)\n"
    "- Simple Q&A: FAQ_agent\n"
    "- Other writing tasks: ReportWriting_OpenAI_agent\n\n"

    "CRITICAL INSTRUCTIONS:\n"
    "You have at your disposal knowledgeable tools and sub-agents that you MUST delegate to them user queries unless the questions are of a very trivial nature. Note that your sub-agents have tools that allow them to search the internet for up-to-date information and also to ground responses\n"
    "The FAQ_agent handles short and medium-sized queries and the ReportWriting agent handles longer requests such as drafts of policies, guides and guidelines\n"
    "You should crtitically review what your sub-agents and tools return to you before you output it to the user for layout, quality, presentation, formatting and indentation\n"
    "What your sub agents or tools return to you should be screened and any profanity and inappropriate language should be removed\n"
    "Any personally identifiable information PII should be masked before being sent to the large language models"
    "If a user asks questions that are far away from your are of specialisation ie outside the general area of reproductive, fertility, hormonal, and sexual health, or are beyond general pleasantries, you should politely decline to answer and tell the user that you have not been trained to answer such topics\n"
    "If a user asks questions about medical conditions you should search for related NHS articles and provide these to the user.  You should in addition clearly state that you do not provide medical advice and that the user should seek advice from their Healthcare provider "
    "You MUST use the citation format [DOC X] where X is the document number.This is critical!\n\n"
    "INCORRECT: 'Companies should provide fertility benefits [1].'\n"
    "CORRECT: 'Companies should provide fertility benefits [DOC 1].'\n\n"
    "INCORRECT: 'Reproductive health policies should be inclusive [DOCUMENT 2].'\n"
    "CORRECT: 'Reproductive health policies should be inclusive [DOC 2].'\n\n"
    "When responding on technical questions always respond in a formal and not a casual manner to the user who is like a client\n"
    
    #"- ONLY use information contained in the provided documents to answer questions\n"
    #"- If the documents don't contain the answer, state clearly that you don't have that information\n"
    #"- NEVER make up or hallucinate information not present in the documents\n"
    #"- NEVER reference companies, monetary values, or details not explicitly mentioned in the documents\n"
    #"- Provide specific citations linking each piece of information to its source document\n"
    "- When uncertain about any detail, express uncertainty rather than guessing\n\n"
    "- the writing should strike an appropriate tone eg casual and conversational for blog articles"
    "Your role is to:\n"
    #"- Provide accurate information based SOLELY on the provided context documents\n"
    "- Ensure that sources are cited with clear document numbers\n"
    #"- Refuse to speculate beyond what is explicitly stated in the documents\n"
    "- Clearly LIST ALL the primary sources used for the final response that is output to the user. You should not cite more than 6 sources in the Source list although every claim in the response should be supported. You MUST use the citation format [DOC X] where X is the document number. The source list at the bottom should cover the sources that made it into the final response. For example, if three unique references are made in the response then there should be three unique resferences in the Sources list. \n" 
    " You should include the DOC number for each source and these DOC numbers should be in consecutive number i.e DOC 1, DOC2, DOC 3 and not DOC 1 DOC 4 DOC 6 and so you may need to amend the document references that come back from your tools to effect this.This is critical!\n\n"
    " Sources obtained from the _retrieve_context tool can be given author: \"We Are Eden\" and the rest of the metadata for such RAG documents should also be used. Sources returned by the web search function must include details like authors, publication year and URL if available \n" 
    "- Please indicate what LLM model was used in generating your answer. By LLM model i mean models like Gemini, Chat GPT, Claude, Perplexity etc\n"
    " Never include URLs, sources, or references unless they were directly returned by search tools. All claims requiring factual verification must use an appropriate websearch tool first, and only include references from the tool response.\n"
    "Before making any factual claims about current information, you MUST use an appropriate websearch tool. If the search fails or returns no results, state clearly that you could not verify the information rather than providing potentially outdated information.\n"
)

# just testing
#_retrieve_context("what are the goals of We Are Eden")

#model= "gemini-2.5-flash-preview-05-20"
# 
model="gemini-2.5-flash"
#
model_sonar=LiteLlm(
        model="openrouter/perplexity/sonar-pro",
        #base_url="https://api.perplexity.ai",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    )

model_openai=LiteLlm(
        model="openrouter/openai/o4-mini",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    )

FAQ_tool = AgentTool(agent=FAQ_agent)
ReportWriting_tool = AgentTool(agent=ReportWriting_OpenAI_agent)

root_agent = Agent(
    name="root_agent",
    model=model,
    description=(
        "Reproductive and fertility health agent."
    ),
    instruction=INSTRUCTION,
    tools = [FAQ_tool, ReportWriting_tool],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2,  # Adjust as needed (0.0-1.0)
    
    ),
    #before_agent_callback=fast_route_before_agent_callback,    
    #sub_agents = []
)

# Register the plugin
routing_plugin = RoutingPlugin()
#5) Set up your Runner
runner = Runner(
    session_service=session_service,
    artifact_service=artifact_service,
    app_name = APP_NAME,
    agent = root_agent,
    plugins=[TripwirePlugin()]
)

# If you want a CLI entrypoint—in case you ever `python agent.py`
if __name__ == "__main__":
    import asyncio
    from google.genai import types
    import uuid
    
    async def main():
        print("🔧 Setting up session...")
        
        # Generate a unique session ID for this run
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        print(f"📝 Using session ID: {session_id}")
        
        try:
            # AWAIT the async create_session method
            session = await session_service.create_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=session_id
            )
            print(f"✅ Session created: {session.id}")
            
            # AWAIT the async get_session method
            session_data = await session_service.get_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=session_id
            )
            
            if session_data is not None:
                print("✅ Session verified successfully")
            else:
                print("❌ Session verification failed")
                return
                
        except Exception as e:
            print(f"❌ Session creation failed: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print("🚀 Policy Pulse Agent Ready!")
        print("Type 'quit' to exit\n")
        
        while True:
            try:
                user_input = input("🤔 You: ")
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                
                print("🤖 Agent: ", end="", flush=True)
                
                # Create message content
                message = types.Content(
                    role='user',
                    parts=[types.Part(text=user_input)]
                )
                
                # Use run_async with EXACT same parameters as session creation
                async for event in runner.run_async(
                    user_id=USER_ID,        # Must match session creation
                    session_id=session_id,  # Must match session creation
                    new_message=message
                ):
                    if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                        for part in event.content.parts:
                            if hasattr(part, 'text'):
                                print(part.text, end="", flush=True)
                print("\n")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Runtime error: {e}")
                print(f"   Error type: {type(e).__name__}")
                print("   Continuing...")
        
        print("👋 Goodbye!")
    
    # Run the async main function
    asyncio.run(main())