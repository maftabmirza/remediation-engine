"""
Vision AI Service
Analyzes architecture diagrams and flowcharts using Claude Vision
"""
import logging
import base64
from typing import Optional, Dict, Any, List
from pathlib import Path
import os

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

logger = logging.getLogger(__name__)


class VisionAIService:
    """Service for analyzing diagrams using Claude Vision API."""
    
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        self.model = os.getenv('VISION_MODEL', 'claude-3-haiku-20240307')
        
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not set - Vision AI will not work")
        
        if Anthropic is None:
            logger.warning("Anthropic library not available")
        
        self.client = Anthropic(api_key=self.api_key) if self.api_key and Anthropic else None
    
    def is_configured(self) -> bool:
        """Check if Vision AI is properly configured."""
        return self.client is not None
    
    def analyze_diagram(
        self, 
        image_path: str,
        image_type: str = 'architecture'
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze an architecture diagram or flowchart.
        
        Args:
            image_path: Path to image file or file-like object
            image_type: Type of diagram (architecture, flowchart, sequence, etc.)
            
        Returns:
            Dictionary with extracted information or None if analysis fails
        """
        if not self.is_configured():
            logger.error("Vision AI not configured")
            return None
        
        try:
            # Read and encode image
            image_data = self._read_image(image_path)
            if not image_data:
                return None
            
            # Get appropriate prompt for diagram type
            prompt = self._get_analysis_prompt(image_type)
            
            # Call Claude Vision API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_data['media_type'],
                                "data": image_data['data']
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )
            
            # Extract response text
            response_text = response.content[0].text
            
            # Parse the structured response
            return self._parse_analysis(response_text, image_type)
            
        except Exception as e:
            logger.error(f"Vision AI analysis failed: {e}")
            return None
    
    def _read_image(self, image_path: str) -> Optional[Dict[str, str]]:
        """Read and encode image to base64."""
        try:
            # Handle both file paths and file-like objects
            if isinstance(image_path, str):
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()
                # Detect media type from extension
                ext = Path(image_path).suffix.lower()
            else:
                image_bytes = image_path.read()
                # Try to get extension from filename attribute
                ext = getattr(image_path, 'name', '').split('.')[-1].lower()
            
            media_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            
            media_type = media_type_map.get(f'.{ext}' if not ext.startswith('.') else ext, 'image/jpeg')
            
            return {
                'data': base64.b64encode(image_bytes).decode('utf-8'),
                'media_type': media_type
            }
        except Exception as e:
            logger.error(f"Failed to read image: {e}")
            return None
    
    def _get_analysis_prompt(self, image_type: str) -> str:
        """Get the appropriate analysis prompt for the diagram type."""
        
        base_prompt = """Analyze this {type} diagram and extract detailed technical information.

Please provide:

1. **Components**: List all services, databases, queues, APIs, and systems shown
   - For each: name, type, description, technology (if visible)

2. **Connections**: Identify all data flows, API calls, and integrations
   - For each: from component, to component, connection type, protocol (if visible)

3. **Failure Scenarios**: Infer potential failure points and their impacts
   - For each: which component, what could fail, impact on system

4. **Dependencies**: Note critical dependencies and single points of failure

5. **Text Content**: Extract any visible text, labels, or annotations

Format your response as a detailed technical description that can be used for documentation and troubleshooting. Be specific about component names and relationships."""
        
        type_specific = {
            'architecture': "system architecture",
            'flowchart': "process flowchart",
            'sequence': "sequence diagram",
            'erd': "entity relationship diagram",
            'network': "network diagram",
            'deployment': "deployment diagram",
            'component': "component diagram"
        }
        
        diagram_name = type_specific.get(image_type, "technical diagram")
        return base_prompt.format(type=diagram_name)
    
    def _parse_analysis(self, response_text: str, image_type: str) -> Dict[str, Any]:
        """
        Parse the Claude response into structured data.
        
        Args:
            response_text: Raw response from Claude
            image_type: Type of diagram
            
        Returns:
            Structured analysis data
        """
        # For now, store the full text response
        # In the future, we could add more sophisticated parsing
        # to extract structured JSON from the response
        
        analysis = {
            'description': response_text,
            'image_type': image_type,
            'raw_response': response_text,
            'extracted_components': [],  # TODO: Parse components
            'identified_connections': [],  # TODO: Parse connections
            'failure_scenarios': []  # TODO: Parse scenarios
        }
        
        # Simple extraction of components (basic parsing)
        # Look for numbered lists or bullet points
        lines = response_text.split('\n')
        current_section = None
        
        for line in lines:
            line_lower = line.lower().strip()
            if 'component' in line_lower:
                current_section = 'components'
            elif 'connection' in line_lower or 'flow' in line_lower:
                current_section = 'connections'
            elif 'failure' in line_lower or 'scenario' in line_lower:
                current_section = 'failures'
        
        return analysis
    
    def generate_searchable_text(self, analysis: Dict[str, Any]) -> str:
        """
        Generate searchable text from analysis results.
        
        Args:
            analysis: Analysis dictionary
            
        Returns:
            Searchable text for chunking and embedding
        """
        parts = []
        
        # Add description
        if analysis.get('description'):
            parts.append(analysis['description'])
        
        # Add component info
        if analysis.get('extracted_components'):
            parts.append("\n## Components\n")
            for comp in analysis['extracted_components']:
                parts.append(f"- {comp.get('name', 'Unknown')}: {comp.get('description', '')}")
        
        # Add connections
        if analysis.get('identified_connections'):
            parts.append("\n## Connections\n")
            for conn in analysis['identified_connections']:
                parts.append(f"- {conn.get('from', '')} → {conn.get('to', '')}: {conn.get('type', '')}")
        
        # Add failure scenarios
        if analysis.get('failure_scenarios'):
            parts.append("\n## Potential Failure Scenarios\n")
            for scenario in analysis['failure_scenarios']:
                parts.append(f"- {scenario.get('component', '')}: {scenario.get('scenario', '')}")
        
        return '\n'.join(parts)
