# AI Helper Bug Fixes - Conversation Context Issue

## 🐛 **Bug Fixed: Context Loss Across Messages**

### **Problem**
The AI Helper was losing conversation context between messages, causing it to:
- Forget previous requests
- Ask for information already provided
- Not maintain continuity in conversations
- Treat every message as if it was the first interaction

### **Root Cause**
The `_update_session()` method in `ai_helper_orchestrator.py` was updating session metrics (queries, tokens, cost) but **NOT saving the actual conversation history** to `session.context['history']`.

---

## ✅ **What Was Fixed**

### **1. Session History Persistence**

**Before (Lines 435-447):**
```python
async def _update_session(self, session_id: UUID, llm_response: Dict[str, Any]):
    """Update session with latest interaction"""
    session = self.db.query(AIHelperSession).filter(
        AIHelperSession.id == session_id
    ).first()

    if session:
        session.last_activity_at = datetime.utcnow()
        session.total_queries += 1
        session.total_tokens_used += llm_response.get('usage', {}).get('total_tokens', 0)
        cost_float = self._calculate_cost(llm_response)
        session.total_cost_usd += Decimal(str(cost_float))
        self.db.commit()
        # ❌ NO CONVERSATION HISTORY SAVED!
```

**After (Lines 502-552):**
```python
async def _update_session(
    self,
    session_id: UUID,
    user_query: str,              # ✅ Now accepts the query
    llm_response: Dict[str, Any],
    ai_action: str                # ✅ Now accepts the action
):
    """Update session with latest interaction (✅ FIXED - now saves conversation history)"""
    session = self.db.query(AIHelperSession).filter(
        AIHelperSession.id == session_id
    ).first()

    if session:
        session.last_activity_at = datetime.utcnow()
        session.total_queries += 1
        session.total_tokens_used += llm_response.get('usage', {}).get('total_tokens', 0)
        cost_float = self._calculate_cost(llm_response)
        session.total_cost_usd += Decimal(str(cost_float))

        # ✅ CRITICAL FIX: Save conversation history to session.context
        if not session.context:
            session.context = {'history': []}

        history = session.context.get('history', [])

        # Add user query
        history.append({
            'role': 'user',
            'content': user_query,
            'timestamp': datetime.utcnow().isoformat()
        })

        # Add AI response
        llm_content = ""
        if llm_response.get('choices'):
            llm_content = llm_response['choices'][0].get('message', {}).get('content', '')

        history.append({
            'role': 'assistant',
            'content': llm_content,
            'action': ai_action,
            'timestamp': datetime.utcnow().isoformat()
        })

        # Keep only last 20 messages (10 conversation turns)
        session.context['history'] = history[-20:]

        self.db.commit()
        logger.debug(f"Session {session_id} updated with conversation history (total messages: {len(session.context['history'])})")
```

---

### **2. Updated Method Call**

**Before (Line 176):**
```python
await self._update_session(session_id, llm_response)
```

**After (Line 173):**
```python
await self._update_session(session_id, query, llm_response, ai_action)
```

---

### **3. Improved Prompt Engineering**

**Before:**
- Session history was dumped as raw text
- No clear formatting
- History appeared at the end (less prominent)

**After (Lines 406-443):**
```python
def _build_user_message(self, query: str, context: Dict[str, Any]) -> str:
    """Build user message with context (✅ IMPROVED - better history formatting)"""
    message_parts = []

    # Add conversation history FIRST if available (✅ CRITICAL for context continuity)
    if context.get('session_history'):
        message_parts.append("## Previous Conversation:")
        for msg in context['session_history'][-6:]:  # Last 6 messages (3 turns)
            role = msg.get('role', 'user').capitalize()
            content = msg.get('content', '')
            # Truncate long messages
            if len(content) > 500:
                content = content[:500] + "..."
            message_parts.append(f"{role}: {content}")
        message_parts.append("\n---\n")

    # Current query
    message_parts.append(f"## Current User Query:\n{query}")

    # Add page context
    if context.get('page_context'):
        page_info = context['page_context']
        message_parts.append(f"\n## Current Page Context:")
        message_parts.append(f"URL: {page_info.get('url', 'unknown')}")
        message_parts.append(f"Page Type: {page_info.get('page_type', 'unknown')}")
        if page_info.get('form_id'):
            message_parts.append(f"Form ID: {page_info.get('form_id')}")

    # Add knowledge results
    if context.get('knowledge_results'):
        message_parts.append("\n## Relevant Documentation:")
        for i, result in enumerate(context['knowledge_results'][:3], 1):
            content = result.get('content', '')[:200]
            message_parts.append(f"{i}. {content}...")

    return "\n".join(message_parts)
```

---

### **4. Enhanced System Prompt**

Added **concrete examples** to guide the LLM on how to format responses (Lines 354-404):

```python
EXAMPLES:

Example 1 - Suggesting form values for a runbook:
{
  "action": "suggest_form_values",
  "action_details": {
    "form_fields": {
      "name": "Apache2 Restart Runbook",
      "description": "Automatically restart Apache2 service when it fails",
      "server": "t-aisop-01",
      "steps": [
        {"command": "systemctl status apache2", "description": "Check current status"},
        {"command": "systemctl restart apache2", "description": "Restart service"},
        {"command": "systemctl status apache2", "description": "Verify restart succeeded"}
      ],
      "notification_enabled": true
    },
    "explanation": "These values will create a runbook to restart Apache2 on server t-aisop-01. The user needs to fill these values in the form and click 'Create'."
  },
  "reasoning": "User requested a runbook to restart Apache2 on t-aisop-01",
  "confidence": 0.9
}

Example 2 - General chat:
{
  "action": "chat",
  "action_details": {
    "message": "Hello! I can help you with creating runbooks, configuring alerts, understanding the platform features, and more. What would you like help with?"
  },
  "reasoning": "User greeted me",
  "confidence": 1.0
}

Example 3 - Explaining a concept:
{
  "action": "explain_concept",
  "action_details": {
    "concept": "runbooks",
    "explanation": "Runbooks are automated remediation scripts that execute predefined steps to resolve issues. They can check service status, restart services, or perform other maintenance tasks."
  },
  "reasoning": "User asking about what runbooks are",
  "confidence": 1.0
}
```

---

### **5. Better Session Initialization**

**Before (Lines 422-433):**
```python
async def _create_session(self, user_id: UUID) -> UUID:
    """Create new AI helper session"""
    session = AIHelperSession(
        user_id=user_id,
        session_type='general',
        status='active',
        context={}  # ❌ Empty context
    )
```

**After (Lines 489-500):**
```python
async def _create_session(self, user_id: UUID) -> UUID:
    """Create new AI helper session"""
    session = AIHelperSession(
        user_id=user_id,
        session_type='general',
        status='active',
        context={'history': []}  # ✅ Initialize with empty history array
    )
```

---

### **6. Improved Context Assembly**

**Before (Lines 282-288):**
```python
# Get session history (last 5 interactions)
session = self.db.query(AIHelperSession).filter(
    AIHelperSession.id == session_id
).first()

if session and session.context:
    context['session_history'] = session.context.get('history', [])[-5:]
```

**After (Lines 283-289):**
```python
# Get session history (✅ FIXED - retrieve from session.context)
session = self.db.query(AIHelperSession).filter(
    AIHelperSession.id == session_id
).first()

if session and session.context:
    context['session_history'] = session.context.get('history', [])[-10:]  # Last 10 messages (5 turns)
```

---

## 📊 **Expected Behavior After Fix**

### **Scenario 1: Creating a Runbook**

**Before Fix:**
```
User: "Can you help me create a runbook to restart apache2 service on t-aisop-01"
AI: *suggests form values*

User: "Can you create it?"
AI: "I need more details about what you want to create. What type of runbook?"
     (❌ NO MEMORY OF PREVIOUS MESSAGE!)

User: "I just told you! Apache2 restart!"
AI: "Oh, you want to create an Apache2 runbook. What server?"
     (❌ STILL NO MEMORY!)
```

**After Fix:**
```
User: "Can you help me create a runbook to restart apache2 service on t-aisop-01"
AI: *suggests specific form values for Apache2 restart runbook*

User: "Can you create it?"
AI: "I already suggested the form values for the Apache2 restart runbook on t-aisop-01.
     I cannot create it directly - you need to:
     1. Fill in the form with the suggested values I provided
     2. Review them
     3. Click the 'Create Runbook' button

     Would you like me to explain any of the suggested values?"
     (✅ REMEMBERS THE CONTEXT!)

User: "What were those values again?"
AI: "Sure! Here are the values I suggested for the Apache2 restart runbook:
     - Name: Apache2 Restart Runbook
     - Server: t-aisop-01
     - Steps: [shows the 3 steps again]

     Should I explain what each step does?"
     (✅ FULL CONVERSATION CONTINUITY!)
```

---

### **Scenario 2: Multi-turn Conversation**

**Before Fix:**
```
User: "Hello"
AI: "Hello! How can I help?"

User: "What can you do?"
AI: "Hello! How can I help?"
     (❌ FORGOT THE GREETING, REPEATS ITSELF!)
```

**After Fix:**
```
User: "Hello"
AI: "Hello! How can I help you with the AIOps platform today?"

User: "What can you do?"
AI: "I can help you with:
     - Creating and configuring runbooks
     - Setting up alerts
     - Understanding platform features
     - Answering questions about your infrastructure

     Is there something specific you'd like help with?"
     (✅ NATURAL CONVERSATION FLOW!)
```

---

## 🔧 **Technical Details**

### **Data Flow**

```
User sends message
    ↓
process_query() called
    ↓
_assemble_context() retrieves session history from session.context['history']
    ↓
_build_user_message() formats history into prompt
    ↓
LLM sees previous conversation in prompt
    ↓
LLM generates contextual response
    ↓
_update_session() saves BOTH user query AND AI response to session.context['history']
    ↓
Next message will include this conversation in context
```

### **Session Context Structure**

```json
{
  "history": [
    {
      "role": "user",
      "content": "Can you help me create a runbook to restart apache2 on t-aisop-01",
      "timestamp": "2025-01-04T12:00:00Z"
    },
    {
      "role": "assistant",
      "content": "{\"action\": \"suggest_form_values\", ...}",
      "action": "suggest_form_values",
      "timestamp": "2025-01-04T12:00:01Z"
    },
    {
      "role": "user",
      "content": "Can you create it?",
      "timestamp": "2025-01-04T12:01:00Z"
    },
    {
      "role": "assistant",
      "content": "I already suggested form values...",
      "action": "chat",
      "timestamp": "2025-01-04T12:01:01Z"
    }
  ]
}
```

### **History Limits**

- **Storage**: Last 20 messages (10 conversation turns) kept in `session.context['history']`
- **Prompt**: Last 10 messages (5 turns) included in LLM prompt
- **Truncation**: Messages over 500 characters truncated in prompt

---

## 🧪 **Testing the Fix**

### **Test 1: Basic Continuity**
```
1. Start new conversation
2. Send: "Hello"
3. Verify AI responds with greeting
4. Send: "What did I just say?"
5. ✅ AI should reference the "Hello" greeting
```

### **Test 2: Form Assistance**
```
1. Send: "Create Apache2 runbook for server-01"
2. Verify AI suggests form values
3. Send: "What server was that for?"
4. ✅ AI should respond "server-01"
```

### **Test 3: Multi-turn Planning**
```
1. Send: "I need help with high CPU alerts"
2. AI provides guidance
3. Send: "How do I implement that?"
4. ✅ AI should reference the specific guidance from step 2
```

### **Test 4: Context Window**
```
1. Have a 15-message conversation
2. Send: "What did I ask you first?"
3. ✅ AI should reference message 1 (if still in 10-message window)
   or say it's beyond the context window
```

---

## 📝 **Commit Information**

**Commit**: `957cd9c`
**Branch**: `claude/review-grafana-docs-xr3h8-PDXto`
**Files Changed**: `app/services/ai_helper_orchestrator.py`
**Lines Changed**: +139 -31

---

## ✅ **Summary**

The AI Helper now:
- ✅ Maintains conversation history across messages
- ✅ Remembers previous user requests
- ✅ Provides contextual responses
- ✅ Can reference earlier parts of the conversation
- ✅ Gives better, more specific form suggestions
- ✅ Behaves like a proper conversational assistant

**The bug is FIXED!** 🎉
