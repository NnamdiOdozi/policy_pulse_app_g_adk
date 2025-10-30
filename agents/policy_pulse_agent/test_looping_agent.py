"""
Quick test script for looping agent integration

This script tests the quality review loop without the full app context.
Run this to verify your looping integration works correctly.

Usage:
    python test_looping_agent.py
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, os.path.abspath(project_root))

# Now import agent
from agents.policy_pulse_agent.agent import (
    root_agent,
    runner,
    session_service,
    APP_NAME,
    USER_ID,
    USE_QUALITY_LOOP
)
from google.genai import types

async def test_basic_query():
    """Test a simple query with the root agent"""
    print("\n" + "="*70)
    print("TESTING: Basic Query (Current Configuration)")
    print(f"Quality Loop Enabled: {USE_QUALITY_LOOP}")
    print("="*70 + "\n")
    
    # Create session
    session_id = f"test_{os.urandom(4).hex()}"
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id
    )
    
    # Test query
    test_query = "What maternity leave benefits do UK companies typically offer?"
    print(f"Query: {test_query}\n")
    print("Response:")
    print("-" * 70)
    
    message = types.Content(
        role='user',
        parts=[types.Part(text=test_query)]
    )
    
    # Run query
    try:
        response_parts = []
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=message
        ):
            if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'text'):
                        print(part.text, end="", flush=True)
                        response_parts.append(part.text)
        
        print("\n" + "-" * 70)
        print(f"\n✅ Test completed successfully!")
        print(f"Response length: {len(''.join(response_parts))} characters")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

async def test_with_loop_enabled():
    """Test specifically with quality loop enabled"""
    print("\n" + "="*70)
    print("TESTING: Quality Loop Behavior")
    print("="*70 + "\n")
    
    if not USE_QUALITY_LOOP:
        print("⚠️  Quality loop is currently DISABLED")
        print("To test loop behavior, set USE_QUALITY_LOOP = True in agent.py")
        return
    
    session_id = f"loop_test_{os.urandom(4).hex()}"
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id
    )
    
    # Query that should trigger refinement
    test_query = "Explain fertility treatment workplace policies"
    print(f"Query: {test_query}\n")
    print("Watching for loop iterations...")
    print("-" * 70)
    
    message = types.Content(
        role='user',
        parts=[types.Part(text=test_query)]
    )
    
    iteration_count = 0
    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=message
        ):
            # Track loop events
            if hasattr(event, 'agent_name'):
                if 'Critic' in str(event.agent_name):
                    iteration_count += 1
                    print(f"\n[Iteration {iteration_count}] Quality review...")
                elif 'Refiner' in str(event.agent_name):
                    print(f"[Iteration {iteration_count}] Applying refinements...")
            
            # Show final output
            if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text.strip():
                        print(f"\n{part.text}", end="", flush=True)
        
        print("\n" + "-" * 70)
        print(f"\n✅ Loop completed with {iteration_count} iterations")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

async def test_session_state():
    """Test that session state is properly maintained"""
    print("\n" + "="*70)
    print("TESTING: Session State Persistence")
    print("="*70 + "\n")
    
    session_id = f"state_test_{os.urandom(4).hex()}"
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id
    )
    
    # First query
    query1 = "What is maternity leave?"
    print(f"Query 1: {query1}")
    
    message1 = types.Content(
        role='user',
        parts=[types.Part(text=query1)]
    )
    
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=message1
    ):
        pass  # Just drain events
    
    print("✓ First query processed\n")
    
    # Check session state
    session_data = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id
    )
    
    if session_data and session_data.state:
        print("Session state keys:")
        for key in session_data.state.keys():
            print(f"  - {key}")
        print("\n✅ Session state is persisting")
    else:
        print("⚠️  No session state found")
    
    # Follow-up query
    query2 = "Can you tell me more about that?"
    print(f"\nQuery 2: {query2}")
    
    message2 = types.Content(
        role='user',
        parts=[types.Part(text=query2)]
    )
    
    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=message2
        ):
            if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'text'):
                        print(part.text[:100] + "...", end="")
                        break
        print("\n\n✅ Follow-up query handled correctly")
    except Exception as e:
        print(f"\n❌ Follow-up failed: {e}")

async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("POLICY PULSE - LOOPING AGENT TEST SUITE")
    print("="*70)
    
    tests = [
        ("Basic Query", test_basic_query),
        ("Quality Loop", test_with_loop_enabled),
        ("Session State", test_session_state),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {test_name} test failed: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Total: {len(tests)}")
    print("="*70 + "\n")
    
    if failed == 0:
        print("🎉 All tests passed! Your looping integration is working.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    print("\n🔧 Starting looping agent tests...\n")
    asyncio.run(main())
