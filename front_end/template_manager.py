# Create new file: front-end/template_manager.py
# =============================================================================
# POLICY TEMPLATE MANAGEMENT
# =============================================================================
# PURPOSE: Generate and manage dynamic policy document templates
# WHY DYNAMIC?: Each user request is unique (different topics, length, focus)

import json
import os
from datetime import datetime
from pathlib import Path

class PolicyTemplateManager:
    """
    Manages policy template lifecycle (create, store, retrieve)
    
    DESIGN PATTERN: Manager class for template CRUD operations
    - Create: Generate template from questionnaire
    - Store: Save template to filesystem/database
    - Retrieve: Load template for document generation
    - Update: Modify template based on user feedback
    
    WHY NOT DATABASE?:
    - Templates are large JSON structures
    - Not frequently queried or searched
    - Filesystem is simpler for development
    - Can migrate to DB later if needed
    
    TEMPLATE STRUCTURE:
    {
      "document_type": "policy|guidelines|guide",
      "topics": ["maternity", "paternity", "fertility"],
      "sections": [
        {
          "title": "Maternity Leave",
          "required": true,
          "word_count_target": 500,
          "subsections": [...]
        }
      ],
      "compliance_requirements": ["UK", "GDPR"],
      "total_word_count": 3000
    }
    
    LIFECYCLE:
    1. User completes questionnaire
    2. generate_dynamic_template() creates structure
    3. save_template() persists to disk
    4. ReportWriting_agent loads and fills sections
    5. Root agent reviews final output
    """

    def __init__(self, templates_dir="policy_templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(exist_ok=True)
    
    def generate_template_name(self, responses):
        """Auto-generate template name based on responses"""
        doc_type = responses.get('document_type', 'policy')
        focus = responses.get('policy_focus', 'general')
        length = responses.get('detail_level', 'standard')
        
        # Clean and format
        focus_clean = focus.replace('/', '_').replace(' ', '_').lower()
        name = f"{focus_clean}_{doc_type}_{length}_{datetime.now().strftime('%Y%m%d')}"
        return name
    
    def save_template(self, template_name, questionnaire_responses, generated_sections):
        """Save template for future reuse"""
        template_data = {
            "name": template_name,
            "created_date": datetime.now().isoformat(),
            "questionnaire_responses": questionnaire_responses,
            "sections_structure": generated_sections,
            "metadata": {
                "document_type": questionnaire_responses.get('document_type'),
                "focus_area": questionnaire_responses.get('policy_focus'),
                "length": questionnaire_responses.get('detail_level')
            }
        }
        
        file_path = self.templates_dir / f"{template_name}.json"
        with open(file_path, 'w') as f:
            json.dump(template_data, f, indent=2)
        
        return str(file_path)
    
    def load_template(self, template_name):
        """Load existing template"""
        file_path = self.templates_dir / f"{template_name}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        return None
    
    def list_templates(self):
        """List all saved templates"""
        templates = []
        for file_path in self.templates_dir.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    template = json.load(f)
                    templates.append({
                        "name": template["name"],
                        "focus": template["metadata"]["focus_area"],
                        "type": template["metadata"]["document_type"],
                        "created": template["created_date"][:10]  # Just date
                    })
            except Exception as e:
                print(f"Error reading template {file_path}: {e}")
        
        return sorted(templates, key=lambda x: x["created"], reverse=True)