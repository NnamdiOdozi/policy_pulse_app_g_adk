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
# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import Agent
from google.adk.sessions import DatabaseSessionService
import asyncio
from google.adk.runners import Runner
from google.adk.models.lite_llm import LiteLlm
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.tools import FunctionTool, agent_tool, google_search
from google.adk.tools.agent_tool import AgentTool
from google.genai import types
import psycopg2
from psycopg2.extras import RealDictCursor

# Add this path manipulation
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..' , '..')
sys.path.insert(0, os.path.abspath(project_root))

from sqlalchemy import create_engine  # This will work - SQLAlchemy is already installed
from sqlalchemy.pool import QueuePool

from agents.policy_pulse_agent.tools import RetrieveContextTool
from agents.policy_pulse_agent.FAQ_agent import FAQ_agent
from agents.policy_pulse_agent.ReportWriting_agent import ReportWriting_agent
from agents.policy_pulse_agent.ReportWriting_OpenAI_agent import ReportWriting_OpenAI_agent

APP_NAME = "policy_pulse_app"
USER_ID = "default_user"

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

INSTRUCTION = (
    "You are the supervisor agent for the Policy Pulse App which is a compliance assistant specializing in workplace reproductive and fertility health.\n\n"
    
    "POLICY GENERATION WORKFLOW:\n"
    "When a user requests a policy, guide, or guidelines, follow this process:\n\n"
    
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
    
    "5. DOCUMENT UPLOAD HANDLING:\n"
    "If user uploads documents, acknowledge and include context in the delegation to ReportWriting agent.\n\n"
    
    "DELEGATION RULES:\n"
    "- Policy generation/refinement: ReportWriting_OpenAI_agent (always include complete template)\n"
    "- Simple Q&A: FAQ_agent\n"
    "- Other writing tasks: ReportWriting_OpenAI_agent\n\n"


        "CRITICAL INSTRUCTIONS:\n" \
        "You have at your disposal knowledgeable tools and sub-agents that you should delegate to them user queries unless the questions are of a very trivial and general nature\n"
        "You should crtitically review what your sub-agents and tools return to you before you output it to the user for layout, quality, presentation, formatting and indentation\n"
        "What your sub agents are tools return to you should be screened and any profanity and inappropriate language should be removed\n"
        "Any personally identifiable information PII should be masked before being sent to the large language models" \
        "If a user asks questions that are far away from your are of specialisation ie outside the general area of reproductive, fertility and sexual health, or are beyond general pleasantries, you should politely decline to answer and tell the user that you have not been trained to answer such topics\n"
        "If a user asks questions about medical conditions you should search for related NHS articles and provide these to the user.  You should in addition clearly state that you do not provide medical advice and that the user should seek advice from their Healthcare provider " \
        "You MUST use the citation format [DOC X] where X is the document number.This is critical!\n\n"
        "INCORRECT: 'Companies should provide fertility benefits [1].'\n"
        "CORRECT: 'Companies should provide fertility benefits [DOC 1].'\n\n"
        "INCORRECT: 'Reproductive health policies should be inclusive [DOCUMENT 2].'\n"
        "CORRECT: 'Reproductive health policies should be inclusive [DOC 2].'\n\n"
        "When responding on technical questions always respond in a formal and not a casual manner to the user who is like a client\n" \
        
        #"- ONLY use information contained in the provided documents to answer questions\n"
        #"- If the documents don't contain the answer, state clearly that you don't have that information\n"
        #"- NEVER make up or hallucinate information not present in the documents\n"
        #"- NEVER reference companies, monetary values, or details not explicitly mentioned in the documents\n"
        #"- Provide specific citations linking each piece of information to its source document\n"
        "- When uncertain about any detail, express uncertainty rather than guessing\n\n"
        " - the writing should strike an appropriate tone eg casual and conversational for blog articles"
        "Your role is to:\n"
        #"- Provide accurate information based SOLELY on the provided context documents\n"
        "- Ensure that sources are cited with clear document numbers\n"
        #"- Refuse to speculate beyond what is explicitly stated in the documents\n"
       
        "- Clearly LIST the primary sources used for the summary. You must include details like authors, publication year and direct URL if available. If these details are not available you should not speculate as to the reasons for this and should simply say unvailable. You should not say if the documents rae traninig documents or internal documents\n"
        "- Please indicate what LLM model was used in generating your answer. By LLM model i mean models like Gemini, Chat GPT, Claude, Perplexity etc\n"

)




# just testing
#_retrieve_context("what are the goals of We Are Eden")

#model= "gemini-2.5-flash-preview-05-20"
# 
model="gemini-2.5-pro"
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
        temperature=0.5,  # Adjust as needed (0.0-1.0)
    ),
        
    #sub_agents = []
)

#print(root_agent.model)

#5) Set up your Runner
runner = Runner(
    session_service=session_service,
    artifact_service=artifact_service,
    app_name = APP_NAME,
    agent = root_agent
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
            verify_session = await session_service.get_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=session_id
            )
            
            if verify_session:
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