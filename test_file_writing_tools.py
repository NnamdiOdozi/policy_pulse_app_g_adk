"""
Test File Writing Tools

Demonstrates the file writing tools that agents can use to create:
- Markdown files (.md)
- Text files (.txt)
- Word documents (.docx)

Usage:
    python test_file_writing_tools.py
"""

import sys
import os

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from agents.policy_pulse_agent.tools import (
    write_markdown_file,
    write_text_file,
    write_word_document,
    write_file
)


def test_markdown_file():
    """Test writing a markdown file"""
    print("=" * 60)
    print("TEST 1: write_markdown_file")
    print("=" * 60)
    
    markdown_content = """# Maternity Leave Policy

## Introduction

This policy outlines our commitment to supporting employees during pregnancy and maternity leave.

## Eligibility

All employees who have been with the company for at least **26 weeks** are eligible for maternity leave.

### Key Requirements:
- 26 weeks continuous service
- Notification 15 weeks before due date
- Form MAT B1 submitted

## Leave Duration

Employees are entitled to:
- **52 weeks** total maternity leave
- 26 weeks Ordinary Maternity Leave (OML)
- 26 weeks Additional Maternity Leave (AML)

## Pay and Benefits

During maternity leave, you will receive:

1. Statutory Maternity Pay (SMP) for 39 weeks
2. Company-enhanced pay for first 12 weeks
3. Continued benefits throughout leave period

## Return to Work

- Provide *8 weeks notice* of return date
- Flexible return options available
- Phased return program offered

## Contact

For questions, contact:
- HR Department: hr@company.com
- Phone: 0800-123-4567

## References

[DOC 1] Gov.UK (2024). Maternity Leave Regulations
[DOC 2] ACAS (2024). Pregnancy at Work Guide
"""
    
    print("\n📝 Writing markdown file...")
    result = write_markdown_file(
        filename="test_maternity_policy.md",
        content=markdown_content
    )
    
    if result["status"] == "success":
        print(f"✅ {result['message']}")
        print(f"   Path: {result['file_path']}")
        print(f"   Size: {result['file_size_bytes']} bytes")
    else:
        print(f"❌ Error: {result['error']}")


def test_text_file():
    """Test writing a text file"""
    print("\n" + "=" * 60)
    print("TEST 2: write_text_file")
    print("=" * 60)
    
    text_content = """Policy Pulse - Maternity Leave Quick Reference

Eligibility: 26 weeks continuous service
Leave Duration: 52 weeks total (26 OML + 26 AML)
Pay: SMP for 39 weeks + company enhancement for 12 weeks
Notice: 8 weeks before return

Contact: hr@company.com | 0800-123-4567

Generated: 2025-01-26
Version: 1.0
"""
    
    print("\n📄 Writing text file...")
    result = write_text_file(
        filename="test_maternity_quick_ref.txt",
        content=text_content
    )
    
    if result["status"] == "success":
        print(f"✅ {result['message']}")
        print(f"   Path: {result['file_path']}")
        print(f"   Size: {result['file_size_bytes']} bytes")
    else:
        print(f"❌ Error: {result['error']}")


def test_word_document():
    """Test writing a Word document"""
    print("\n" + "=" * 60)
    print("TEST 3: write_word_document")
    print("=" * 60)
    
    word_content = """# Fertility Support Policy

## Overview

This policy demonstrates our commitment to supporting employees through their fertility journey.

## Coverage

Our fertility benefits include:

- IVF treatment coverage
- Fertility preservation services
- Consultations and assessments
- Mental health support

## Financial Support

Employees receive:

1. **Up to £10,000** per year for fertility treatments
2. **4 additional days** of paid leave for appointments
3. **Counseling services** at no cost

## Eligibility

To be eligible, you must:

- Have 12 months continuous service
- Be actively trying to conceive
- Provide medical documentation

## Confidentiality

All fertility-related information is:

- Kept strictly *confidential*
- Stored securely in HR systems
- Only shared with your *explicit consent*

## How to Apply

1. Contact HR to schedule initial consultation
2. Complete fertility support application form
3. Submit required medical documentation
4. Await approval (typically 5-7 days)

## Support Resources

- Fertility Network UK: www.fertilitynetworkuk.org
- Counseling Hotline: 0800-XXX-XXXX
- HR Support: fertility@company.com

## References

[DOC 1] ACAS (2024). Fertility Treatment at Work Guide
[DOC 2] Fertility Network UK (2024). Workplace Support Standards
"""
    
    print("\n📄 Writing Word document...")
    result = write_word_document(
        filename="test_fertility_policy.docx",
        content=word_content,
        include_formatting=True
    )
    
    if result["status"] == "success":
        print(f"✅ {result['message']}")
        print(f"   Path: {result['file_path']}")
        print(f"   Size: {result['file_size_bytes']} bytes")
        print(f"\n   Note: Document includes formatted headings, bold, and italic text")
    else:
        print(f"❌ Error: {result['error']}")
        if "python-docx" in result.get("error", ""):
            print(f"\n   💡 Tip: Install python-docx with: pip install python-docx")


def test_universal_write():
    """Test the universal write_file function"""
    print("\n" + "=" * 60)
    print("TEST 4: write_file (universal)")
    print("=" * 60)
    
    content = """# Test Policy

This is a test document created with the universal write_file function.

## Features

- Auto-detects file type from extension
- Supports .md, .txt, .docx
- Simple to use
"""
    
    # Test 1: Auto-detect markdown
    print("\n📝 Test 4a: Auto-detect markdown (.md)...")
    result = write_file(
        filename="test_universal.md",
        content=content
    )
    print(f"   {'✅' if result['status'] == 'success' else '❌'} {result.get('message', result.get('error'))}")
    
    # Test 2: Auto-detect text
    print("\n📄 Test 4b: Auto-detect text (.txt)...")
    result = write_file(
        filename="test_universal.txt",
        content=content
    )
    print(f"   {'✅' if result['status'] == 'success' else '❌'} {result.get('message', result.get('error'))}")
    
    # Test 3: Explicit type override
    print("\n📝 Test 4c: Explicit type override (no extension)...")
    result = write_file(
        filename="test_universal_no_ext",
        content=content,
        file_type="markdown"
    )
    print(f"   {'✅' if result['status'] == 'success' else '❌'} {result.get('message', result.get('error'))}")


def test_custom_output_dir():
    """Test writing to a custom output directory"""
    print("\n" + "=" * 60)
    print("TEST 5: Custom output directory")
    print("=" * 60)
    
    content = "# Policy in Custom Directory\n\nThis file is saved in a custom location."
    
    print("\n📁 Writing to 'test_output/policies' directory...")
    result = write_markdown_file(
        filename="custom_dir_test.md",
        content=content,
        output_dir="test_output/policies"
    )
    
    if result["status"] == "success":
        print(f"✅ {result['message']}")
        print(f"   Path: {result['file_path']}")
        print(f"   Note: Directory was created automatically")
    else:
        print(f"❌ Error: {result['error']}")


def list_generated_files():
    """List all files generated during testing"""
    print("\n" + "=" * 60)
    print("GENERATED FILES")
    print("=" * 60)
    
    output_dirs = ["output", "test_output/policies"]
    
    for dir_path in output_dirs:
        if os.path.exists(dir_path):
            print(f"\n📂 {dir_path}/")
            files = os.listdir(dir_path)
            if files:
                for file in sorted(files):
                    file_path = os.path.join(dir_path, file)
                    size = os.path.getsize(file_path)
                    print(f"   - {file} ({size} bytes)")
            else:
                print(f"   (empty)")


def run_all_tests():
    """Run all file writing tests"""
    print("\n")
    print("📝" * 30)
    print("TESTING FILE WRITING TOOLS")
    print("📝" * 30)
    
    try:
        test_markdown_file()
        test_text_file()
        test_word_document()
        test_universal_write()
        test_custom_output_dir()
        
        list_generated_files()
        
        print("\n")
        print("✅" * 30)
        print("ALL TESTS COMPLETED!")
        print("✅" * 30)
        
        print("\n💡 HOW TO USE IN YOUR AGENT:\n")
        print("from agents.policy_pulse_agent.tools import write_file\n")
        print("agent = Agent(")
        print("    name='PolicyWriter',")
        print("    tools=[write_file]  # Agent can now write files!")
        print(")\n")
        print("Agent will automatically call write_file when asked to save content.")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
