"""
Policy Pulse - Looping Agent Integration Examples

This file demonstrates different approaches to integrate looping/refinement
agents into the Policy Pulse architecture.

THREE APPROACHES:
1. Simple Quality Loop (Recommended for FAQ)
2. Conditional Looping (Smart routing + loop)
3. Multi-Stage Pipeline (Complex workflows)
"""

import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import Agent, LoopAgent, LlmAgent, SequentialAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.agent_tool import AgentTool
from google.adk.sessions import DatabaseSessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.runners import Runner
from google.genai import types

# Import your existing agents
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, os.path.abspath(project_root))

from agents.policy_pulse_agent.FAQ_agent import FAQ_agent
from agents.policy_pulse_agent.ReportWriting_OpenAI_agent import ReportWriting_OpenAI_agent

# =============================================================================
# CONFIGURATION
# =============================================================================

APP_NAME = "policy_pulse_looping_examples"
USER_ID = "test_user"
db_url = os.environ.get("DATABASE_URL")

session_service = DatabaseSessionService(
    db_url=db_url,
    pool_pre_ping=True,
    pool_recycle=240,
    connect_args={
        "sslmode": "require",
        "keepalives_idle": 60,
        "keepalives_interval": 15,
        "keepalives_count": 5,
    },
)

artifact_service = InMemoryArtifactService()

# =============================================================================
# STATE KEYS
# =============================================================================

STATE_USER_QUERY = "user_query"
STATE_CURRENT_RESPONSE = "current_response"
STATE_CRITIQUE = "critique"
APPROVAL_PHRASE = "RESPONSE_APPROVED"

# =============================================================================
# LOOP EXIT TOOL
# =============================================================================

def exit_refinement_loop(tool_context: ToolContext):
    """Exit the refinement loop when quality standards are met."""
    print(f"[EXIT] Refinement complete by {tool_context.agent_name}")
    tool_context.actions.escalate = True
    return {"status": "approved"}

# =============================================================================
# APPROACH 1: SIMPLE QUALITY LOOP
# Best for: FAQ responses that need quality checks
# =============================================================================

def create_simple_quality_loop():
    """
    Simple pattern: FAQ → Critic → Refiner → Output
    
    Use this when you want to add quality review to FAQ responses.
    """
    
    # Quality critic
    critic = LlmAgent(
        name="QualityCritic",
        model="gemini-2.5-flash",
        include_contents='none',
        instruction=f"""Review this response for quality:
        
        Response: {{{STATE_CURRENT_RESPONSE}}}
        
        Check for:
        - Accuracy and completeness
        - Professional tone
        - Proper citations [DOC X]
        - No inappropriate content
        
        IF response meets all standards:
        Output EXACTLY: "{APPROVAL_PHRASE}"
        
        ELSE provide specific critique for improvement.
        Output only critique OR approval phrase.""",
        output_key=STATE_CRITIQUE
    )
    
    # Refiner
    refiner = LlmAgent(
        name="Refiner",
        model="gemini-2.5-flash",
        include_contents='none',
        instruction=f"""Current Response: {{{STATE_CURRENT_RESPONSE}}}
        Critique: {{{STATE_CRITIQUE}}}
        
        IF critique is EXACTLY "{APPROVAL_PHRASE}":
        Call exit_refinement_loop function.
        
        ELSE apply critique to improve response.
        Output only improved response.""",
        tools=[exit_refinement_loop],
        output_key=STATE_CURRENT_RESPONSE
    )
    
    # Create loop
    quality_loop = LoopAgent(
        name="QualityLoop",
        sub_agents=[critic, refiner],
        max_iterations=3
    )
    
    # Wrap FAQ agent and quality loop in sequence
    # NOTE: SequentialAgent needs BaseAgent instances, not AgentTool wrappers
    faq_with_quality = SequentialAgent(
        name="FAQ_with_QualityLoop",
        sub_agents=[
            FAQ_agent,  # Generate initial response (direct agent, not wrapped)
            quality_loop  # Refine iteratively
        ],
        description="FAQ with automatic quality refinement"
    )
    
    return faq_with_quality

# =============================================================================
# APPROACH 2: CONDITIONAL LOOPING
# Best for: Smart routing where only some queries need loops
# =============================================================================

def create_conditional_loop_agent():
    """
    Conditional pattern: Root decides IF looping is needed
    
    Use this when you want to loop only for complex queries.
    """
    
    # Same critic/refiner as above
    critic = LlmAgent(
        name="ConditionalCritic",
        model="gemini-2.5-flash",
        include_contents='none',
        instruction=f"""Review: {{{STATE_CURRENT_RESPONSE}}}
        
        IF response is complete and accurate:
        Output: "{APPROVAL_PHRASE}"
        ELSE provide specific improvements needed.""",
        output_key=STATE_CRITIQUE
    )
    
    refiner = LlmAgent(
        name="ConditionalRefiner",
        model="gemini-2.5-flash",
        include_contents='none',
        instruction=f"""Response: {{{STATE_CURRENT_RESPONSE}}}
        Critique: {{{STATE_CRITIQUE}}}
        
        IF critique == "{APPROVAL_PHRASE}": Call exit_refinement_loop
        ELSE improve the response.""",
        tools=[exit_refinement_loop],
        output_key=STATE_CURRENT_RESPONSE
    )
    
    refinement_loop = LoopAgent(
        name="ConditionalLoop",
        sub_agents=[critic, refiner],
        max_iterations=2
    )
    
    # Root agent with loop as a tool
    instruction = """You are Policy Pulse supervisor.
    
    WORKFLOW:
    1. For simple FAQ queries: Use FAQ_agent directly
    2. For policy generation: Use ReportWriting_OpenAI_agent
    3. For queries needing refinement: Use the refinement loop
    
    Check session state 'needs_refinement' to decide.
    """
    
    # For Agent (not SequentialAgent), we DO use AgentTool to wrap sub-agents
    root_with_loop = Agent(
        name="root_with_conditional_loop",
        model="gemini-2.5-flash",
        instruction=instruction,
        tools=[
            AgentTool(agent=FAQ_agent),
            AgentTool(agent=ReportWriting_OpenAI_agent),
            AgentTool(agent=refinement_loop)  # AgentTool doesn't take 'name' parameter
        ]
    )
    
    return root_with_loop

# =============================================================================
# APPROACH 3: MULTI-STAGE PIPELINE
# Best for: Complex workflows with multiple review stages
# =============================================================================

def create_multi_stage_pipeline():
    """
    Multi-stage pattern: Generate → Review → Refine → Final Review
    
    Use this for complex policy generation with multiple quality gates.
    """
    
    # Stage 1: Initial generation
    initial_generator = LlmAgent(
        name="InitialGenerator",
        model="gemini-2.5-flash",
        include_contents='none',
        instruction=f"""Generate initial response to: {{{STATE_USER_QUERY}}}
        
        Provide comprehensive, accurate information.
        Output only the response.""",
        output_key=STATE_CURRENT_RESPONSE
    )
    
    # Stage 2: Content review (in loop)
    content_reviewer = LlmAgent(
        name="ContentReviewer",
        model="gemini-2.5-flash",
        include_contents='none',
        instruction=f"""Review content accuracy:
        {{{STATE_CURRENT_RESPONSE}}}
        
        IF content is accurate and complete: "{APPROVAL_PHRASE}"
        ELSE provide specific accuracy issues.""",
        output_key=STATE_CRITIQUE
    )
    
    content_refiner = LlmAgent(
        name="ContentRefiner",
        model="gemini-2.5-flash",
        include_contents='none',
        instruction=f"""Response: {{{STATE_CURRENT_RESPONSE}}}
        Issues: {{{STATE_CRITIQUE}}}
        
        IF critique == "{APPROVAL_PHRASE}": Call exit_refinement_loop
        ELSE fix accuracy issues.""",
        tools=[exit_refinement_loop],
        output_key=STATE_CURRENT_RESPONSE
    )
    
    content_loop = LoopAgent(
        name="ContentRefinementLoop",
        sub_agents=[content_reviewer, content_refiner],
        max_iterations=2
    )
    
    # Stage 3: Format review (in loop)
    format_reviewer = LlmAgent(
        name="FormatReviewer",
        model="gemini-2.5-flash",
        include_contents='none',
        instruction=f"""Review formatting:
        {{{STATE_CURRENT_RESPONSE}}}
        
        Check citations, structure, professional tone.
        IF formatting is perfect: "{APPROVAL_PHRASE}"
        ELSE provide formatting improvements.""",
        output_key=STATE_CRITIQUE
    )
    
    format_refiner = LlmAgent(
        name="FormatRefiner",
        model="gemini-2.5-flash",
        include_contents='none',
        instruction=f"""Response: {{{STATE_CURRENT_RESPONSE}}}
        Format issues: {{{STATE_CRITIQUE}}}
        
        IF critique == "{APPROVAL_PHRASE}": Call exit_refinement_loop
        ELSE fix formatting.""",
        tools=[exit_refinement_loop],
        output_key=STATE_CURRENT_RESPONSE
    )
    
    format_loop = LoopAgent(
        name="FormatRefinementLoop",
        sub_agents=[format_reviewer, format_refiner],
        max_iterations=2
    )
    
    # Complete pipeline
    multi_stage_pipeline = SequentialAgent(
        name="MultiStagePipeline",
        sub_agents=[
            initial_generator,  # Generate
            content_loop,       # Review content
            format_loop         # Review format
        ],
        description="Multi-stage policy generation with dual review loops"
    )
    
    return multi_stage_pipeline

# =============================================================================
# TESTING EXAMPLES
# =============================================================================

async def test_simple_quality_loop():
    """Test the simple quality loop approach"""
    print("\n" + "="*70)
    print("TESTING: Simple Quality Loop")
    print("="*70 + "\n")
    
    agent = create_simple_quality_loop()
    runner = Runner(
        session_service=session_service,
        artifact_service=artifact_service,
        app_name=APP_NAME,
        agent=agent
    )
    
    session_id = f"simple_loop_test_{os.urandom(4).hex()}"
    test_query = "What maternity leave benefits do UK companies typically provide?"
    
    message = types.Content(
        role='user',
        parts=[types.Part(text=test_query)]
    )
    
    print(f"Query: {test_query}\n")
    print("Agent output:")
    
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=message
    ):
        if hasattr(event, 'content') and hasattr(event.content, 'parts'):
            for part in event.content.parts:
                if hasattr(part, 'text'):
                    print(part.text, end="", flush=True)
    print("\n")

async def test_conditional_loop():
    """Test conditional looping approach"""
    print("\n" + "="*70)
    print("TESTING: Conditional Loop")
    print("="*70 + "\n")
    
    agent = create_conditional_loop_agent()
    runner = Runner(
        session_service=session_service,
        artifact_service=artifact_service,
        app_name=APP_NAME,
        agent=agent
    )
    
    session_id = f"conditional_loop_test_{os.urandom(4).hex()}"
    test_query = "Explain fertility treatment coverage in workplace policies"
    
    message = types.Content(
        role='user',
        parts=[types.Part(text=test_query)]
    )
    
    print(f"Query: {test_query}\n")
    print("Agent output:")
    
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=message
    ):
        if hasattr(event, 'content') and hasattr(event.content, 'parts'):
            for part in event.content.parts:
                if hasattr(part, 'text'):
                    print(part.text, end="", flush=True)
    print("\n")

async def test_multi_stage():
    """Test multi-stage pipeline"""
    print("\n" + "="*70)
    print("TESTING: Multi-Stage Pipeline")
    print("="*70 + "\n")
    
    agent = create_multi_stage_pipeline()
    runner = Runner(
        session_service=session_service,
        artifact_service=artifact_service,
        app_name=APP_NAME,
        agent=agent
    )
    
    session_id = f"multi_stage_test_{os.urandom(4).hex()}"
    
    # Initialize session with query
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id
    )
    session.state[STATE_USER_QUERY] = "Describe menopause workplace support policies"
    await session_service.update_session(session)
    
    test_query = "Generate response"
    message = types.Content(
        role='user',
        parts=[types.Part(text=test_query)]
    )
    
    print(f"Query: Describe menopause workplace support policies\n")
    print("Agent output:")
    
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=message
    ):
        if hasattr(event, 'content') and hasattr(event.content, 'parts'):
            for part in event.content.parts:
                if hasattr(part, 'text'):
                    print(part.text, end="", flush=True)
    print("\n")

# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Run all test examples"""
    print("\n" + "="*70)
    print("POLICY PULSE - LOOPING AGENT EXAMPLES")
    print("="*70)
    
    # Test each approach
    await test_simple_quality_loop()
    await test_conditional_loop()
    await test_multi_stage()
    
    print("\n" + "="*70)
    print("All tests complete!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
