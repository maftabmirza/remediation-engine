"""
Dashboard Variables API

API endpoints for managing dashboard variables (template variables).
Supports query, custom, constant, textbox, and interval variable types.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
import json
import re

from app.database import get_db
from app.models_dashboards import DashboardVariable, Dashboard, PrometheusDatasource, VariableType
from app.services.prometheus_service import PrometheusService

router = APIRouter(prefix="/api/dashboards/{dashboard_id}/variables", tags=["variables"])


# Pydantic schemas
class VariableCreate(BaseModel):
    name: str = Field(..., description="Variable name (used in queries as $name)")
    label: Optional[str] = Field(None, description="Display label")
    type: str = Field(default="query", description="Variable type: query, custom, constant, textbox, interval")
    query: Optional[str] = Field(None, description="PromQL query for query type")
    datasource_id: Optional[str] = Field(None, description="Datasource ID for query type")
    regex: Optional[str] = Field(None, description="Regex to filter/transform query results")
    custom_values: Optional[List[str]] = Field(None, description="List of values for custom type")
    default_value: Optional[str] = Field(None, description="Default selected value")
    multi_select: bool = Field(default=False, description="Allow multiple selections")
    include_all: bool = Field(default=False, description="Include 'All' option")
    all_value: Optional[str] = Field(default=".*", description="Value to use when 'All' is selected")
    hide: int = Field(default=0, description="0=visible, 1=label only, 2=hidden")
    sort: int = Field(default=0, description="Display order")

    class Config:
        from_attributes = True


class VariableUpdate(BaseModel):
    label: Optional[str] = None
    query: Optional[str] = None
    datasource_id: Optional[str] = None
    regex: Optional[str] = None
    custom_values: Optional[List[str]] = None
    default_value: Optional[str] = None
    current_value: Optional[str] = None
    multi_select: Optional[bool] = None
    include_all: Optional[bool] = None
    all_value: Optional[str] = None
    hide: Optional[int] = None
    sort: Optional[int] = None

    class Config:
        from_attributes = True


class VariableResponse(BaseModel):
    id: str
    dashboard_id: str
    name: str
    label: Optional[str]
    type: str
    query: Optional[str]
    datasource_id: Optional[str]
    regex: Optional[str]
    custom_values: Optional[List[str]]
    default_value: Optional[str]
    current_value: Optional[str]
    multi_select: bool
    include_all: bool
    all_value: Optional[str]
    hide: int
    sort: int
    options: Optional[List[str]] = None  # Populated options

    class Config:
        from_attributes = True


@router.get("/", response_model=List[VariableResponse])
async def list_variables(
    dashboard_id: str,
    db: Session = Depends(get_db)
):
    """List all variables for a dashboard"""
    # Verify dashboard exists
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    variables = db.query(DashboardVariable)\
        .filter(DashboardVariable.dashboard_id == dashboard_id)\
        .order_by(DashboardVariable.sort)\
        .all()

    # Populate options for each variable
    result = []
    for var in variables:
        var_dict = {
            "id": var.id,
            "dashboard_id": var.dashboard_id,
            "name": var.name,
            "label": var.label or var.name,
            "type": var.type,
            "query": var.query,
            "datasource_id": var.datasource_id,
            "regex": var.regex,
            "custom_values": var.custom_values,
            "default_value": var.default_value,
            "current_value": var.current_value or var.default_value,
            "multi_select": var.multi_select,
            "include_all": var.include_all,
            "all_value": var.all_value,
            "hide": var.hide,
            "sort": var.sort,
            "options": await get_variable_options(var, db)
        }
        result.append(VariableResponse(**var_dict))

    return result


@router.post("/", response_model=VariableResponse, status_code=201)
async def create_variable(
    dashboard_id: str,
    variable: VariableCreate,
    db: Session = Depends(get_db)
):
    """Create a new dashboard variable"""
    # Verify dashboard exists
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    # Check if variable name already exists
    existing = db.query(DashboardVariable)\
        .filter(
            DashboardVariable.dashboard_id == dashboard_id,
            DashboardVariable.name == variable.name
        ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Variable with name '{variable.name}' already exists in this dashboard"
        )

    # Validate variable type
    if variable.type not in [vt.value for vt in VariableType]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid variable type. Must be one of: {[vt.value for vt in VariableType]}"
        )

    # Create variable
    db_variable = DashboardVariable(
        dashboard_id=dashboard_id,
        name=variable.name,
        label=variable.label or variable.name,
        type=variable.type,
        query=variable.query,
        datasource_id=variable.datasource_id,
        regex=variable.regex,
        custom_values=variable.custom_values,
        default_value=variable.default_value,
        multi_select=variable.multi_select,
        include_all=variable.include_all,
        all_value=variable.all_value or ".*",
        hide=variable.hide,
        sort=variable.sort
    )

    db.add(db_variable)
    db.commit()
    db.refresh(db_variable)

    # Get options
    options = await get_variable_options(db_variable, db)

    return VariableResponse(
        id=db_variable.id,
        dashboard_id=db_variable.dashboard_id,
        name=db_variable.name,
        label=db_variable.label,
        type=db_variable.type,
        query=db_variable.query,
        datasource_id=db_variable.datasource_id,
        regex=db_variable.regex,
        custom_values=db_variable.custom_values,
        default_value=db_variable.default_value,
        current_value=db_variable.current_value or db_variable.default_value,
        multi_select=db_variable.multi_select,
        include_all=db_variable.include_all,
        all_value=db_variable.all_value,
        hide=db_variable.hide,
        sort=db_variable.sort,
        options=options
    )


@router.get("/{variable_id}", response_model=VariableResponse)
async def get_variable(
    dashboard_id: str,
    variable_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific variable"""
    variable = db.query(DashboardVariable)\
        .filter(
            DashboardVariable.id == variable_id,
            DashboardVariable.dashboard_id == dashboard_id
        ).first()

    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")

    options = await get_variable_options(variable, db)

    return VariableResponse(
        id=variable.id,
        dashboard_id=variable.dashboard_id,
        name=variable.name,
        label=variable.label,
        type=variable.type,
        query=variable.query,
        datasource_id=variable.datasource_id,
        regex=variable.regex,
        custom_values=variable.custom_values,
        default_value=variable.default_value,
        current_value=variable.current_value or variable.default_value,
        multi_select=variable.multi_select,
        include_all=variable.include_all,
        all_value=variable.all_value,
        hide=variable.hide,
        sort=variable.sort,
        options=options
    )


@router.put("/{variable_id}", response_model=VariableResponse)
async def update_variable(
    dashboard_id: str,
    variable_id: str,
    variable_update: VariableUpdate,
    db: Session = Depends(get_db)
):
    """Update a variable"""
    variable = db.query(DashboardVariable)\
        .filter(
            DashboardVariable.id == variable_id,
            DashboardVariable.dashboard_id == dashboard_id
        ).first()

    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")

    # Update fields
    update_data = variable_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(variable, key, value)

    db.commit()
    db.refresh(variable)

    options = await get_variable_options(variable, db)

    return VariableResponse(
        id=variable.id,
        dashboard_id=variable.dashboard_id,
        name=variable.name,
        label=variable.label,
        type=variable.type,
        query=variable.query,
        datasource_id=variable.datasource_id,
        regex=variable.regex,
        custom_values=variable.custom_values,
        default_value=variable.default_value,
        current_value=variable.current_value or variable.default_value,
        multi_select=variable.multi_select,
        include_all=variable.include_all,
        all_value=variable.all_value,
        hide=variable.hide,
        sort=variable.sort,
        options=options
    )


@router.delete("/{variable_id}", status_code=204)
async def delete_variable(
    dashboard_id: str,
    variable_id: str,
    db: Session = Depends(get_db)
):
    """Delete a variable"""
    variable = db.query(DashboardVariable)\
        .filter(
            DashboardVariable.id == variable_id,
            DashboardVariable.dashboard_id == dashboard_id
        ).first()

    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")

    db.delete(variable)
    db.commit()

    return None


@router.get("/{variable_id}/values", response_model=List[str])
async def get_variable_values(
    dashboard_id: str,
    variable_id: str,
    db: Session = Depends(get_db)
):
    """Get current values/options for a variable"""
    variable = db.query(DashboardVariable)\
        .filter(
            DashboardVariable.id == variable_id,
            DashboardVariable.dashboard_id == dashboard_id
        ).first()

    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")

    options = await get_variable_options(variable, db)
    return options


# Helper function to get variable options
async def get_variable_options(variable: DashboardVariable, db: Session) -> List[str]:
    """Get available options for a variable based on its type"""
    if variable.type == "custom":
        options = variable.custom_values or []
    elif variable.type == "query":
        options = await evaluate_query_variable(variable, db)
    elif variable.type == "constant":
        options = [variable.default_value] if variable.default_value else []
    elif variable.type == "textbox":
        options = [variable.current_value or variable.default_value or ""]
    elif variable.type == "interval":
        options = ["1m", "5m", "10m", "30m", "1h", "6h", "12h", "1d", "7d", "30d"]
    else:
        options = []

    # Add "All" option if enabled
    if variable.include_all and variable.type not in ["constant", "textbox"]:
        options = ["All"] + options

    return options


async def evaluate_query_variable(variable: DashboardVariable, db: Session) -> List[str]:
    """Evaluate a query variable to get its options"""
    if not variable.query or not variable.datasource_id:
        return []

    try:
        # Get datasource
        datasource = db.query(PrometheusDatasource)\
            .filter(PrometheusDatasource.id == variable.datasource_id)\
            .first()

        if not datasource:
            return []

        # Use PrometheusService to execute query
        prom_service = PrometheusService(datasource)
        result = await prom_service.query(variable.query)

        # Extract values from result
        values = set()
        if result and "data" in result:
            data = result["data"]
            if "result" in data:
                for item in data["result"]:
                    if "metric" in item:
                        # Extract all label values
                        for key, value in item["metric"].items():
                            values.add(value)
                    elif "value" in item and len(item["value"]) > 1:
                        # For instant queries, use the value
                        values.add(str(item["value"][1]))

        # Apply regex filter if specified
        if variable.regex and values:
            pattern = re.compile(variable.regex)
            values = {v for v in values if pattern.search(v)}

        return sorted(list(values))

    except Exception as e:
        print(f"Error evaluating query variable: {e}")
        return []
