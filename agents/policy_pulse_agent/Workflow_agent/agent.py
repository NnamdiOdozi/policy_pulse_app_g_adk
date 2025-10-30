# Part of agent.py --> Follow https://google.github.io/adk-docs/get-started/quickstart/ to learn the setup

import asyncio
import os
from google.adk.agents import LoopAgent, LlmAgent, BaseAgent, SequentialAgent
from google.genai import types
from google.adk.runners import InMemoryRunner
from google.adk.agents.invocation_context import InvocationContext
from google.adk.tools.tool_context import ToolContext
from typing import AsyncGenerator, Optional
from google.adk.events import Event, EventActions
import logging
from ..tools import search_with_tavily_faq, search_with_exa, _retrieve_context_zilliz



logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

# --- Constants ---
APP_NAME = "doc_writing_app_v3" # New App Name
USER_ID = "dev_user_01"
SESSION_ID_BASE = "loop_exit_tool_session" # New Base Session ID
GEMINI_MODEL = "gemini-2.0-flash"
STATE_INITIAL_TOPIC = "initial_topic"

STATE_USER_QUERY = "user_query"
STATE_CURRENT_RESPONSE = "current_response"
STATE_QUALITY_CRITIQUE = "quality_critique"
QUALITY_APPROVED_PHRASE = "RESPONSE_APPROVED"

# --- Tool Definition ---
def exit_quality_loop(tool_context: ToolContext):
  """Call this function ONLY when the critique indicates no further changes are needed, signaling the iterative process should end."""
  print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
  tool_context.actions.escalate = True
  # Return empty dict as tools should typically return JSON-serializable output
  return {}

INSTRUCTION = (
"You are a general purpose assistant specializing in workplace reproductive and fertility health.\n\n")

model="gemini-2.5-flash"



# Quality Critic - Reviews FAQ responses
quality_critic = LlmAgent(
    name="QualityCritic",
    model="gemini-2.5-flash",
    include_contents='default',  # Include context to understand the query
    instruction=f"""You are a Quality Assurance Critic for Policy Pulse FAQ responses.
    
    Review this response for:
    - Accuracy and completeness
    - Professional tone
    - Proper citation format [DOC X]
    - No PII or inappropriate content
    - Clear structure and formatting
    
    **Response to Review:**
    {{{STATE_CURRENT_RESPONSE}}}
    
    **Task:**
    IF the response meets all quality standards (accurate, well-formatted, professional):
    Respond EXACTLY with: "{QUALITY_APPROVED_PHRASE}"
    
    ELSE provide specific, actionable critique:
    - What needs improvement
    - Specific issues found
    - Suggested fixes
    
    Output only the critique OR the approval phrase.""",
    output_key=STATE_QUALITY_CRITIQUE
)

# Response Refiner - Applies critique or exits loop
response_refiner = LlmAgent(
    name="ResponseRefiner",
    model="gemini-2.5-flash",
    include_contents='default',  # Include context
    instruction=f"""You are a Response Refiner for Policy Pulse.
    
    **Current Response:**
    {{{STATE_CURRENT_RESPONSE}}}
    
    **Quality Critique:**
    {{{STATE_QUALITY_CRITIQUE}}}
    
    **TASK:**
    
    If the critique says "{QUALITY_APPROVED_PHRASE}":
    → Call the exit_quality_loop tool (do not write anything)
    
    Otherwise, improve the current response by:
    - Fixing the specific issues mentioned in the critique
    - Ensuring proper citation format [DOC X]
    - Improving clarity and professionalism
    - Output ONLY the complete improved response text (not a summary or apology)
    
    DO NOT say "I apologize" or explain what you're doing. Just output the improved response or call the tool.""",
    tools=[exit_quality_loop],
    output_key=STATE_CURRENT_RESPONSE
)

# Quality Review Loop - This is the main export for use by other agents
quality_review_loop = LoopAgent(
    name="QualityReviewLoop",
    sub_agents=[
        quality_critic,
        response_refiner
    ],
    max_iterations=3  # Prevent infinite loops
)

# Output agent - Simply outputs the refined response from state
output_agent = LlmAgent(
    name="OutputAgent",
    model="gemini-2.5-flash",
    include_contents='none',
    instruction=f"""Your task is to output the final refined response exactly as written in the state, with no changes or additions.

**Refined Response from State:**
{{{STATE_CURRENT_RESPONSE}}}

Output this response verbatim. Do not add commentary, apologies, or explanations."""
)

# Pipeline that includes the loop and output
quality_pipeline = SequentialAgent(
    name="QualityPipeline",
    sub_agents=[
        quality_review_loop,
        output_agent
    ]
)

# Export the quality pipeline as the root agent
# This agent expects STATE_CURRENT_RESPONSE to be set by a previous agent
# It reviews and refines the response in place, then outputs it
root_agent = quality_pipeline

# Note: FAQ_agent and other agents should use quality_review_loop in a pipeline:
# SequentialAgent(sub_agents=[their_responder, quality_review_loop])

