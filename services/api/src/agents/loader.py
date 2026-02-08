"""
Loads and renders prompt templates from YAML files using Jinja2.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from jinja2 import Template

from src.ingestion.normalization.taxonomy_retriever import get_taxonomy_retriever

logger = logging.getLogger(__name__)


class PromptLoader:
    """
    Loads and renders prompt templates for the Event Intelligence Platform.
    Supports tiered classification and enrichment phases.
    """

    def __init__(self):
        # Base path: src/prompts/
        self.root_path = Path(__file__).parent
        self.taxonomy = get_taxonomy_retriever()

    def get_prompt(
        self, group: str, feature: str, variables: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Loads a YAML prompt and injects necessary taxonomy context.

        Args:
            group: 'classification' or 'enrichment'
            feature: The filename without extension (e.g., 'experience_pulse')
            variables: Data to render into the template (title, description, etc.)
        """
        file_path = self.root_path / group / f"{feature}.yaml"

        if not file_path.exists():
            logger.error(f"Prompt template not found: {file_path}")
            raise FileNotFoundError(f"Missing prompt: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 1. Inject Taxonomy Helpers for the Experience Pulse
        if "taxonomy_context" not in variables:
            sub_id = variables.get("subcategory_id")
            if sub_id:
                variables["taxonomy_context"] = (
                    self.taxonomy.get_subcategory_context_for_prompt(sub_id)
                )
            else:
                variables["taxonomy_context"] = (
                    self.taxonomy.get_all_categories_summary()
                )

        # 2. Inject standard allowed attribute values (energy_level, etc.)
        variables["attribute_options_string"] = (
            self.taxonomy.get_attribute_options_string()
        )

        # 3. Render Templates
        try:
            sys_tmpl = Template(config["system_prompt"])
            user_tmpl = Template(config["user_prompt"])

            return {
                "system": sys_tmpl.render(**variables),
                "user": user_tmpl.render(**variables),
            }
        except KeyError as e:
            logger.error(f"YAML missing required key in {file_path}: {e}")
            raise

    def get_all_group_prompts(
        self, variables: Dict[str, Any]
    ) -> Dict[str, Dict[str, str]]:
        """
        Helper to fetch all three primary prompts for a full enrichment pass.
        """
        return {
            "core": self.get_prompt("classification", "core_metadata", variables),
            "pulse": self.get_prompt("enrichment", "experience_pulse", variables),
            "logistics": self.get_prompt("enrichment", "logistics", variables),
        }
