# File Writing Tools - Complete Guide

## Overview

Your Policy Pulse agent can now **write files directly** using these new tools:

- **`write_markdown_file`** - Create formatted markdown documents (.md)
- **`write_text_file`** - Create plain text files (.txt)
- **`write_word_document`** - Create Word documents (.docx) with formatting
- **`write_file`** - Universal tool that auto-detects file type

## Why These Tools Are Useful

### For Policy Pulse Agent:
- ✅ Generate policy documents as downloadable files
- ✅ Create formatted reports for users
- ✅ Save research outputs
- ✅ Export FAQ responses as documents
- ✅ Produce Word documents ready for editing

### Benefits:
- Users get **downloadable files**, not just chat responses
- Files are **properly formatted** with headings, lists, bold/italic
- Supports **Word format** for easy corporate use
- **Automatic markdown conversion** to Word formatting

---

## Tool 1: write_markdown_file

### Description
Creates a markdown file with your content. Perfect for policies and documentation.

### Function Signature
```python
write_markdown_file(
    filename: str,           # Name of file (auto-adds .md)
    content: str,            # Markdown content
    output_dir: str = "output"  # Where to save (default: "output/")
) -> dict
```

### Example Usage

#### In Your Agent
```python
from agents.policy_pulse_agent.tools import write_markdown_file

root_agent = Agent(
    name="root_agent",
    tools=[
        FAQ_tool,
        ReportWriting_tool,
        write_markdown_file  # Add file writing capability
    ]
)
```

#### Agent Instruction
```python
instruction = """
When user requests a policy document:
1. Generate the policy content with markdown formatting
2. Call write_markdown_file with:
   - filename: "company_maternity_policy.md"
   - content: [the generated policy]
3. Inform user the file has been saved
"""
```

#### Sample Content
```python
content = """# Maternity Leave Policy

## Introduction
This policy outlines our maternity leave benefits.

## Eligibility
- 26 weeks continuous service
- Notification required 15 weeks before due date

## Leave Duration
**52 weeks** total leave available:
- 26 weeks Ordinary Maternity Leave
- 26 weeks Additional Maternity Leave

## Contact
Email: hr@company.com
"""

result = write_markdown_file("maternity_policy.md", content)
# Returns: {
#   "status": "success",
#   "file_path": "E:/Work/policy_pulse_app_g_adk/output/maternity_policy.md",
#   "file_size_bytes": 512,
#   "message": "Markdown file written successfully: maternity_policy.md"
# }
```

### What Agent Sees
```
User: "Can you create a maternity policy and save it as a file?"

Agent: "I'll generate a comprehensive maternity policy for you..."
[Generates policy content]
[Calls write_markdown_file]

Agent: "✅ I've created your maternity policy! 
The file has been saved as: output/maternity_policy.md
File size: 512 bytes

You can now download and use this policy document."
```

---

## Tool 2: write_text_file

### Description
Creates a plain text file. Good for simple outputs, logs, or data.

### Function Signature
```python
write_text_file(
    filename: str,
    content: str,
    output_dir: str = "output"
) -> dict
```

### Example Usage
```python
content = """Quick Reference - Maternity Leave

Eligibility: 26 weeks service
Duration: 52 weeks
Pay: SMP for 39 weeks
Notice: 8 weeks before return

Contact: hr@company.com
"""

result = write_text_file("maternity_quick_ref.txt", content)
```

### Use Cases
- Quick reference guides
- Data exports
- Log files
- Simple checklists

---

## Tool 3: write_word_document

### Description
Creates a Word document (.docx) with automatic formatting from markdown syntax.

### Function Signature
```python
write_word_document(
    filename: str,
    content: str,
    output_dir: str = "output",
    include_formatting: bool = True  # Apply markdown→Word conversion
) -> dict
```

### Supported Formatting

| Markdown Syntax | Word Output |
|----------------|-------------|
| `# Heading` | Heading 1 style |
| `## Heading` | Heading 2 style |
| `### Heading` | Heading 3 style |
| `**bold text**` | **Bold text** |
| `*italic text*` | *Italic text* |
| `- bullet` | • Bullet list |
| `1. numbered` | 1. Numbered list |

### Example Usage
```python
content = """# Fertility Support Policy

## Overview
This policy provides **comprehensive support** for employees undergoing fertility treatment.

## Benefits
- IVF coverage up to *£10,000* per year
- 4 days paid leave for appointments
- Counseling services

## Eligibility
To qualify, you must:
1. Have 12 months service
2. Provide medical documentation
3. Complete application form

## Contact
Email: fertility@company.com
"""

result = write_word_document("fertility_policy.docx", content)
```

### Output
Creates a properly formatted Word document with:
- ✅ Heading 1: "Fertility Support Policy"
- ✅ Heading 2: "Overview", "Benefits", etc.
- ✅ Bold text: "comprehensive support"
- ✅ Italic text: "£10,000"
- ✅ Bullet lists properly formatted
- ✅ Numbered lists properly formatted

### Requirements
```bash
pip install python-docx
```

If not installed, the tool returns:
```python
{
    "status": "error",
    "error": "python-docx not installed. Run: pip install python-docx"
}
```

---

## Tool 4: write_file (Universal)

### Description
Smart tool that auto-detects file type from extension. One tool for all formats!

### Function Signature
```python
write_file(
    filename: str,           # With extension (.md, .txt, .docx)
    content: str,
    output_dir: str = "output",
    file_type: Optional[str] = None  # Override auto-detection
) -> dict
```

### Example Usage

#### Auto-detect from extension
```python
# Automatically creates markdown
write_file("policy.md", "# My Policy\n...")

# Automatically creates text
write_file("notes.txt", "Some notes...")

# Automatically creates Word doc
write_file("report.docx", "# Report\n...")
```

#### Explicit type override
```python
# Force markdown even without extension
write_file("policy", "# Content", file_type="markdown")
```

### Detection Logic
- `.md` → markdown
- `.txt` → text
- `.docx` → word
- No extension + no file_type → text (default)

---

## Integration with Agent

### Method 1: Add to Root Agent
```python
# In agent.py
from agents.policy_pulse_agent.tools import write_file

root_agent = Agent(
    name="root_agent",
    tools=[
        FAQ_tool,
        ReportWriting_tool,
        write_file  # Universal file writer
    ],
    instruction="""
    When user requests a policy document:
    1. Generate the content
    2. Call write_file with appropriate filename
    3. Confirm file has been saved with path
    """
)
```

### Method 2: Add to ReportWriting Agent
```python
# In ReportWriting_agent/__init__.py
from agents.policy_pulse_agent.tools import write_word_document

ReportWriting_agent = Agent(
    name="ReportWriting_agent",
    tools=[
        write_word_document,  # Can write Word docs
        calculate_word_count
    ],
    instruction="""
    After generating a policy:
    1. Call write_word_document to save as .docx
    2. Inform user of the file location
    """
)
```

### Method 3: Multiple File Tools
```python
root_agent = Agent(
    name="root_agent",
    tools=[
        write_markdown_file,  # For markdown
        write_word_document,  # For Word
        write_text_file       # For plain text
    ],
    instruction="""
    You can save files in different formats:
    - Use write_markdown_file for .md files
    - Use write_word_document for .docx files
    - Use write_text_file for .txt files
    
    Choose the format based on user preference.
    """
)
```

---

## Complete Example: Policy Generation Workflow

### User Request
```
User: "Create a comprehensive maternity policy and save it as a Word document"
```

### Agent Workflow
```python
# 1. Agent generates policy content
policy_content = """# Maternity Leave Policy

## Introduction
[Generated content...]

## Eligibility
[Generated content...]
"""

# 2. Agent calls write_word_document
result = write_word_document(
    filename="maternity_policy.docx",
    content=policy_content,
    output_dir="output"
)

# 3. Agent responds to user
if result["status"] == "success":
    response = f"""
    ✅ I've created your maternity policy!
    
    **File Details:**
    - Format: Word Document (.docx)
    - Location: {result['file_path']}
    - Size: {result['file_size_bytes']} bytes
    
    The document includes:
    - Formatted headings
    - Bold and italic text
    - Bullet and numbered lists
    
    You can now download and edit this policy in Microsoft Word.
    """
```

---

## Advanced Features

### Custom Output Directories
```python
# Save to specific folder
write_file(
    "policy.md",
    content,
    output_dir="policies/2025/maternity"
)
# Creates: policies/2025/maternity/policy.md
# (directories created automatically)
```

### Error Handling
```python
result = write_file("policy.md", content)

if result["status"] == "success":
    print(f"✅ File saved: {result['file_path']}")
else:
    print(f"❌ Error: {result['error']}")
```

### Check File Size
```python
result = write_word_document("policy.docx", content)

if result["file_size_bytes"] > 1000000:  # 1 MB
    print("⚠️  Large file generated")
```

---

## Testing the Tools

### Quick Test (Python REPL)
```python
from agents.policy_pulse_agent.tools import write_file

# Test markdown
result = write_file("test.md", "# Test\n\nThis works!")
print(result)

# Test text
result = write_file("test.txt", "Simple text file")
print(result)

# Test Word (requires python-docx)
result = write_file("test.docx", "# Test\n\n**Bold** and *italic*")
print(result)
```

### Full Test Script
```bash
python test_file_writing_tools.py
```

This will:
- Create sample markdown files
- Create sample text files
- Create sample Word documents
- Test different output directories
- List all generated files

---

## Common Use Cases for Policy Pulse

### 1. Save Generated Policy
```python
# After ReportWriting_agent generates policy
write_word_document(
    filename=f"{policy_type}_policy_{date}.docx",
    content=generated_policy
)
```

### 2. Export FAQ Responses
```python
# Save FAQ answer as markdown
write_markdown_file(
    filename="faq_maternity_leave.md",
    content=faq_response
)
```

### 3. Create Quick Reference
```python
# Save summary as text
write_text_file(
    filename="policy_summary.txt",
    content=policy_summary
)
```

### 4. Batch Export Multiple Policies
```python
for policy_type in ["maternity", "fertility", "menopause"]:
    content = generate_policy(policy_type)
    write_word_document(
        filename=f"{policy_type}_policy.docx",
        content=content,
        output_dir=f"output/policies/{year}"
    )
```

---

## Troubleshooting

### Issue: "python-docx not installed"
**Solution:**
```bash
pip install python-docx
```

### Issue: "Permission denied"
**Solution:** Check if file is open in another program (Word, text editor)

### Issue: "Directory not found"
**Solution:** The tool auto-creates directories, but check parent folder permissions

### Issue: Files not appearing
**Solution:** Check the output directory (default: `./output/`)

---

## Best Practices

### ✅ DO:
- Use descriptive filenames: `maternity_policy_2025.docx`
- Include dates in filenames for versioning
- Use Word format for corporate policies (easier to edit)
- Use markdown for technical documentation
- Check result status before confirming to user

### ❌ DON'T:
- Use special characters in filenames: `policy#1!.docx` ❌
- Overwrite important files without confirmation
- Generate very large files (>10MB) without warning
- Assume file was created without checking result

---

## Summary

### Quick Reference

| Tool | File Type | Best For | Formatting |
|------|-----------|----------|------------|
| `write_markdown_file` | .md | Docs, READMEs | Markdown |
| `write_text_file` | .txt | Simple text | None |
| `write_word_document` | .docx | Corporate policies | MD→Word |
| `write_file` | Auto | Any of above | Auto |

### Installation
```bash
# Required for Word documents
pip install python-docx
```

### Import in agent.py
```python
from agents.policy_pulse_agent.tools import (
    write_file,              # Universal (recommended)
    write_markdown_file,     # Markdown specific
    write_text_file,         # Text specific
    write_word_document      # Word specific
)
```

### Add to Agent
```python
root_agent = Agent(
    name="root_agent",
    tools=[FAQ_tool, ReportWriting_tool, write_file]
)
```

### Agent Uses Automatically
When user says "save as a file" or "create a document", the agent will automatically call the appropriate tool!

---

## Next Steps

1. ✅ **Test the tools:** Run `test_file_writing_tools.py`
2. ✅ **Add to your agent:** Import and add to tools list
3. ✅ **Update instructions:** Tell agent when to save files
4. ✅ **Test with real queries:** Try "Create a policy and save as Word doc"

**Your agent can now create downloadable policy documents! 🎉**
