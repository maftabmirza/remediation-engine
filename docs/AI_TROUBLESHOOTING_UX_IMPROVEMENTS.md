# AI Troubleshooting UX Improvements

## Feedback Summary & Implementation Plan

**Date:** 2026-01-17  
**Status:** Planning  
**Priority:** High  

---

## Executive Summary

User feedback has identified 4 critical gaps in the `/ai` troubleshooting experience:

| # | Gap | Current State | Impact |
|---|-----|---------------|--------|
| 1 | No visible reasoning | 5-phase protocol hidden in prompt | Users don't know what AI is thinking |
| 2 | Commands not editable | Click "Run" executes immediately | No chance to modify commands before execution |
| 3 | No planning artifact | Plan exists only in AI's context | Users can't review or modify the investigation plan |
| 4 | No progress tracking | Unknown where AI is in workflow | Users feel lost during long investigations |

---

## Gap 1: Reasoning Panel (Show AI's Thinking)

### Problem
The 5-phase troubleshooting protocol (IDENTIFY → VERIFY → INVESTIGATE → PLAN → ACT) is embedded in the system prompt but invisible to users. Users see tool outputs but not the AI's reasoning.

### Current Implementation
- [react_agent.py](../app/services/agentic/react_agent.py): Phases defined in system prompt
- [progress_messages.py](../app/services/agentic/progress_messages.py): Phase messages exist but only partially shown

### Solution: Collapsible Reasoning Panel

#### UI Design
```
┌─────────────────────────────────────────────────────────────────┐
│ 🤖 AI Troubleshooting                              [≡] [−] [×]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 💭 AI Reasoning                              [▼ Expand]  │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ 🔍 Phase 1: IDENTIFY                                    │   │
│  │    "User reports high CPU on web-server-01"             │   │
│  │                                                         │   │
│  │ ✅ Phase 2: VERIFY                                      │   │
│  │    "Confirmed: Ubuntu 22.04, systemd, Apache running"   │   │
│  │                                                         │   │
│  │ 📊 Phase 3: INVESTIGATE                     ← Current   │   │
│  │    Thought: "CPU at 95% - checking process list"        │   │
│  │    Tool: get_process_list → Found apache2 using 89%     │   │
│  │    Tool: query_metrics → Spike started at 14:32         │   │
│  │                                                         │   │
│  │ 🧠 Phase 4: PLAN (pending)                              │   │
│  │ 🛠️ Phase 5: ACT (pending)                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [Chat messages continue below...]                              │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation

**Backend Changes:**

1. **New streaming event type** - Emit reasoning updates via WebSocket:
```python
# app/services/agentic/react_agent.py

class ReasoningEvent:
    """Structured event for UI reasoning panel"""
    def __init__(self, phase: str, thought: str, tool_call: str = None, observation: str = None):
        self.phase = phase
        self.thought = thought
        self.tool_call = tool_call
        self.observation = observation

async def stream(self, user_message: str) -> AsyncGenerator[str, None]:
    # ... existing code ...
    
    # NEW: Emit reasoning events
    yield f"[REASONING]{json.dumps({
        'phase': current_phase,
        'thought': thought_text,
        'tool': action_name if action else None,
        'step': iterations
    })}[/REASONING]"
```

2. **Phase detection from LLM output**:
```python
# app/services/agentic/phase_detector.py (NEW FILE)

import re
from enum import Enum

class PhaseDetector:
    """Detect which phase the AI is in based on its output"""
    
    PHASE_PATTERNS = {
        'identify': [r'identifying', r'what we\'re troubleshooting', r'issue is'],
        'verify': [r'verifying', r'confirmed?', r'target (server|system)'],
        'investigate': [r'gathering', r'querying', r'checking', r'looking at'],
        'plan': [r'analyzing', r'hypothesis', r'likely cause', r'based on'],
        'act': [r'suggest(ing)?', r'recommend', r'command to run']
    }
    
    @classmethod
    def detect_phase(cls, text: str) -> str:
        text_lower = text.lower()
        for phase, patterns in cls.PHASE_PATTERNS.items():
            if any(re.search(p, text_lower) for p in patterns):
                return phase
        return 'unknown'
```

**Frontend Changes:**

1. **New reasoning panel component** in `ai_chat.js`:
```javascript
// static/js/ai_chat.js

let reasoningHistory = [];  // Store reasoning steps
let reasoningPanelVisible = true;

function initReasoningPanel() {
    const panel = document.createElement('div');
    panel.id = 'reasoningPanel';
    panel.className = 'reasoning-panel bg-gray-900 border border-gray-700 rounded-lg mb-4';
    panel.innerHTML = `
        <div class="reasoning-header flex justify-between items-center p-2 border-b border-gray-700 cursor-pointer" 
             onclick="toggleReasoningPanel()">
            <span class="text-sm font-medium text-gray-300">
                <i class="fas fa-brain mr-2 text-purple-400"></i>AI Reasoning
            </span>
            <i class="fas fa-chevron-down text-gray-500" id="reasoningToggleIcon"></i>
        </div>
        <div class="reasoning-body p-3 max-h-64 overflow-y-auto" id="reasoningBody">
            <div class="text-gray-500 text-sm">Waiting for investigation to start...</div>
        </div>
    `;
    return panel;
}

function updateReasoningPanel(event) {
    // Parse [REASONING]...[/REASONING] from stream
    const data = JSON.parse(event);
    reasoningHistory.push(data);
    renderReasoningSteps();
}

function renderReasoningSteps() {
    const body = document.getElementById('reasoningBody');
    if (!body) return;
    
    body.innerHTML = reasoningHistory.map((step, i) => `
        <div class="reasoning-step ${step.phase === getCurrentPhase() ? 'current' : ''} 
                    mb-3 pl-4 border-l-2 ${getPhaseColor(step.phase)}">
            <div class="flex items-center text-xs font-medium mb-1">
                ${getPhaseIcon(step.phase)} 
                <span class="ml-2">${getPhaseTitle(step.phase)}</span>
                ${step.phase === getCurrentPhase() ? '<span class="ml-2 text-blue-400">← Current</span>' : ''}
            </div>
            ${step.thought ? `<div class="text-gray-400 text-xs italic">"${step.thought}"</div>` : ''}
            ${step.tool ? `
                <div class="text-xs mt-1">
                    <span class="text-yellow-400">Tool:</span> ${step.tool}
                </div>
            ` : ''}
        </div>
    `).join('');
}
```

2. **CSS for reasoning panel**:
```css
/* In ai_chat.html or separate CSS file */
.reasoning-panel {
    transition: all 0.3s ease;
}
.reasoning-panel.collapsed .reasoning-body {
    display: none;
}
.reasoning-step.current {
    background: rgba(59, 130, 246, 0.1);
    border-radius: 4px;
    padding: 8px;
    margin-left: -8px;
}
.border-identify { border-color: #60a5fa; }
.border-verify { border-color: #34d399; }
.border-investigate { border-color: #fbbf24; }
.border-plan { border-color: #a78bfa; }
.border-act { border-color: #f472b6; }
```

---

## Gap 2: Editable Commands Before Execution

### Problem
When AI suggests a command via `suggest_ssh_command`, clicking "Run" executes immediately. Users cannot modify parameters or review command details.

### Current Implementation
- [ai_chat.js#renderCommandCard()](../static/js/ai_chat.js#L680): Renders command with Run button
- No edit capability before execution

### Solution: Command Editor Modal

#### UI Design
```
┌─────────────────────────────────────────────────────────────────┐
│ 📝 Review Command Before Execution                         [×]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Target Server: web-server-01                                   │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Command:                                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ systemctl restart apache2                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│  [Edit ✏️]                                                      │
│                                                                 │
│  Explanation:                                                   │
│  "Restart Apache to apply configuration changes and clear       │
│   any stuck worker processes."                                  │
│                                                                 │
│  Safety Check: ✅ Safe (service restart)                        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [Cancel]              [Copy]         [▶ Execute]        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Expanded Edit Mode:**
```
┌─────────────────────────────────────────────────────────────────┐
│  Command (editing):                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ systemctl restart apache2 --no-block                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│  [Done ✓] [Revert ↩]                                           │
│                                                                 │
│  ⚠️ Modified from original suggestion                           │
│  Re-validating... ✅ Still safe                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation

**Frontend Changes:**

1. **Replace direct execution with modal**:
```javascript
// static/js/ai_chat.js

// Replace existing renderCommandCard function
function renderCommandCard(command, server, explanation) {
    const cardId = 'cmd-' + Date.now();
    const container = document.getElementById('chatMessages');
    
    const wrapper = document.createElement('div');
    wrapper.className = 'command-card-wrapper';
    wrapper.innerHTML = `
        <div id="${cardId}" class="command-card bg-gray-800 border border-blue-600 rounded-lg p-4 my-2">
            <div class="flex items-start justify-between mb-2">
                <div class="flex items-center">
                    <i class="fas fa-terminal text-blue-400 mr-2"></i>
                    <span class="text-sm font-medium text-gray-200">Suggested Command</span>
                </div>
                <span class="text-xs text-gray-500">${server}</span>
            </div>
            
            <div class="command-display bg-gray-900 p-3 rounded font-mono text-sm text-green-400 mb-2">
                ${escapeHtml(command)}
            </div>
            
            <div class="text-xs text-gray-400 mb-3">
                <i class="fas fa-info-circle mr-1"></i>${escapeHtml(explanation)}
            </div>
            
            <div class="cmd-actions flex gap-2">
                <button onclick="openCommandEditor('${cardId}', '${escapeAttr(command)}', '${escapeAttr(server)}', '${escapeAttr(explanation)}')" 
                        class="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded font-medium transition-colors flex items-center justify-center">
                    <i class="fas fa-play mr-2"></i>Review & Run
                </button>
                <button onclick="skipCommand('${cardId}', '${escapeAttr(command)}')" 
                        class="bg-yellow-600 hover:bg-yellow-500 text-white text-sm px-3 py-2 rounded font-medium transition-colors"
                        title="Skip this command">
                    <i class="fas fa-forward"></i>
                </button>
                <button onclick="copyToClipboard('${escapeAttr(command)}')" 
                        class="bg-gray-600 hover:bg-gray-500 text-white text-sm px-3 py-2 rounded font-medium transition-colors"
                        title="Copy command">
                    <i class="fas fa-copy"></i>
                </button>
            </div>
            
            <div class="cmd-output hidden mt-2"></div>
        </div>
    `;
    container.appendChild(wrapper);
}

// NEW: Command editor modal
function openCommandEditor(cardId, command, server, explanation) {
    const modal = document.createElement('div');
    modal.id = 'commandEditorModal';
    modal.className = 'fixed inset-0 bg-black/70 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-gray-800 border border-gray-600 rounded-lg w-full max-w-lg mx-4 shadow-2xl">
            <div class="flex justify-between items-center p-4 border-b border-gray-700">
                <h3 class="text-lg font-medium text-white">
                    <i class="fas fa-edit mr-2 text-blue-400"></i>Review Command
                </h3>
                <button onclick="closeCommandEditor()" class="text-gray-400 hover:text-white">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div class="p-4">
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Target Server</label>
                    <div class="bg-gray-900 p-2 rounded text-sm text-gray-300">
                        <i class="fas fa-server mr-2 text-blue-400"></i>${escapeHtml(server)}
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Command</label>
                    <div class="relative">
                        <textarea id="editableCommand" 
                                  class="w-full bg-gray-900 border border-gray-700 rounded p-3 font-mono text-sm text-green-400 focus:border-blue-500 focus:outline-none"
                                  rows="3">${escapeHtml(command)}</textarea>
                        <button onclick="resetCommand('${escapeAttr(command)}')" 
                                class="absolute top-2 right-2 text-xs text-gray-500 hover:text-white"
                                title="Reset to original">
                            <i class="fas fa-undo"></i>
                        </button>
                    </div>
                    <div id="commandModifiedBadge" class="hidden text-xs text-yellow-400 mt-1">
                        <i class="fas fa-exclamation-triangle mr-1"></i>Modified from original
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Explanation</label>
                    <div class="bg-gray-900/50 p-2 rounded text-xs text-gray-400 italic">
                        "${escapeHtml(explanation)}"
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="text-xs text-gray-400 block mb-1">Safety Check</label>
                    <div id="safetyCheckResult" class="bg-gray-900 p-2 rounded text-sm">
                        <i class="fas fa-spinner fa-spin mr-2 text-blue-400"></i>Validating...
                    </div>
                </div>
            </div>
            
            <div class="flex justify-end gap-2 p-4 border-t border-gray-700 bg-gray-900/50">
                <button onclick="closeCommandEditor()" 
                        class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">
                    Cancel
                </button>
                <button onclick="copyToClipboard(document.getElementById('editableCommand').value)" 
                        class="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors">
                    <i class="fas fa-copy mr-1"></i>Copy
                </button>
                <button id="executeBtn" onclick="executeFromEditor('${cardId}', '${escapeAttr(server)}')" 
                        class="px-4 py-2 text-sm bg-green-600 hover:bg-green-500 text-white rounded font-medium transition-colors">
                    <i class="fas fa-play mr-1"></i>Execute
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Setup change detection
    const textarea = document.getElementById('editableCommand');
    textarea.addEventListener('input', () => {
        const modified = textarea.value !== command;
        document.getElementById('commandModifiedBadge').classList.toggle('hidden', !modified);
        if (modified) {
            validateCommand(textarea.value, server);
        }
    });
    
    // Initial validation
    validateCommand(command, server);
}

async function validateCommand(command, server) {
    const resultDiv = document.getElementById('safetyCheckResult');
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin mr-2 text-blue-400"></i>Validating...';
    
    try {
        const response = await fetch('/api/commands/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command, server })
        });
        const data = await response.json();
        
        const icons = {
            'allowed': '<i class="fas fa-check-circle text-green-400 mr-2"></i>',
            'warning': '<i class="fas fa-exclamation-triangle text-yellow-400 mr-2"></i>',
            'blocked': '<i class="fas fa-ban text-red-400 mr-2"></i>'
        };
        
        resultDiv.innerHTML = `${icons[data.result] || ''}${data.message}`;
        
        // Disable execute button if blocked
        document.getElementById('executeBtn').disabled = data.result === 'blocked';
        document.getElementById('executeBtn').classList.toggle('opacity-50', data.result === 'blocked');
    } catch (err) {
        resultDiv.innerHTML = '<i class="fas fa-question-circle text-gray-400 mr-2"></i>Could not validate';
    }
}

function closeCommandEditor() {
    const modal = document.getElementById('commandEditorModal');
    if (modal) modal.remove();
}

function executeFromEditor(cardId, server) {
    const command = document.getElementById('editableCommand').value;
    closeCommandEditor();
    
    // Update the original card's command if modified
    const card = document.getElementById(cardId);
    if (card) {
        const queueItem = commandQueue.find(c => c.id === cardId);
        if (queueItem) {
            queueItem.command = command;  // Update to edited version
        }
    }
    
    // Execute via existing flow
    runQueuedCommand(cardId, { dataset: { cmd: command, server: server } });
}
```

**Backend Changes:**

1. **Add command validation endpoint**:
```python
# app/routers/chat_api.py

@router.post("/commands/validate")
async def validate_command(
    request: CommandValidateRequest,
    current_user: User = Depends(get_current_user)
):
    """Validate a command before execution"""
    from app.services.command_validator import CommandValidator, ValidationResult
    
    validator = CommandValidator()
    os_type = "windows" if "win" in request.server.lower() else "linux"
    result = validator.validate_command(request.command, os_type)
    
    return {
        "result": result.result.value,
        "message": result.message,
        "risk_level": result.risk_level
    }
```

---

## Gap 3: Visible Planning Artifact

### Problem
The investigation plan exists only in the AI's context. Users cannot see, export, or modify the plan.

### Current Implementation
- Plan is implicit in the 5-phase protocol
- No persistent storage or visibility

### Solution: Markdown Plan Document with Live Updates

#### UI Design
```
┌─────────────────────────────────────────────────────────────────┐
│ 📋 Investigation Plan                              [Export] [×] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  # High CPU Investigation - web-server-01                       │
│  **Created:** 2026-01-17 14:32                                  │
│  **Status:** In Progress (Phase 3/5)                            │
│                                                                 │
│  ## Objective                                                   │
│  Identify and resolve high CPU usage reported on web-server-01  │
│                                                                 │
│  ## Investigation Steps                                         │
│                                                                 │
│  - [x] **Phase 1: Identify** ✅                                 │
│        Target: web-server-01, Issue: High CPU                   │
│                                                                 │
│  - [x] **Phase 2: Verify** ✅                                   │
│        OS: Ubuntu 22.04, Services: Apache2, MySQL               │
│                                                                 │
│  - [ ] **Phase 3: Investigate** 🔄 (current)                    │
│        - [x] Check process list → apache2 at 89%                │
│        - [x] Query metrics → Spike at 14:32                     │
│        - [ ] Check logs for errors                              │
│        - [ ] Review recent deployments                          │
│                                                                 │
│  - [ ] **Phase 4: Analyze**                                     │
│        Pending investigation results                            │
│                                                                 │
│  - [ ] **Phase 5: Act**                                         │
│        Will suggest remediation based on findings               │
│                                                                 │
│  ## Evidence Collected                                          │
│  | Source | Finding | Time |                                    │
│  |--------|---------|------|                                    │
│  | top | apache2: 89% CPU | 14:33 |                             │
│  | Grafana | CPU spike started 14:32 | 14:34 |                  │
│                                                                 │
│  ## Notes                                                       │
│  _Add your notes here..._                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation

**Database Schema:**
```sql
-- Already defined in AI_TERMINAL_IMPROVEMENT_PLAN.md
-- plans and plan_steps tables

-- Add index for quick lookup
CREATE INDEX idx_plans_session ON plans(session_id);
CREATE INDEX idx_plan_steps_plan ON plan_steps(plan_id);
```

**Backend Service:**
```python
# app/services/plan_service.py (NEW FILE)

from datetime import datetime
from typing import List, Optional
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models import Plan, PlanStep

class PlanService:
    """Service for managing investigation plans"""
    
    PLAN_TEMPLATE = """# {title}
**Created:** {created_at}
**Status:** {status}

## Objective
{objective}

## Investigation Steps

{steps}

## Evidence Collected
| Source | Finding | Time |
|--------|---------|------|
{evidence}

## Notes
{notes}
"""
    
    def create_plan(self, db: Session, session_id: str, title: str, objective: str) -> Plan:
        """Create a new investigation plan"""
        plan = Plan(
            id=str(uuid4()),
            session_id=session_id,
            title=title,
            status='active',
            markdown_content=self._generate_markdown(title, objective, [], []),
            created_at=datetime.utcnow()
        )
        db.add(plan)
        
        # Create default phase steps
        phases = ['identify', 'verify', 'investigate', 'plan', 'act']
        for i, phase in enumerate(phases):
            step = PlanStep(
                id=str(uuid4()),
                plan_id=plan.id,
                step_number=i + 1,
                title=f"Phase {i+1}: {phase.title()}",
                phase=phase,
                status='pending',
                created_at=datetime.utcnow()
            )
            db.add(step)
        
        db.commit()
        return plan
    
    def update_step(self, db: Session, plan_id: str, phase: str, 
                    status: str, details: str = None) -> PlanStep:
        """Update a plan step"""
        step = db.query(PlanStep).filter(
            PlanStep.plan_id == plan_id,
            PlanStep.phase == phase
        ).first()
        
        if step:
            step.status = status
            if details:
                step.description = details
            if status == 'completed':
                step.completed_at = datetime.utcnow()
            db.commit()
            
            # Regenerate markdown
            self._update_plan_markdown(db, plan_id)
        
        return step
    
    def add_evidence(self, db: Session, plan_id: str, 
                     source: str, finding: str) -> None:
        """Add evidence to the plan"""
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if plan:
            # Parse existing evidence from markdown and append
            # (simplified - in production use JSON column)
            evidence_line = f"| {source} | {finding} | {datetime.utcnow().strftime('%H:%M')} |"
            plan.markdown_content = plan.markdown_content.replace(
                "## Notes",
                f"{evidence_line}\n\n## Notes"
            )
            plan.updated_at = datetime.utcnow()
            db.commit()
    
    def get_plan_markdown(self, db: Session, plan_id: str) -> str:
        """Get the plan as markdown"""
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        return plan.markdown_content if plan else ""
    
    def export_plan(self, db: Session, plan_id: str, format: str = 'markdown') -> str:
        """Export plan in various formats"""
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            return ""
        
        if format == 'markdown':
            return plan.markdown_content
        elif format == 'json':
            return self._to_json(db, plan)
        elif format == 'html':
            import markdown
            return markdown.markdown(plan.markdown_content)
        
        return plan.markdown_content
```

**API Endpoints:**
```python
# app/routers/plan_api.py (NEW FILE)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.plan_service import PlanService

router = APIRouter(prefix="/api/plans", tags=["plans"])

@router.post("/")
async def create_plan(request: CreatePlanRequest, db: Session = Depends(get_db)):
    """Create a new investigation plan"""
    service = PlanService()
    plan = service.create_plan(db, request.session_id, request.title, request.objective)
    return {"plan_id": plan.id, "markdown": plan.markdown_content}

@router.get("/{plan_id}")
async def get_plan(plan_id: str, db: Session = Depends(get_db)):
    """Get plan details"""
    service = PlanService()
    markdown = service.get_plan_markdown(db, plan_id)
    if not markdown:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan_id": plan_id, "markdown": markdown}

@router.put("/{plan_id}/steps/{phase}")
async def update_step(plan_id: str, phase: str, request: UpdateStepRequest, 
                      db: Session = Depends(get_db)):
    """Update a plan step"""
    service = PlanService()
    step = service.update_step(db, plan_id, phase, request.status, request.details)
    return {"step_id": step.id, "status": step.status}

@router.get("/{plan_id}/export")
async def export_plan(plan_id: str, format: str = 'markdown', 
                      db: Session = Depends(get_db)):
    """Export plan in various formats"""
    service = PlanService()
    content = service.export_plan(db, plan_id, format)
    return {"format": format, "content": content}
```

**Frontend Integration:**

```javascript
// static/js/plan_panel.js (NEW FILE)

let currentPlanId = null;
let planPanelVisible = false;

function initPlanPanel() {
    // Create plan panel in the right pane area
    const planTab = document.getElementById('planTabBtn');
    if (!planTab) {
        // Add Plan tab to the tab bar
        const tabBar = document.querySelector('#dataOutputTabBtn').parentElement;
        const planTabBtn = document.createElement('button');
        planTabBtn.id = 'planTabBtn';
        planTabBtn.className = 'px-3 py-1 text-xs font-medium bg-transparent text-gray-400 border-r border-gray-600 hover:text-white hover:bg-gray-800 transition-colors';
        planTabBtn.innerHTML = '<i class="fas fa-clipboard-list mr-1"></i>Plan';
        planTabBtn.onclick = () => switchRightPane('plan');
        tabBar.insertBefore(planTabBtn, document.getElementById('agentHQTabBtn'));
    }
}

async function createPlan(sessionId, title, objective) {
    const response = await fetch('/api/plans/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, title, objective })
    });
    const data = await response.json();
    currentPlanId = data.plan_id;
    renderPlanPanel(data.markdown);
    
    // Auto-switch to plan tab
    switchRightPane('plan');
}

function renderPlanPanel(markdown) {
    const container = document.getElementById('planPaneContent');
    if (!container) return;
    
    // Use marked.js to render markdown
    container.innerHTML = `
        <div class="plan-content p-4 prose prose-invert prose-sm max-w-none">
            ${marked.parse(markdown)}
        </div>
        <div class="plan-actions p-3 border-t border-gray-700 flex justify-end gap-2">
            <button onclick="exportPlan('markdown')" class="text-xs text-gray-400 hover:text-white">
                <i class="fas fa-download mr-1"></i>Export MD
            </button>
            <button onclick="exportPlan('html')" class="text-xs text-gray-400 hover:text-white">
                <i class="fas fa-file-code mr-1"></i>Export HTML
            </button>
        </div>
    `;
}

async function updatePlanStep(phase, status, details) {
    if (!currentPlanId) return;
    
    await fetch(`/api/plans/${currentPlanId}/steps/${phase}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, details })
    });
    
    // Refresh plan display
    const response = await fetch(`/api/plans/${currentPlanId}`);
    const data = await response.json();
    renderPlanPanel(data.markdown);
}

async function exportPlan(format) {
    if (!currentPlanId) return;
    
    const response = await fetch(`/api/plans/${currentPlanId}/export?format=${format}`);
    const data = await response.json();
    
    // Download file
    const blob = new Blob([data.content], { 
        type: format === 'html' ? 'text/html' : 'text/markdown' 
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `investigation-plan.${format === 'html' ? 'html' : 'md'}`;
    a.click();
}
```

---

## Gap 4: Visual Progress Indicator

### Problem
During long investigations, users don't know where the AI is in the workflow or how long it will take.

### Current Implementation
- [progress_messages.py](../app/services/agentic/progress_messages.py): Has phase messages but no visual indicator
- No progress bar or step counter

### Solution: Progress Bar with Phase Steps

#### UI Design
```
┌─────────────────────────────────────────────────────────────────┐
│  Progress: Phase 3 of 5 - Investigating                         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░░░  60%             │
│                                                                 │
│  🔍 ──✓── ✅ ──✓── 📊 ──●── 🧠 ────── 🛠️                        │
│  Identify  Verify   Investigate  Plan    Act                    │
│                     (current)                                   │
│                                                                 │
│  ⏱️ Elapsed: 45s | Tools called: 2/2 minimum                    │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation

**Frontend Components:**

```javascript
// static/js/progress_indicator.js (NEW FILE)

const PHASES = [
    { key: 'identify', icon: '🔍', label: 'Identify' },
    { key: 'verify', icon: '✅', label: 'Verify' },
    { key: 'investigate', icon: '📊', label: 'Investigate' },
    { key: 'plan', icon: '🧠', label: 'Plan' },
    { key: 'act', icon: '🛠️', label: 'Act' }
];

let progressState = {
    currentPhase: null,
    completedPhases: [],
    toolsCalled: 0,
    startTime: null,
    visible: false
};

function initProgressIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'progressIndicator';
    indicator.className = 'progress-indicator hidden bg-gray-900/95 border border-gray-700 rounded-lg p-3 mb-4';
    indicator.innerHTML = getProgressHTML();
    
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.parentElement.insertBefore(indicator, chatMessages);
}

function getProgressHTML() {
    const currentIndex = PHASES.findIndex(p => p.key === progressState.currentPhase);
    const percentage = currentIndex >= 0 ? ((currentIndex + 1) / PHASES.length * 100) : 0;
    const elapsed = progressState.startTime ? 
        Math.floor((Date.now() - progressState.startTime) / 1000) : 0;
    
    return `
        <div class="flex justify-between items-center mb-2">
            <span class="text-sm font-medium text-gray-300">
                ${progressState.currentPhase ? 
                    `Phase ${currentIndex + 1} of ${PHASES.length} - ${PHASES[currentIndex]?.label || ''}` : 
                    'Starting investigation...'}
            </span>
            <span class="text-xs text-gray-500">${Math.round(percentage)}%</span>
        </div>
        
        <div class="progress-bar h-2 bg-gray-700 rounded-full mb-3 overflow-hidden">
            <div class="progress-fill h-full bg-gradient-to-r from-blue-600 to-purple-600 transition-all duration-500"
                 style="width: ${percentage}%"></div>
        </div>
        
        <div class="phase-steps flex justify-between items-center mb-2">
            ${PHASES.map((phase, i) => {
                const isCompleted = progressState.completedPhases.includes(phase.key);
                const isCurrent = phase.key === progressState.currentPhase;
                const isPending = !isCompleted && !isCurrent;
                
                return `
                    <div class="phase-step flex flex-col items-center ${isCurrent ? 'current' : ''} ${isCompleted ? 'completed' : ''} ${isPending ? 'pending' : ''}">
                        <div class="phase-icon text-lg ${isCompleted ? 'text-green-400' : isCurrent ? 'text-blue-400' : 'text-gray-600'}">
                            ${isCompleted ? '✓' : phase.icon}
                        </div>
                        <div class="phase-label text-[10px] ${isCurrent ? 'text-blue-400 font-medium' : 'text-gray-500'}">
                            ${phase.label}
                        </div>
                        ${isCurrent ? '<div class="text-[9px] text-blue-400">(current)</div>' : ''}
                    </div>
                    ${i < PHASES.length - 1 ? `
                        <div class="phase-connector flex-1 h-0.5 mx-1 ${isCompleted ? 'bg-green-400' : 'bg-gray-700'}"></div>
                    ` : ''}
                `;
            }).join('')}
        </div>
        
        <div class="flex justify-between text-xs text-gray-500">
            <span><i class="fas fa-clock mr-1"></i>Elapsed: ${elapsed}s</span>
            <span><i class="fas fa-wrench mr-1"></i>Tools: ${progressState.toolsCalled}/2 minimum</span>
        </div>
    `;
}

function showProgress() {
    const indicator = document.getElementById('progressIndicator');
    if (indicator) {
        indicator.classList.remove('hidden');
        progressState.visible = true;
        progressState.startTime = Date.now();
        
        // Start elapsed time updater
        progressState.elapsedInterval = setInterval(updateProgressDisplay, 1000);
    }
}

function hideProgress() {
    const indicator = document.getElementById('progressIndicator');
    if (indicator) {
        indicator.classList.add('hidden');
        progressState.visible = false;
        if (progressState.elapsedInterval) {
            clearInterval(progressState.elapsedInterval);
        }
    }
}

function updateProgress(phase, toolsCalled = null) {
    const prevPhase = progressState.currentPhase;
    
    if (prevPhase && prevPhase !== phase && !progressState.completedPhases.includes(prevPhase)) {
        progressState.completedPhases.push(prevPhase);
    }
    
    progressState.currentPhase = phase;
    
    if (toolsCalled !== null) {
        progressState.toolsCalled = toolsCalled;
    }
    
    updateProgressDisplay();
}

function updateProgressDisplay() {
    const indicator = document.getElementById('progressIndicator');
    if (indicator && progressState.visible) {
        indicator.innerHTML = getProgressHTML();
    }
}

function completeProgress() {
    // Mark all phases as completed
    progressState.completedPhases = PHASES.map(p => p.key);
    progressState.currentPhase = null;
    updateProgressDisplay();
    
    // Hide after animation
    setTimeout(hideProgress, 2000);
}

// Reset for new investigation
function resetProgress() {
    progressState = {
        currentPhase: null,
        completedPhases: [],
        toolsCalled: 0,
        startTime: null,
        visible: false
    };
}
```

**CSS Styling:**
```css
/* Progress indicator styles */
.progress-indicator {
    animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.phase-step.current .phase-icon {
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
}

.phase-step.completed .phase-icon {
    animation: checkmark 0.3s ease-out;
}

@keyframes checkmark {
    from { transform: scale(0); }
    to { transform: scale(1); }
}

.progress-fill {
    animation: shimmer 2s infinite;
    background-size: 200% 100%;
}

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}
```

**Backend Integration:**

Update the ReAct agent to emit progress events:
```python
# app/services/agentic/react_agent.py

async def stream(self, user_message: str) -> AsyncGenerator[str, None]:
    # ... existing code ...
    
    # Detect and emit phase changes
    detected_phase = PhaseDetector.detect_phase(response)
    if detected_phase != self._current_phase:
        self._current_phase = detected_phase
        yield f"[PROGRESS]{json.dumps({
            'phase': detected_phase,
            'tools_called': len(self.tool_calls_made)
        })}[/PROGRESS]"
```

---

## Implementation Priority & Timeline

| Priority | Gap | Effort | Impact | Sprint |
|----------|-----|--------|--------|--------|
| 1 | Progress Tracking (#4) | Medium | High | Sprint 1 |
| 2 | Reasoning Panel (#1) | Medium | High | Sprint 1 |
| 3 | Command Editor (#2) | Low | Medium | Sprint 2 |
| 4 | Plan Artifact (#3) | High | Medium | Sprint 2-3 |

### Sprint 1 (1 week)
- [ ] Implement progress indicator component
- [ ] Add phase detection to ReAct agent
- [ ] Create reasoning panel UI
- [ ] Emit reasoning events from backend

### Sprint 2 (1 week)
- [ ] Build command editor modal
- [ ] Add command validation endpoint
- [ ] Database schema for plans
- [ ] Plan service backend

### Sprint 3 (1 week)
- [ ] Plan panel UI
- [ ] Plan export functionality
- [ ] Integration testing
- [ ] Documentation

---

## Files to Create/Modify

### New Files
| File | Description |
|------|-------------|
| `app/services/agentic/phase_detector.py` | Detect current phase from AI output |
| `app/services/plan_service.py` | Plan management service |
| `app/routers/plan_api.py` | Plan API endpoints |
| `static/js/progress_indicator.js` | Progress bar component |
| `static/js/plan_panel.js` | Plan panel component |
| `static/js/command_editor.js` | Command editor modal |

### Modified Files
| File | Changes |
|------|---------|
| `app/services/agentic/react_agent.py` | Emit progress/reasoning events |
| `static/js/ai_chat.js` | Integrate new components |
| `templates/ai_chat.html` | Add new panel containers |
| `app/routers/chat_api.py` | Add validation endpoint |

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| User understands AI reasoning | Low (hidden) | High (visible panel) |
| Command modification rate | 0% | 20%+ users edit commands |
| Plan export usage | N/A | 30%+ sessions export plan |
| "Lost" feeling during investigation | High | Low (progress visible) |

---

## Related Documents

- [AI_TERMINAL_IMPROVEMENT_PLAN.md](./AI_TERMINAL_IMPROVEMENT_PLAN.md) - Full improvement roadmap
- [CONSOLIDATED_IMPLEMENTATION_PLAN.md](./CONSOLIDATED_IMPLEMENTATION_PLAN.md) - Overall platform plan
- [react_agent.py](../app/services/agentic/react_agent.py) - Current agent implementation
- [progress_messages.py](../app/services/agentic/progress_messages.py) - Phase definitions

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-17  
**Author:** AI Assistant
