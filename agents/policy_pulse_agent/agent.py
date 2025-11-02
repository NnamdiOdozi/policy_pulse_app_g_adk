"""
Policy Pulse Root Agent

ARCHITECTURE OVERVIEW:
This is the root/supervisor agent that orchestrates the Policy Pulse application.
It manages two specialized sub-agents:
- FAQ_agent: Handles quick factual questions using RAG
- ReportWriting_agent: Manages multi-turn policy document creation

Why separate sub-agents? - Specialization improves response quality and reduces token costs

UNUSUAL PATTERNS TO NOTE:
- Fast-path routing: Bypasses normal agent flow for FAQ queries (see RoutingPlugin)
- Context compression: Not yet implemented, but see comments about future optimization
- Tool wrapping: AgentTool wraps entire sub-agents as "tools" the root agent can call
"""

import asyncio
import os
import sys
from pathlib import Path

import logging
import agentops

# Load environment variables
from dotenv import load_dotenv

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

# === IMPORT SUB-AGENTS ===
# Each sub-agent is defined in its own folder with specialized instructions
from agents.policy_pulse_agent.FAQ_agent import FAQ_agent
from agents.policy_pulse_agent.ReportWriting_agent import ReportWriting_agent
from agents.policy_pulse_agent.ReportWriting_OpenAI_agent import ReportWriting_OpenAI_agent

# Configure detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Suppress AgentOps verbose logging
logging.getLogger('agentops').setLevel(logging.DEBUG)

load_dotenv()  # Load environment variables first (DATABASE_URL, API keys, etc.)
# === CONFIGURATION ===
APP_NAME = "policy_pulse_app"  # Used to namespace sessions in database
USER_ID = "default_user"  # Fallback if no user context provided

# === OBSERVABILITY SETUP ===
# AgentOps provides monitoring/tracing for AI agent behavior in production
# WHY: Helps debug multi-agent interactions and track tool usage

# Initialize AgentOps before defining agents
# === AGENTOPS CONFIGURATION ===
agentops_enabled = os.getenv("AGENTOPS_API_KEY") is not None

if agentops_enabled:
    agentops.init(
    api_key=os.getenv("AGENTOPS_API_KEY"),
    # v0.4.x: prevent an auto session so we control lifecycle
    auto_start_session=False,
    # keep your labels; in 0.4.x `tags` as list is fine
    trace_name="policy-pulse-debug",
    tags=["policy-pulse", "production"],
    default_tags=[os.getenv("ENVIRONMENT", "development")],
)
    logger.info("✅ AgentOps initialized and tracking enabled")

    # Test connection
    try:
        test_session = agentops.start_session(tags=["initialization-test"])
        test_session.record(agentops.ActionEvent(
            action_type="app_startup",
            params={"app_name": APP_NAME},
            returns={"status": "ready"}
        ))
        test_session.end_session(end_state="Success")
        logger.info("✅ AgentOps test session completed")
    except Exception as e:
        logger.warning(f"⚠️ AgentOps test failed: {e}")
else:
    logger.warning("⚠️ AGENTOPS_API_KEY not set - tracking disabled")

# Calculate project root based on file location
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent  # Adjust levels as needed
sys.path.insert(0, str(project_root))

db_url = os.getenv("DATABASE_URL")  # Full database URL from environment
# === SESSION SERVICE SETUP ===
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

# === ARTIFACT SERVICE ===
# Artifacts are large outputs (documents, code) that agents generate
# WHY IN-MEMORY? We don't need persistence for artifacts - they're regenerated on demand
# (Optional) Artifact service—keeps artifacts in memory; swap for a DB-based store if you need
artifact_service = InMemoryArtifactService()

# =============================================================================
# ROOT AGENT INSTRUCTIONS
# =============================================================================

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
    
    "CRITICAL - UPLOADED DOCUMENTS:\n"
    "When users upload documents (PDFs, DOCX, TXT) during the questionnaire:\n"
    "- The TEXT CONTENT has been pre-extracted from these files\n"
    "- The extracted text is included in messages under 'Uploaded Documents Context'\n"
    "- You DO have access to this content - it's right there in the prompt\n"
    "- DO NOT say 'I cannot access attached files' or 'I cannot read PDFs'\n"
    "- DO acknowledge the uploaded content when users mention it\n"
    "- Example: User uploads 'maternity_policy.pdf' → You say: 'Thanks for uploading maternity_policy.pdf. "
    "I can see it covers [brief summary]. I'll use this as reference when generating your new policy.'\n"
    "- When generating the policy, pass the uploaded document context to ReportWriting_OpenAI_agent\n\n"
    

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

# === WRAP SUB-AGENTS AS TOOLS ===
# UNUSUAL: We wrap entire agents as tools
# WHY? Allows root agent to "call" sub-agents via tool calling interface
# The root agent sees these as function calls, ADK handles the delegation
FAQ_tool = AgentTool(agent=FAQ_agent)
ReportWriting_tool = AgentTool(agent=ReportWriting_OpenAI_agent)

# === CREATE ROOT AGENT ===
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
#routing_plugin = RoutingPlugin()

# === CREATE RUNNER ===
# Runner executes the agent conversation loop
# Plugins are registered here
runner = Runner(
    session_service=session_service,
    artifact_service=artifact_service,
    app_name = APP_NAME,
    agent = root_agent,
    
)

# =============================================================================
# CLI ENTRY POINT (for testing)
# =============================================================================
# If you want a CLI entrypoint—in case you ever `python agent.py`

if __name__ == "__main__":
    """
    This runs when you execute: python agent.py
    Useful for testing the agent without Streamlit frontend.
    """
    import uuid
    
    async def main():
        print("🔧 Setting up session...")
        
        # Generate a unique session ID for this run
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        print(f"📝 Using session ID: {session_id}")
        
        try:
            # Create session
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

        # Simple REPL Loop
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
                
                # Use run_async with EXACT same parameters as session creation to run agent
                async for event in runner.run_async(
                    user_id=USER_ID,        # Must match session creation
                    session_id=session_id,  # Must match session creation
                    new_message=message
                ):
                    if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                        for part in event.content.parts:
                            if hasattr(part, 'text'):
                                print(part.text, end="", flush=True)
                print("\n") # New line after response
                
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