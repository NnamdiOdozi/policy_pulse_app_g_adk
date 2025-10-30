"""
Example: Integrating File Writing Tools into Policy Pulse Agent

This shows how to add file writing capabilities to your agents.
"""

from google.adk.agents import Agent
from google.genai import types

# Import file writing tools
from agents.policy_pulse_agent.tools import (
    write_file,              # Universal file writer (recommended)
    write_markdown_file,     # Markdown specific
    write_word_document,     # Word specific
    write_text_file          # Text specific
)

# =============================================================================
# EXAMPLE 1: Add to Root Agent (Simple Approach)
# =============================================================================

def example_1_simple():
    """Add write_file to root agent - simplest approach"""
    
    root_agent = Agent(
        name="root_agent",
        model="gemini-2.5-flash",
        instruction="""
        You are the Policy Pulse supervisor agent.
        
        FILE SAVING CAPABILITY:
        When users request a policy document or want to save content as a file:
        1. Generate the content with proper formatting
        2. Call write_file with:
           - filename: descriptive name with extension (.md, .txt, .docx)
           - content: the generated content
        3. Inform user with file path and size
        
        EXAMPLE:
        User: "Create a maternity policy and save it"
        You:
          1. Generate policy content
          2. Call write_file("maternity_policy.docx", content)
          3. Respond: "✅ Policy saved as maternity_policy.docx at [path]"
        """,
        tools=[
            FAQ_tool,
            ReportWriting_tool,
            write_file  # ← Universal file writer
        ]
    )
    
    return root_agent


# =============================================================================
# EXAMPLE 2: Add All File Tools (Maximum Flexibility)
# =============================================================================

def example_2_all_tools():
    """Give agent access to all file writing tools"""
    
    ENHANCED_INSTRUCTION = """
    You are the Policy Pulse supervisor agent.
    
    FILE WRITING TOOLS:
    You have multiple file writing tools:
    
    1. write_markdown_file(filename, content)
       - Use for: Documentation, READMEs, technical content
       - Format: Markdown with #headings, **bold**, *italic*
       - Extension: .md
    
    2. write_text_file(filename, content)
       - Use for: Simple text, logs, quick references
       - Format: Plain text, no formatting
       - Extension: .txt
    
    3. write_word_document(filename, content)
       - Use for: Corporate policies, formal documents
       - Format: Converts markdown → Word formatting
       - Extension: .docx
       - Note: Requires python-docx installed
    
    4. write_file(filename, content)
       - Universal tool - auto-detects from extension
       - Use when user specifies format or extension
    
    DECISION LOGIC:
    - User wants "Word document" → use write_word_document
    - User wants "markdown" → use write_markdown_file
    - User wants "text file" → use write_text_file
    - User says "save as file" (no format) → use write_word_document (default)
    - User provides filename with extension → use write_file
    
    Always confirm file creation with path and size!
    """
    
    root_agent = Agent(
        name="root_agent",
        model="gemini-2.5-flash",
        instruction=ENHANCED_INSTRUCTION,
        tools=[
            FAQ_tool,
            ReportWriting_tool,
            write_markdown_file,
            write_text_file,
            write_word_document,
            write_file
        ]
    )
    
    return root_agent


# =============================================================================
# EXAMPLE 3: Add to ReportWriting Agent (Specialized)
# =============================================================================

def example_3_specialized():
    """Add file writing directly to ReportWriting agent"""
    
    ReportWriting_agent_enhanced = Agent(
        name="ReportWriting_agent",
        model="gemini-2.5-flash",
        instruction="""
        You are a policy document writer.
        
        WORKFLOW:
        1. Generate policy content based on template
        2. AUTOMATICALLY save as Word document using write_word_document
        3. Return confirmation with file details
        
        IMPORTANT:
        After generating EVERY policy, call write_word_document with:
        - filename: descriptive name based on policy type and date
        - content: the generated policy
        
        Example filename: "maternity_policy_2025_01.docx"
        """,
        tools=[
            write_word_document,  # Automatically save policies
            calculate_word_count  # Check word counts
        ]
    )
    
    return ReportWriting_agent_enhanced


# =============================================================================
# EXAMPLE 4: Conversation Flow with File Writing
# =============================================================================

async def example_4_conversation_flow():
    """Example conversation demonstrating file writing"""
    
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
    
    # Setup
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    
    agent = example_1_simple()  # Agent with write_file tool
    
    runner = Runner(
        session_service=session_service,
        artifact_service=artifact_service,
        app_name="policy_pulse_test",
        agent=agent
    )
    
    # Simulate conversation
    print("=" * 60)
    print("EXAMPLE CONVERSATION WITH FILE WRITING")
    print("=" * 60)
    
    # Message 1: User requests policy
    message1 = types.Content(
        role='user',
        parts=[types.Part(text="Create a brief maternity policy and save it as a Word document")]
    )
    
    print("\n🤔 User: Create a brief maternity policy and save it as a Word document\n")
    print("🤖 Agent:")
    
    async for event in runner.run_async(
        user_id="test_user",
        session_id="test_session",
        new_message=message1
    ):
        if hasattr(event, 'content') and hasattr(event.content, 'parts'):
            for part in event.content.parts:
                if hasattr(part, 'text'):
                    print(f"   {part.text}")
    
    print("\n✅ File should be created in output/ directory")


# =============================================================================
# EXAMPLE 5: Custom Instruction for File Naming
# =============================================================================

FILE_NAMING_INSTRUCTION = """
FILE NAMING CONVENTIONS:
When saving files, use this format:

For policies:
- {policy_type}_policy_{date}.docx
- Example: "maternity_policy_2025_01_26.docx"

For quick references:
- {policy_type}_quick_ref.txt
- Example: "fertility_quick_ref.txt"

For documentation:
- {topic}_guide.md
- Example: "compliance_guide.md"

Always use:
- Lowercase with underscores
- Descriptive names
- Include date for versioning
- Appropriate extension (.md, .txt, .docx)

EXAMPLES:
✅ "maternity_policy_2025_01.docx"
✅ "fertility_benefits_guide.md"
✅ "policy_summary.txt"

❌ "Policy#1!.docx" (special chars)
❌ "doc.docx" (not descriptive)
❌ "POLICY.DOCX" (all caps)
"""


# =============================================================================
# EXAMPLE 6: Error Handling Pattern
# =============================================================================

def example_6_error_handling():
    """Show how agent should handle file writing errors"""
    
    INSTRUCTION_WITH_ERROR_HANDLING = """
    When calling file writing tools:
    
    1. Call the tool (e.g., write_file)
    2. Check the result status
    3. Handle success and errors appropriately
    
    RESPONSE PATTERNS:
    
    If status == "success":
    ✅ "I've saved your policy!
    - File: {filename}
    - Location: {file_path}
    - Size: {file_size_bytes} bytes
    You can now download this file."
    
    If error contains "python-docx":
    ⚠️  "I can create the policy but Word documents require python-docx.
    I'll save it as markdown instead."
    [Then call write_markdown_file]
    
    If error contains "Permission denied":
    ❌ "Unable to save the file - it may be open in another program.
    Please close it and try again."
    
    Always provide helpful error messages!
    """
    
    return INSTRUCTION_WITH_ERROR_HANDLING


# =============================================================================
# EXAMPLE 7: Complete Integration in agent.py
# =============================================================================

# This is what you would add to your actual agent.py file:

"""
In agent.py, add these imports:

from agents.policy_pulse_agent.tools import (
    write_file,
    write_markdown_file,
    write_word_document
)

Then modify root_agent:

root_agent = Agent(
    name="root_agent",
    model=model,
    instruction=INSTRUCTION + FILE_NAMING_INSTRUCTION,  # Add file naming guidance
    tools=[
        FAQ_tool,
        ReportWriting_tool,
        write_file  # Add file writing capability
    ]
)

That's it! Agent can now write files.
"""


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

if __name__ == "__main__":
    print("File Writing Tool Integration Examples\n")
    
    print("Example 1: Simple Integration")
    print("-" * 50)
    agent1 = example_1_simple()
    print(f"✅ Created agent with {len(agent1.tools)} tools")
    print(f"   Tools: {[tool.__name__ if hasattr(tool, '__name__') else str(tool) for tool in agent1.tools]}\n")
    
    print("Example 2: All File Tools")
    print("-" * 50)
    agent2 = example_2_all_tools()
    print(f"✅ Created agent with {len(agent2.tools)} tools")
    print("   Includes all file writing tools\n")
    
    print("Example 3: Specialized Agent")
    print("-" * 50)
    agent3 = example_3_specialized()
    print(f"✅ Created specialized agent")
    print("   Auto-saves policies as Word documents\n")
    
    print("Example 6: Error Handling")
    print("-" * 50)
    instruction = example_6_error_handling()
    print("✅ Error handling instruction created")
    print("   Includes success/error response patterns\n")
    
    print("=" * 50)
    print("To run conversation example:")
    print("  import asyncio")
    print("  asyncio.run(example_4_conversation_flow())")
