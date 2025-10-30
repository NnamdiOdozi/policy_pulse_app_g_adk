# =============================================================================
# THIS FILE IS STILL WIP - DO NOT USE 
# =============================================================================

# === GOOGLE ADK IMPORTS ===
# Agent Development Kit (ADK) - Google's framework for building agentic systems
from google.adk.agents import Agent
from google.adk.sessions import DatabaseSessionService, InMemorySessionService # Session persistence options
from google.adk.runners import Runner # Executes agent conversations
from google.adk.models.lite_llm import LiteLlm
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService # Artifact storage
from google.adk.tools import FunctionTool, agent_tool, google_search #Wtappers for Python functions as tools
from google.adk.tools.agent_tool import AgentTool #Wraps entire agents as tools
from google.adk.agents.callback_context import CallbackContext #Access to session state during execution
from google.adk.models import LlmRequest, LlmResponse
from google.adk.plugins.base_plugin import BasePlugin # For custom pre/post-processing logic
from google.adk.agents.invocation_context import InvocationContext # For plugin callbacks

from google.genai import types

# =============================================================================
# ROUTING LOGIC - QUERY CLASSIFICATION
# =============================================================================

# The 4 functions below are to achieve query routing so as to speed up response times for short answer questions
def classify_query_intent(query: str) -> dict:
    """Classify query intent and complexity for routing hints

    WHY? Different query types need different handling:
    - Simple FAQs: Fast-path to FAQ_agent (skip heavy planning)
    - Policy requests: Route to ReportWriting_agent
    - Conversational: Let root agent handle
    
    APPROACH: Uses regex patterns + keyword scoring
    - Simple but effective for POC
    - Alternative: Could use an LLM classifier for more accuracy
    - Trade-off: Keywords are fast but less flexible
    
    Returns:
        dict with keys:
        - intent: 'faq' | 'report_creation' | 'general'
        - complexity_score: float 0-1
        - domain_confidence: float 0-1
        - has_question_mark: bool
        - word_count: int
    
    """
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

# =============================================================================
# ROUTING PLUGIN - FAST-PATH OPTIMIZATION
# =============================================================================

class RoutingPlugin(BasePlugin):
    """
    Custom plugin that implements "fast-path" routing for FAQ queries.
    
    CONTEXT ENGINEERING TECHNIQUE: "Offload and bypass"
    Instead of sending every query through the full agent planning cycle:
    1. Classify query intent BEFORE the root agent sees it
    2. For simple FAQs, directly call FAQ_agent
    3. Skip the root agent's chain-of-thought planning (saves tokens)
    4. Return result immediately
    
    WHY THIS WORKS:
    - FAQ queries are stateless (don't need conversation context)
    - FAQ_agent is specialized and fast
    - Root agent's planning adds latency without value for simple queries
    
    TRADE-OFFS:
    - Faster response (2-3s saved)
    - Lower token cost (~1000 tokens saved)
    - BUT: Bypasses root agent's quality control/review
    
    WHEN NOT TO USE:
    - Complex queries needing context
    - Follow-up questions
    - Queries needing multi-agent coordination
    """

    def __init__(self):
        print("[RoutingPlugin] __init__")
        super().__init__(name="routing_plugin")

    async def on_user_message_callback(
        self, *,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> Optional[types.Content]:
        """
        Hook that runs BEFORE the root agent processes the message.
        
        This is where the magic happens - we can intercept the message,
        analyze it, and potentially return a response without ever
        calling the root agent's LLM.
        """
        
        # -- visible in `adk web` logs --
        print("[RoutingPlugin] on_user_message_callback fired")
        # Extract raw text
        text_parts = [getattr(p, "text", "") for p in (user_message.parts or [])]
        user_text = " ".join([t for t in text_parts if t]).strip()
        print(f"[RoutingPlugin] user_text: {user_text[:120]}")

        session = invocation_context.session
        state = session.state or {}

        # Classify query and store in session state for observability
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

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def _content_to_text(msg: types.Content | str) -> str:
    """
    Extract plain text from Google's Content type
    
    WHY NEEDED? ADK uses structured Content objects with parts.
    We often need just the raw text string for processing.
    """
    if isinstance(msg, str):
        return msg.strip()
    out = []
    for p in getattr(msg, "parts", []) or []:
        t = getattr(p, "text", None)
        if t:
            out.append(t)
    return " ".join(out).strip()

def _drain_run_and_get_assistant_content(runner, *, user_id: str, session_id: str, new_message: types.Content) -> types.Content:
    """
    Run an agent and extract the final assistant response.
    
    WHY "DRAIN"? runner.run() returns a generator of events.
    We need to consume all events and extract the final response.
    
    This is a synchronous wrapper around ADK's event stream.
    """
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
    """
    Generate a prompt for the root agent to review FAQ_agent's output
    
    WHY REVIEW? FAQ_agent might include:
    - Inappropriate content
    - Incorrect citations
    - PII that should be masked
    """
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
