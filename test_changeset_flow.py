
import asyncio
import uuid
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from app.database import SessionLocal
# Import all models to ensure SQL Alchemy registry is populated
import app.models
import app.models_application
import app.models_agent
import app.models_changeset
import app.models_revive
import app.models_knowledge
import app.models_remediation
import app.models_scheduler
import app.models_dashboards
from app.models_changeset import ChangeSet, ChangeItem
from app.services.changeset_service import ChangeSetService
from app.services.file_ops_service import FileOpsService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_changeset_flow():
    db = SessionLocal()
    try:
        # Mock FileOpsService to avoid actual SSH
        mock_file_ops = MagicMock(spec=FileOpsService)
        # Setup async methods
        mock_file_ops.create_backup = AsyncMock(return_value=True)
        mock_file_ops.write_file = AsyncMock(return_value={"status": "written"})
        mock_file_ops.read_file = AsyncMock(return_value={"content": "original content"})
        
        service = ChangeSetService(db, mock_file_ops)
        
        # Create dependencies for FK constraints
        logger.info("Creating dependencies...")
        
        # User
        user = app.models.User(username=f"test_user_{uuid.uuid4()}", password_hash="dummy")
        db.add(user)
        db.flush()
        
        # Server Credential
        server = app.models.ServerCredential(name="TestServer2", hostname="localhost", username="root", protocol="ssh")
        db.add(server)
        db.flush()
        
        # AI Session
        ai_session = app.models_revive.AISession(user_id=user.id, title="Testing Session")
        db.add(ai_session)
        db.commit()
        
        session_id = ai_session.id
        server_id = server.id
        
        logger.info("Creating Change Set...")
        cs = service.create_change_set(session_id, "Test Change Set", "Testing logic")
        logger.info(f"Created CS: {cs.id} - {cs.status}")
        
        # 2. Add Items
        logger.info("Adding items...")
        item1 = service.add_change_item(cs.id, "/tmp/test.txt", "modify", "new content", "old content")
        item2 = service.add_change_item(cs.id, "/tmp/new.txt", "create", "created content")
        
        # Verify items in DB
        db.refresh(cs)
        logger.info(f"Items count: {len(cs.items)}")
        assert len(cs.items) == 2
        
        # 3. Apply Change Set
        logger.info("Applying Change Set...")
        await service.apply_change_set(cs.id, server_id)
        
        db.refresh(cs)
        logger.info(f"CS Status after apply: {cs.status}")
        assert cs.status == 'applied'
        
        for item in cs.items:
            logger.info(f"Item {item.file_path} status: {item.status}")
            assert item.status == 'applied'
            
        # Verify Mock Calls
        assert mock_file_ops.create_backup.called
        assert mock_file_ops.write_file.call_count == 2
        
        # 4. Rollback
        logger.info("Rolling back...")
        await service.rollback_change_set(cs.id, server_id)
        
        db.refresh(cs)
        logger.info(f"CS Status after rollback: {cs.status}")
        assert cs.status == 'rolled_back'
        
        logger.info("✅ Test Passed Successfully")

    except Exception as e:
        logger.error(f"❌ Test Failed: {e}")
        db.rollback()
    finally:
        # Cleanup (optional, but good for local db)
        # db.delete(cs) ... 
        db.close()

if __name__ == "__main__":
    asyncio.run(test_changeset_flow())
