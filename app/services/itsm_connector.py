"""
Generic ITSM API Connector

Supports ANY JSON API through configurable field mapping.
Handles authentication, pagination, and field extraction.
"""
import logging
import json
import base64
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
from abc import ABC, abstractmethod
from uuid import UUID

import requests
from jsonpath_ng import parse
from dateutil import parser as date_parser

from app.models_itsm import ChangeEvent, ITSMIntegration


def utc_now():
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)


# ========== AUTH HANDLERS ==========

class BaseAuthHandler(ABC):
    """Base class for authentication handlers"""

    @abstractmethod
    def apply_auth(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Apply authentication to headers"""
        pass


class BearerTokenAuth(BaseAuthHandler):
    """Bearer token authentication"""

    def __init__(self, token: str):
        self.token = token

    def apply_auth(self, headers: Dict[str, str]) -> Dict[str, str]:
        headers['Authorization'] = f'Bearer {self.token}'
        return headers


class BasicAuth(BaseAuthHandler):
    """HTTP Basic authentication"""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def apply_auth(self, headers: Dict[str, str]) -> Dict[str, str]:
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers['Authorization'] = f'Basic {encoded}'
        return headers


class APIKeyAuth(BaseAuthHandler):
    """API key in header"""

    def __init__(self, key: str, header_name: str = 'X-API-Key'):
        self.key = key
        self.header_name = header_name

    def apply_auth(self, headers: Dict[str, str]) -> Dict[str, str]:
        headers[self.header_name] = self.key
        return headers


class NoAuth(BaseAuthHandler):
    """No authentication"""

    def apply_auth(self, headers: Dict[str, str]) -> Dict[str, str]:
        return headers


class AuthHandlerFactory:
    """Factory for creating auth handlers"""

    @staticmethod
    def create(auth_config: Optional[Dict[str, Any]]) -> BaseAuthHandler:
        """
        Create auth handler from config

        Config formats:
        - Bearer: {"type": "bearer_token", "token": "xxx"}
        - Basic: {"type": "basic", "username": "user", "password": "pass"}
        - API Key: {"type": "api_key", "key": "xxx", "header_name": "X-API-Key"}
        - None: {"type": "none"} or None
        """
        if not auth_config or auth_config.get('type') == 'none':
            return NoAuth()

        auth_type = auth_config.get('type', 'bearer_token')

        if auth_type == 'bearer_token':
            return BearerTokenAuth(auth_config['token'])
        elif auth_type == 'basic':
            return BasicAuth(auth_config['username'], auth_config['password'])
        elif auth_type == 'api_key':
            return APIKeyAuth(
                auth_config['key'],
                auth_config.get('header_name', 'X-API-Key')
            )
        else:
            raise ValueError(f"Unknown auth type: {auth_type}")


# ========== PAGINATION HANDLERS ==========

class BasePaginationHandler(ABC):
    """Base class for pagination handlers"""

    @abstractmethod
    def get_next_params(
        self,
        current_params: Dict[str, Any],
        response_data: Dict[str, Any],
        page_num: int
    ) -> Optional[Dict[str, Any]]:
        """Get parameters for next page, or None if no more pages"""
        pass

    @abstractmethod
    def has_more_results(self, response_data: Dict[str, Any], current_count: int) -> bool:
        """Check if there are more results to fetch"""
        pass


class OffsetPagination(BasePaginationHandler):
    """Offset-based pagination (offset + limit)"""

    def __init__(self, config: Dict[str, Any]):
        self.offset_param = config.get('offset_param', 'offset')
        self.limit_param = config.get('limit_param', 'limit')
        self.page_size = config.get('page_size', 100)
        self.max_pages = config.get('max_pages', 10)

    def get_next_params(
        self,
        current_params: Dict[str, Any],
        response_data: Dict[str, Any],
        page_num: int
    ) -> Optional[Dict[str, Any]]:
        if page_num >= self.max_pages:
            return None

        current_offset = current_params.get(self.offset_param, 0)
        next_offset = current_offset + self.page_size

        return {
            **current_params,
            self.offset_param: next_offset,
            self.limit_param: self.page_size
        }

    def has_more_results(self, response_data: Dict[str, Any], current_count: int) -> bool:
        return current_count >= self.page_size


class PagePagination(BasePaginationHandler):
    """Page-based pagination (page + per_page)"""

    def __init__(self, config: Dict[str, Any]):
        self.page_param = config.get('page_param', 'page')
        self.per_page_param = config.get('per_page_param', 'per_page')
        self.page_size = config.get('page_size', 100)
        self.max_pages = config.get('max_pages', 10)

    def get_next_params(
        self,
        current_params: Dict[str, Any],
        response_data: Dict[str, Any],
        page_num: int
    ) -> Optional[Dict[str, Any]]:
        if page_num >= self.max_pages:
            return None

        next_page = page_num + 1

        return {
            **current_params,
            self.page_param: next_page,
            self.per_page_param: self.page_size
        }

    def has_more_results(self, response_data: Dict[str, Any], current_count: int) -> bool:
        return current_count >= self.page_size


class NoPagination(BasePaginationHandler):
    """No pagination - single request"""

    def get_next_params(
        self,
        current_params: Dict[str, Any],
        response_data: Dict[str, Any],
        page_num: int
    ) -> Optional[Dict[str, Any]]:
        return None  # Only one page

    def has_more_results(self, response_data: Dict[str, Any], current_count: int) -> bool:
        return False


class PaginationHandlerFactory:
    """Factory for creating pagination handlers"""

    @staticmethod
    def create(pagination_config: Optional[Dict[str, Any]]) -> BasePaginationHandler:
        """
        Create pagination handler from config

        Config formats:
        - Offset: {"type": "offset", "offset_param": "offset", "limit_param": "limit", "page_size": 100}
        - Page: {"type": "page", "page_param": "page", "per_page_param": "per_page", "page_size": 100}
        - None: {"type": "none"} or None
        """
        if not pagination_config or pagination_config.get('type') == 'none':
            return NoPagination()

        pag_type = pagination_config.get('type', 'offset')

        if pag_type == 'offset':
            return OffsetPagination(pagination_config)
        elif pag_type == 'page':
            return PagePagination(pagination_config)
        else:
            raise ValueError(f"Unknown pagination type: {pag_type}")


# ========== FIELD MAPPER ==========

class FieldMapper:
    """Map ITSM fields to ChangeEvent fields using JSONPath"""

    def __init__(self, field_mapping: Dict[str, str], transformations: Optional[Dict[str, Dict]] = None):
        """
        Initialize field mapper

        Args:
            field_mapping: JSONPath expressions for each field
                Example: {"change_id": "$.result[*].number", "timestamp": "$.result[*].sys_created_on"}
            transformations: Optional transformations for fields
                Example: {"timestamp": {"type": "datetime", "format": "iso8601"}}
        """
        self.field_mapping = field_mapping
        self.transformations = transformations or {}

    def extract_fields(self, json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract fields from JSON response using JSONPath

        Args:
            json_data: API response JSON

        Returns:
            List of dicts with mapped fields (one per change)
        """
        # Parse all JSONPath expressions
        parsed_paths = {}
        for field_name, json_path in self.field_mapping.items():
            try:
                parsed_paths[field_name] = parse(json_path)
            except Exception as e:
                logger.error(f"Invalid JSONPath for {field_name}: {json_path} - {e}")
                continue

        # Extract values for each field
        field_values = {}
        for field_name, path_expr in parsed_paths.items():
            try:
                matches = path_expr.find(json_data)
                field_values[field_name] = [m.value for m in matches]
            except Exception as e:
                logger.error(f"Error extracting {field_name}: {e}")
                field_values[field_name] = []

        # Determine number of records
        if not field_values:
            return []

        num_records = max(len(values) for values in field_values.values()) if field_values else 0

        # Build records
        records = []
        for i in range(num_records):
            record = {}
            for field_name, values in field_values.items():
                if i < len(values):
                    raw_value = values[i]
                    # Apply transformations
                    transformed_value = self._transform_value(field_name, raw_value)
                    record[field_name] = transformed_value
                else:
                    record[field_name] = None

            # Only add records with required fields
            if record.get('change_id') and record.get('timestamp'):
                records.append(record)

        return records

    def _transform_value(self, field_name: str, value: Any) -> Any:
        """Apply transformation to a field value"""
        if field_name not in self.transformations:
            return value

        transform = self.transformations[field_name]
        transform_type = transform.get('type')

        if transform_type == 'datetime':
            return self._parse_datetime(value, transform.get('format', 'iso8601'))
        elif transform_type == 'lowercase':
            return str(value).lower() if value else None
        elif transform_type == 'uppercase':
            return str(value).upper() if value else None
        else:
            return value

    def _parse_datetime(self, value: Any, format_type: str) -> Optional[datetime]:
        """Parse datetime from various formats"""
        if not value:
            return None

        try:
            if format_type == 'iso8601':
                return date_parser.parse(str(value))
            elif format_type == 'unix':
                return datetime.fromtimestamp(int(value))
            elif format_type == 'unix_ms':
                return datetime.fromtimestamp(int(value) / 1000)
            else:
                # Try to parse as strptime format
                return datetime.strptime(str(value), format_type)
        except Exception as e:
            logger.warning(f"Failed to parse datetime '{value}': {e}")
            return None


# ========== GENERIC API CONNECTOR ==========

class GenericAPIConnector:
    """Generic API connector for ITSM systems"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize connector with configuration

        Config structure:
        {
            "api_config": {
                "base_url": "https://api.example.com/changes",
                "method": "GET",
                "headers": {"Content-Type": "application/json"},
                "query_params": {"key": "value"}
            },
            "auth": {
                "type": "bearer_token",
                "token": "xxx"
            },
            "pagination": {
                "type": "offset",
                "page_size": 100
            },
            "field_mapping": {
                "change_id": "$.data[*].id",
                "change_type": "$.data[*].type",
                "service_name": "$.data[*].service",
                "description": "$.data[*].summary",
                "timestamp": "$.data[*].created_at"
            },
            "transformations": {
                "timestamp": {"type": "datetime", "format": "iso8601"}
            }
        }
        """
        self.config = config
        self.api_config = config.get('api_config', {})
        
        # Initialize handlers
        self.auth_handler = AuthHandlerFactory.create(config.get('auth'))
        self.pagination_handler = PaginationHandlerFactory.create(config.get('pagination'))
        self.field_mapper = FieldMapper(
            config.get('field_mapping', {}),
            config.get('transformations')
        )

        # HTTP session for connection reuse
        self.session = requests.Session()
        self.timeout = config.get('timeout', 30)

    def test_connection(self) -> Tuple[bool, str, Optional[Dict]]:
        """
        Test API connection with detailed diagnostics

        Returns:
            Tuple of (success, message, detailed_results)
        """
        diagnostics = {
            'http_status': None,
            'response_type': None,
            'response_preview': None,
            'records_found': 0,
            'sample_record': None,
            'field_mapping_results': {},
            'warnings': [],
            'url_tested': None
        }

        try:
            # Build request
            url = self.api_config.get('base_url', '')
            method = self.api_config.get('method', 'GET')
            headers = self.api_config.get('headers', {'Content-Type': 'application/json'})
            params = self.api_config.get('query_params', {}).copy()

            diagnostics['url_tested'] = url

            # Apply auth
            headers = self.auth_handler.apply_auth(headers)

            # Make request (limit to small number for test)
            pagination_config = self.config.get('pagination', {})
            limit_param = pagination_config.get('limit_param') or pagination_config.get('per_page_param') or 'maxResults'
            params[limit_param] = 5  # Get up to 5 records for preview

            logger.info(f"Testing connection to {url}")

            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                timeout=self.timeout
            )

            diagnostics['http_status'] = response.status_code

            if response.status_code == 200:
                try:
                    data = response.json()
                    diagnostics['response_type'] = 'JSON'
                    
                    # Show response preview (truncated)
                    response_str = json.dumps(data, indent=2)
                    diagnostics['response_preview'] = response_str[:500] + ('...' if len(response_str) > 500 else '')
                    
                    # Try to extract records using field mapping
                    records = self.field_mapper.extract_fields(data)
                    diagnostics['records_found'] = len(records)
                    
                    if records:
                        diagnostics['sample_record'] = records[0]
                        
                        # Show which fields were successfully mapped
                        for field_name in self.field_mapper.field_mapping.keys():
                            value = records[0].get(field_name)
                            diagnostics['field_mapping_results'][field_name] = {
                                'extracted': value is not None,
                                'value_preview': str(value)[:100] if value else None
                            }
                        
                        return True, f"Success! Found {len(records)} record(s)", diagnostics
                    else:
                        diagnostics['warnings'].append("No records extracted - check JSONPath field mappings")
                        return True, "Connected but no records extracted", diagnostics
                        
                except json.JSONDecodeError:
                    diagnostics['response_type'] = 'Non-JSON'
                    diagnostics['response_preview'] = response.text[:300]
                    diagnostics['warnings'].append("Response is not valid JSON")
                    return True, "Connection OK but response is not JSON", diagnostics
                    
            elif response.status_code == 401:
                diagnostics['warnings'].append("Authentication failed - check credentials")
                return False, "401 Unauthorized - Invalid credentials", diagnostics
                
            elif response.status_code == 403:
                diagnostics['response_preview'] = response.text[:300]
                diagnostics['warnings'].append("Access forbidden - check API permissions")
                return False, f"403 Forbidden - {response.text[:100]}", diagnostics
                
            elif response.status_code == 404:
                diagnostics['warnings'].append("Endpoint not found - check API URL")
                return False, "404 Not Found - Invalid API URL", diagnostics
                
            elif response.status_code == 410:
                diagnostics['warnings'].append("API endpoint deprecated or unavailable")
                return False, "410 Gone - API endpoint not available", diagnostics
                
            else:
                diagnostics['response_preview'] = response.text[:300]
                return False, f"HTTP {response.status_code}: {response.text[:150]}", diagnostics

        except requests.exceptions.Timeout:
            diagnostics['warnings'].append("Request timed out - server may be slow or unreachable")
            return False, "Connection timed out", diagnostics
        except requests.exceptions.ConnectionError as e:
            diagnostics['warnings'].append(f"Network error: {str(e)[:100]}")
            return False, f"Connection error: {str(e)[:100]}", diagnostics
        except Exception as e:
            logger.exception("Error testing connection")
            diagnostics['warnings'].append(f"Unexpected error: {str(e)[:100]}")
            return False, f"Error: {str(e)[:100]}", diagnostics

    def fetch_changes(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch changes from ITSM API

        Args:
            since: Only fetch changes after this timestamp

        Returns:
            List of change records
        """
        all_records = []
        page_num = 0

        # Build initial request
        url = self.api_config.get('base_url', '')
        method = self.api_config.get('method', 'GET')
        headers = self.api_config.get('headers', {'Content-Type': 'application/json'})
        params = self.api_config.get('query_params', {}).copy()

        # Apply auth
        headers = self.auth_handler.apply_auth(headers)

        # Apply time filter if configured
        if since:
            time_param = self.config.get('time_filter_param')
            time_format = self.config.get('time_filter_format', 'iso8601')
            if time_param:
                if time_format == 'iso8601':
                    params[time_param] = since.isoformat()
                elif time_format == 'unix':
                    params[time_param] = int(since.timestamp())

        # Fetch all pages
        while True:
            logger.info(f"Fetching page {page_num + 1} from {url}")

            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout
                )

                if response.status_code != 200:
                    logger.error(f"API error: {response.status_code} - {response.text[:200]}")
                    break

                data = response.json()
                records = self.field_mapper.extract_fields(data)

                if not records:
                    break

                all_records.extend(records)
                page_num += 1

                # Check for more pages
                if not self.pagination_handler.has_more_results(data, len(records)):
                    break

                next_params = self.pagination_handler.get_next_params(params, data, page_num)
                if not next_params:
                    break

                params = next_params

            except Exception as e:
                logger.exception(f"Error fetching changes: {e}")
                break

        logger.info(f"Fetched {len(all_records)} changes in {page_num + 1} pages")
        return all_records

    def sync(self, db, integration_id: UUID, since: Optional[datetime] = None) -> Tuple[int, int, List[str]]:
        """
        Sync changes from ITSM to database

        Args:
            db: Database session
            integration_id: ID of the ITSM integration
            since: Only sync changes after this timestamp

        Returns:
            Tuple of (created_count, updated_count, errors)
        """
        from sqlalchemy.exc import IntegrityError

        records = self.fetch_changes(since)
        created = 0
        updated = 0
        errors = []

        for record in records:
            try:
                # Check if change already exists
                existing = db.query(ChangeEvent).filter(
                    ChangeEvent.change_id == record['change_id']
                ).first()

                if existing:
                    # Update existing
                    for key, value in record.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                    updated += 1
                else:
                    # Create new
                    change = ChangeEvent(
                        change_id=record['change_id'],
                        change_type=record.get('change_type', 'unknown'),
                        service_name=record.get('service_name'),
                        description=record.get('description'),
                        timestamp=record.get('timestamp') or utc_now(),
                        source=str(integration_id),
                        metadata=record.get('metadata', {})
                    )
                    db.add(change)
                    created += 1

            except IntegrityError as e:
                db.rollback()
                errors.append(f"Duplicate change_id: {record.get('change_id')}")
            except Exception as e:
                errors.append(f"Error processing {record.get('change_id')}: {str(e)}")

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            errors.append(f"Commit error: {str(e)}")

        logger.info(f"Sync complete: {created} created, {updated} updated, {len(errors)} errors")
        return created, updated, errors


# ========== CONFIGURATION TEMPLATES ==========

ITSM_TEMPLATES = {
    "servicenow": {
        "name": "ServiceNow",
        "description": "ServiceNow Change Management",
        "config_template": {
            "api_config": {
                "base_url": "https://YOUR_INSTANCE.service-now.com/api/now/table/change_request",
                "method": "GET",
                "headers": {"Accept": "application/json"},
                "query_params": {"sysparm_display_value": "true"}
            },
            "auth": {
                "type": "basic",
                "username": "YOUR_USERNAME",
                "password": "YOUR_PASSWORD"
            },
            "pagination": {
                "type": "offset",
                "offset_param": "sysparm_offset",
                "limit_param": "sysparm_limit",
                "page_size": 100
            },
            "field_mapping": {
                "change_id": "$.result[*].number",
                "change_type": "$.result[*].type",
                "service_name": "$.result[*].cmdb_ci.display_value",
                "description": "$.result[*].short_description",
                "timestamp": "$.result[*].sys_created_on"
            },
            "transformations": {
                "timestamp": {"type": "datetime", "format": "iso8601"}
            },
            "time_filter_param": "sysparm_query",
            "time_filter_format": "servicenow"
        }
    },
    "jira": {
        "name": "Jira",
        "description": "Jira deployment tickets",
        "config_template": {
            "api_config": {
                "base_url": "https://YOUR_DOMAIN.atlassian.net/rest/api/3/search",
                "method": "GET",
                "headers": {"Accept": "application/json"},
                "query_params": {"jql": "project=OPS AND labels=deployment"}
            },
            "auth": {
                "type": "basic",
                "username": "YOUR_EMAIL",
                "password": "YOUR_API_TOKEN"
            },
            "pagination": {
                "type": "offset",
                "offset_param": "startAt",
                "limit_param": "maxResults",
                "page_size": 50
            },
            "field_mapping": {
                "change_id": "$.issues[*].key",
                "change_type": "$.issues[*].fields.issuetype.name",
                "service_name": "$.issues[*].fields.components[0].name",
                "description": "$.issues[*].fields.summary",
                "timestamp": "$.issues[*].fields.created"
            },
            "transformations": {
                "timestamp": {"type": "datetime", "format": "iso8601"}
            }
        }
    },
    "github": {
        "name": "GitHub Deployments",
        "description": "GitHub deployment events",
        "config_template": {
            "api_config": {
                "base_url": "https://api.github.com/repos/OWNER/REPO/deployments",
                "method": "GET",
                "headers": {"Accept": "application/vnd.github.v3+json"}
            },
            "auth": {
                "type": "bearer_token",
                "token": "YOUR_GITHUB_TOKEN"
            },
            "pagination": {
                "type": "page",
                "page_param": "page",
                "per_page_param": "per_page",
                "page_size": 100
            },
            "field_mapping": {
                "change_id": "$[*].id",
                "change_type": "$[*].task",
                "service_name": "$[*].environment",
                "description": "$[*].description",
                "timestamp": "$[*].created_at"
            },
            "transformations": {
                "timestamp": {"type": "datetime", "format": "iso8601"},
                "change_id": {"type": "string"}
            }
        }
    }
}


def get_itsm_templates() -> List[Dict[str, Any]]:
    """Get list of available ITSM configuration templates"""
    return [
        {
            "name": key,
            "display_name": template["name"],
            "description": template["description"]
        }
        for key, template in ITSM_TEMPLATES.items()
    ]


def get_itsm_template(template_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific ITSM template by name"""
    return ITSM_TEMPLATES.get(template_name)
