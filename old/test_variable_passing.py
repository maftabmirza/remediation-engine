
import asyncio
import re
from unittest.mock import MagicMock, AsyncMock

# Mocking the simplified behavior of RunbookExecutor for verification without fuller DB setup
class MockExecutor:
    def __init__(self):
        self.runtime_vars = {}

    def _render_template(self, template_str, context):
        from jinja2 import Template
        return Template(template_str).render(**context)
    
    def process_step(self, step_name, stdout, output_variable=None, extract_pattern=None):
        print(f"Processing Step: {step_name}")
        print(f"  Output: {stdout}")
        
        # 1. Capture into steps context
        if "steps" not in self.runtime_vars:
            self.runtime_vars["steps"] = {}
        
        step_key = re.sub(r'[^a-zA-Z0-9_]', '_', step_name)
        self.runtime_vars["steps"][step_key] = {"stdout": stdout}
        
        # 2. Extract Variable
        if output_variable:
            captured = None
            if extract_pattern:
                match = re.search(extract_pattern, stdout)
                if match:
                    captured = match.group(1) if match.groups() else match.group(0)
            else:
                captured = stdout.strip()
            
            if captured:
                self.runtime_vars[output_variable] = captured
                print(f"  Captured Variable '{output_variable}': {captured}")
            else:
                print(f"  Failed to capture variable '{output_variable}'")

    def execute_next_step(self, command_template):
        context = {"vars": self.runtime_vars, **self.runtime_vars}
        rendered = self._render_template(command_template, context)
        print(f"  Rendered Command: {rendered}")
        return rendered

async def main():
    executor = MockExecutor()
    
    # Step 1: Simulate getting a PID
    print("\n--- Step 1: Get PID ---")
    step1_output = "Process ID: 9999\nStatus: Running"
    executor.process_step(
        step_name="Get PID",
        stdout=step1_output,
        output_variable="pid",
        extract_pattern=r"Process ID: (\d+)"
    )
    
    # Step 2: Use PID in command
    print("\n--- Step 2: Kill Process ---")
    command_template = "kill -9 {{ pid }}"
    rendered = executor.execute_next_step(command_template)
    
    if rendered == "kill -9 9999":
        print("\nSUCCESS: Variable passed correctly!")
    else:
        print(f"\nFAILURE: Expected 'kill -9 9999', got '{rendered}'")

    # Step 3: Test direct access via steps context (no explicit variable)
    print("\n--- Step 3: Echo Previous Output ---")
    command_template = "echo 'Previous was: {{ steps.Get_PID.stdout }}'"
    rendered = executor.execute_next_step(command_template)
    if "Process ID: 9999" in rendered:
        print("SUCCESS: Steps context access works!")
    else:
         print(f"FAILURE: Expected PID in output, got '{rendered}'")

if __name__ == "__main__":
    asyncio.run(main())
