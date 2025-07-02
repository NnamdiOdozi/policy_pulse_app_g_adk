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
from google.adk.tools import FunctionTool, agent_tool
from google.adk.tools.agent_tool import AgentTool
from google.genai import types
from .FAQ_agent import FAQ_agent
from .ReportWriting_agent import ReportWriting_agent
from .ReportWriting_OpenAI_agent import ReportWriting_OpenAI_agent

# Add this path manipulation
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..' , '..')
sys.path.insert(0, os.path.abspath(project_root))

from sqlalchemy import create_engine  # This will work - SQLAlchemy is already installed

from .tools import RetrieveContextTool

APP_NAME = "policy_pulse_app"
USER_ID = "default_user"

# Read your DB URL from env
db_url = os.environ.get("DATABASE_URL")  # e.g. "postgresql://user:pass@host:5432/dbname"
if not db_url:
    raise RuntimeError("Please set DATABASE_URL in your .env")

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
  "You are the supervisor agent for the Policy Pulse Appp which is a compliance assistant specializing in workplace reproductive and fertility health.\n\n"
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

model= "gemini-2.5-flash-preview-05-20"
# 
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
    model=model_openai,
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