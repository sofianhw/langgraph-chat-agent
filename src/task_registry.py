import json
import os
import yaml
from typing import Dict, Any, List

class TaskRegistry:
    """A registry for managing tasks derived from OpenAPI specs and custom YAML files."""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def load_tasks(self):
        """Loads tasks from all configured sources."""
        self._load_from_openapi()
        self._load_from_custom_yaml()

    def _load_from_openapi(self):
        """Loads tasks from the OpenAPI specification."""
        spec_path = os.path.join(os.path.dirname(__file__), "..", "config", "openapi.json")
        if not os.path.exists(spec_path):
            return

        with open(spec_path, "r") as f:
            spec = json.load(f)

        for path, path_item in spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if "requestBody" in operation:
                    task_name = operation.get("summary", path.strip("/").upper())
                    schema = operation["requestBody"]["content"]["application/json"]["schema"]
                    required_fields = schema.get("required", [])
                    confirmation_fields = operation.get("x-confirmation-fields", required_fields)
                    
                    self.tasks[task_name] = {
                        "name": task_name,
                        "description": operation.get("description", ""),
                        "required_fields": required_fields,
                        "confirmation_fields": confirmation_fields,
                        "confirmation_required": True,  # Assume confirmation for API tasks
                        "endpoint": path,
                        "method": method.upper(),
                    }

    def _load_from_custom_yaml(self):
        """Loads tasks from the custom tasks.yaml file."""
        yaml_path = os.path.join(os.path.dirname(__file__), "..", "config", "tasks.yaml")
        if not os.path.exists(yaml_path):
            return

        with open(yaml_path, "r") as f:
            custom_tasks = yaml.safe_load(f)

        for task in custom_tasks.get("tasks", []):
            self.tasks[task["name"]] = task

    def get_task(self, name: str) -> Dict[str, Any]:
        """Retrieves a task by its name."""
        return self.tasks.get(name)

    def get_inquiry_types(self) -> List[Dict[str, Any]]:
        """A helper to get all defined inquiry types from the INQUIRY task."""
        inquiry_task = self.get_task("INQUIRY")
        return inquiry_task.get("inquiry_types", []) if inquiry_task else []

# Create a singleton instance of the registry
task_registry = TaskRegistry()
task_registry.load_tasks()
