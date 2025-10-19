# Create new file: front-end/dynamic_sections.py
# =============================================================================
# DYNAMIC TEMPLATE GENERATION
# =============================================================================
# PURPOSE: Convert questionnaire answers into structured document template
# KEY CONCEPT: Template drives content generation (not LLM hallucination)


def generate_dynamic_template(responses):
    """
    Generate document template from user's questionnaire responses
    
    INPUT: questionnaire_data dict containing:
    - document_type: "policy", "guidelines", or "guide"
    - topics: List of areas to cover (e.g., ["maternity", "fertility"])
    - compliance: Regulatory requirements (e.g., ["UK", "GDPR"])
    - word_count: Target length (e.g., 3000)
    - company_context: Optional existing policy text
    
    OUTPUT: Structured template with:
    - Section hierarchy (headings, subheadings)
    - Word count targets per section
    - Required vs optional sections
    - Compliance checkpoints
    
    WHY TEMPLATES MATTER:
    - Consistency: Every policy has same structure
    - Completeness: No missing sections
    - Guidance: Agent knows what to write
    - Quality: Structured output, not rambling
    
    SECTION GENERATION LOGIC:
    1. Map topics to standard sections (e.g., "maternity" → "Maternity Leave Policy")
    2. Allocate word count proportionally
    3. Add compliance requirements as subsections
    4. Mark required vs optional based on best practices
    
    EXAMPLE TEMPLATE:
    {
      "sections": [
        {
          "title": "1. Introduction",
          "word_count": 200,
          "required": true,
          "prompts": ["State purpose", "Define scope"]
        },
        {
          "title": "2. Maternity Leave",
          "word_count": 800,
          "required": true,
          "subsections": [
            {
              "title": "2.1 Eligibility",
              "word_count": 200,
              "compliance": ["UK statutory requirements"]
            }
          ]
        }
      ]
    }
    
    DESIGN PRINCIPLES:
    - Top-down: Start with high-level structure
    - Proportional: Distribute word count based on importance
    - Flexible: Allow agent creativity within structure
    - Complete: Cover all user-requested topics
    """
    
    doc_type = responses.get('document_type', 'policy')
    focus = responses.get('policy_focus', 'comprehensive')
    detail_level = responses.get('detail_level', 'standard')
    selected_areas = responses.get('coverage_areas', [])
    
    # Base sections (always included)
    base_sections = [
        {
            "title": "Purpose and Objectives",
            "description": f"Explain the purpose of this {doc_type} and key objectives",
            "minWords": 100, "maxWords": 200, "required": True
        },
        {
            "title": "Scope and Applicability", 
            "description": "Define who this applies to and in what circumstances",
            "minWords": 80, "maxWords": 150, "required": True
        }
    ]
    
    # Generate content sections based on focus and selected areas
    content_sections = []
    
    if 'fertility_support' in selected_areas:
        content_sections.extend([
            {
                "title": "Fertility Treatment Support",
                "description": "Coverage for IVF, fertility assessments, and related treatments",
                "minWords": 150, "maxWords": 300, "required": True
            },
            {
                "title": "Time Off for Fertility Treatment",
                "description": "Policies for appointments and treatment time off",
                "minWords": 100, "maxWords": 200, "required": True
            }
        ])
    
    if 'pregnancy_maternity' in selected_areas:
        content_sections.extend([
            {
                "title": "Pregnancy and Maternity Support",
                "description": "Support during pregnancy, maternity leave, and return to work",
                "minWords": 200, "maxWords": 400, "required": True
            }
        ])
    
    if 'miscarriage_bereavement' in selected_areas:
        content_sections.extend([
            {
                "title": "Pregnancy Loss and Bereavement Support",
                "description": "Support for miscarriage, stillbirth, and pregnancy loss",
                "minWords": 150, "maxWords": 300, "required": True
            }
        ])
    
    if 'menopause' in selected_areas:
        content_sections.append({
            "title": "Menopause Support",
            "description": "Workplace adjustments and support for menopause",
            "minWords": 120, "maxWords": 250, "required": True
        })
    
    if 'parental_leave' in selected_areas:
        content_sections.append({
            "title": "Parental Leave (All Genders)",
            "description": "Leave entitlements for all parents regardless of gender",
            "minWords": 150, "maxWords": 300, "required": True
        })
    
    # Closing sections (always included)
    closing_sections = [
        {
            "title": "Legal and Regulatory Compliance",
            "description": "Reference to UK employment law and regulatory requirements",
            "minWords": 100, "maxWords": 200, "required": True
        },
        {
            "title": "Employee Support and Resources",
            "description": "Available support services and how to access them",
            "minWords": 80, "maxWords": 150, "required": True
        },
        {
            "title": "Review and Updates",
            "description": "How and when this policy will be reviewed",
            "minWords": 50, "maxWords": 100, "required": True
        }
    ]
    
    # Adjust word counts based on detail level
    multiplier = {"brief": 0.7, "standard": 1.0, "comprehensive": 1.5}[detail_level]
    
    all_sections = base_sections + content_sections + closing_sections
    
    for section in all_sections:
        section["minWords"] = int(section["minWords"] * multiplier)
        section["maxWords"] = int(section["maxWords"] * multiplier)
    
    return {
        "policyTitle": {
    "text": f"WORKPLACE {focus.replace('_', ' ').upper()} {doc_type.upper()}",
    "formatting": ["capitalized", "underlined"]
},
        "policyVersion": f"v1.0 – {responses.get('created_date', 'Draft')}",
        "sections": all_sections
    }