# Database Schema Change Cheat Sheet

**Q: Do I modify the python models code first?**
**A: YES!** The Python code (`app/models_*.py`) is the source of truth.

---

## 1. The Workflow

1.  **Modify Python Code**
    *   Open `app/models_remediation.py` (or other model files)
    *   Add/Remove/Modify columns using SQLAlchemy syntax
    *   Example: `new_column = Column(String(50))`

2.  **Generate Migration** (Inside Docker)
    *   Run: `docker exec -it remediation-engine alembic revision --autogenerate -m "Add new_column"`
    *   This compares your *new Python code* vs *current Database* and writes the difference to a new file in `alembic/versions/`.

3.  **Apply Migration** (Inside Docker)
    *   Run: `docker exec -it remediation-engine alembic upgrade head`
    *   This runs the new migration script to update the database schema.

4.  **Commit**
    *   Commit both the `models_*.py` file AND the new `alembic/versions/*.py` file.

---

## 2. Example: Adding a "Notes" Column

**Step 1:** Edit `app/models_remediation.py`:
```python
class Runbook(Base):
    # ... existing fields ...
    notes = Column(Text, nullable=True)  # <--- YOU ADD THIS
```

**Step 2:** Generate Migration:
```bash
docker exec -it remediation-engine alembic revision --autogenerate -m "add notes column"
```

**Step 3:** Apply:
```bash
docker exec -it remediation-engine alembic upgrade head
```

**Step 4:** Deploy (Production):
*   `git pull`
*   `docker-compose restart remediation-engine` (Auto-runs migration!)

---

## 3. Key Commands

| Action | Command |
| :--- | :--- |
| **Check Current Version** | `docker exec -it remediation-engine alembic current` |
| **Show History** | `docker exec -it remediation-engine alembic history` |
| **Upgrade DB** | `docker exec -it remediation-engine alembic upgrade head` |
| **Undo Last Change** | `docker exec -it remediation-engine alembic downgrade -1` |
