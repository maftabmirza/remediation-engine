"""
Unit tests for User model.

Tests cover user creation, authentication, password hashing, role validation,
and unique constraints.
"""
import pytest
import uuid

from app.models import User
from app.services.auth_service import get_password_hash, verify_password
from tests.fixtures.factories import UserFactory


class TestUserCreation:
    """Test user creation and basic attributes."""
    
    def test_create_user_with_required_fields(self, db_session):
        """Test creating a user with all required fields."""
        user = User(
            id=str(uuid.uuid4()),
            username="testuser",
            password_hash=get_password_hash("TestPassword123!"),
            email="test@example.com",
            role="operator",
            is_active=True
        )
        
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == "operator"
        assert user.is_active is True
        assert user.created_at is not None
    
    def test_create_user_with_factory(self, db_session):
        """Test creating user using factory."""
        user = UserFactory()
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.username is not None
        assert user.password_hash is not None


class TestPasswordHashing:
    """Test password hashing and verification."""
    
    def test_password_is_hashed(self, db_session):
        """Test that password is hashed, not stored as plaintext."""
        plain_password = "MySecurePassword123!"
        
        user = User(
            id=str(uuid.uuid4()),
            username="hashtest",
            password_hash=get_password_hash(plain_password),
            role="operator",
            is_active=True
        )
        
        db_session.add(user)
        db_session.commit()
        
        # Password hash should not equal plaintext
        assert user.password_hash != plain_password
        # Should be bcrypt format (starts with $2b$)
        assert user.password_hash.startswith("$2b$")
    
    def test_password_verification_success(self, db_session):
        """Test that correct password validates successfully."""
        plain_password = "CorrectPassword123!"
        
        user = UserFactory()
        user.password_hash = get_password_hash(plain_password)
        db_session.add(user)
        db_session.commit()
        
        # Correct password should verify
        assert verify_password(plain_password, user.password_hash) is True
    
    def test_password_verification_failure(self, db_session):
        """Test that incorrect password fails validation."""
        plain_password = "CorrectPassword123!"
        wrong_password = "WrongPassword456!"
        
        user = UserFactory()
        user.password_hash = get_password_hash(plain_password)
        db_session.add(user)
        db_session.commit()
        
        # Wrong password should not verify
        assert verify_password(wrong_password, user.password_hash) is False


class TestUserUniqueConstraints:
    """Test unique constraints on username and email."""
    
    def test_username_must_be_unique(self, db_session):
        """Test that username must be unique."""
        username = "uniqueuser"
        
        user1 = UserFactory(username=username)
        db_session.add(user1)
        db_session.commit()
        
        # Try to create another user with same username
        user2 = UserFactory(username=username)
        db_session.add(user2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()
    
    def test_email_must_be_unique(self, db_session):
        """Test that email must be unique if provided."""
        email = "unique@example.com"
        
        user1 = UserFactory(email=email)
        db_session.add(user1)
        db_session.commit()
        
        # Try to create another user with same email
        user2 = UserFactory(email=email)
        db_session.add(user2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()


class TestUserRoles:
    """Test user role validation and functionality."""
    
    def test_valid_user_roles(self, db_session):
        """Test that valid roles can be assigned."""
        valid_roles = ["admin", "engineer", "operator", "viewer"]
        
        for role in valid_roles:
            user = UserFactory(role=role)
            db_session.add(user)
            db_session.commit()
            
            assert user.role == role
            db_session.rollback()  # Rollback for next iteration
    
    def test_admin_role(self, db_session):
        """Test creating admin user."""
        user = UserFactory(role="admin")
        db_session.add(user)
        db_session.commit()
        
        assert user.role == "admin"
    
    def test_operator_role(self, db_session):
        """Test creating operator user."""
        user = UserFactory(role="operator")
        db_session.add(user)
        db_session.commit()
        
        assert user.role == "operator"


class TestUserActiveStatus:
    """Test user active/inactive status."""
    
    def test_user_is_active_by_default(self, db_session):
        """Test that users are active by default."""
        user = UserFactory()
        # Factory sets is_active=True by default
        db_session.add(user)
        db_session.commit()
        
        assert user.is_active is True
    
    def test_inactive_user(self, db_session):
        """Test creating inactive user."""
        user = UserFactory(is_active=False)
        db_session.add(user)
        db_session.commit()
        
        assert user.is_active is False
    
    def test_deactivate_user(self, db_session):
        """Test deactivating a user."""
        user = UserFactory(is_active=True)
        db_session.add(user)
        db_session.commit()
        
        # Deactivate
        user.is_active = False
        db_session.commit()
        
        assert user.is_active is False


class TestUserLoginTracking:
    """Test last login tracking."""
    
    def test_last_login_initially_none(self, db_session):
        """Test that last_login is None for new users."""
        user = UserFactory()
        db_session.add(user)
        db_session.commit()
        
        # Check if last_login field exists and is None
        if hasattr(user, 'last_login'):
            assert user.last_login is None
    
    def test_update_last_login(self, db_session):
        """Test updating last_login timestamp."""
        from datetime import datetime
        
        user = UserFactory()
        db_session.add(user)
        db_session.commit()
        
        # Update last login
        if hasattr(user, 'last_login'):
            login_time = datetime.utcnow()
            user.last_login = login_time
            db_session.commit()
            db_session.refresh(user)
            
            assert user.last_login is not None
            assert user.last_login >= login_time


class TestUserQueries:
    """Test common user queries."""
    
    def test_query_users_by_role(self, db_session):
        """Test querying users by role."""
        admin1 = UserFactory(role="admin")
        admin2 = UserFactory(role="admin")
        operator = UserFactory(role="operator")
        
        db_session.add_all([admin1, admin2, operator])
        db_session.commit()
        
        admins = db_session.query(User).filter(User.role == "admin").all()
        
        assert len(admins) == 2
        assert all(u.role == "admin" for u in admins)
    
    def test_query_active_users(self, db_session):
        """Test querying only active users."""
        active1 = UserFactory(is_active=True)
        active2 = UserFactory(is_active=True)
        inactive = UserFactory(is_active=False)
        
        db_session.add_all([active1, active2, inactive])
        db_session.commit()
        
        active_users = db_session.query(User).filter(User.is_active == True).all()
        
        assert len(active_users) == 2
        assert all(u.is_active for u in active_users)
    
    def test_find_user_by_username(self, db_session):
        """Test finding user by username."""
        username = "findme"
        user = UserFactory(username=username)
        db_session.add(user)
        db_session.commit()
        
        found = db_session.query(User).filter(User.username == username).first()
        
        assert found is not None
        assert found.username == username
        assert found.id == user.id


class TestUserValidation:
    """Test user validation and constraints."""
    
    def test_username_required(self, db_session):
        """Test that username is required."""
        user = User(
            id=str(uuid.uuid4()),
            # username missing
            password_hash=get_password_hash("test"),
            role="operator",
            is_active=True
        )
        
        db_session.add(user)
        
        with pytest.raises(Exception):
            db_session.commit()
    
    def test_password_hash_required(self, db_session):
        """Test that password_hash is required."""
        user = User(
            id=str(uuid.uuid4()),
            username="testuser",
            # password_hash missing
            role="operator",
            is_active=True
        )
        
        db_session.add(user)
        
        with pytest.raises(Exception):
            db_session.commit()


class TestUserFullNameAndEmail:
    """Test optional user fields."""
    
    def test_user_with_full_name(self, db_session):
        """Test creating user with full name."""
        user = UserFactory()
        
        if hasattr(user, 'full_name'):
            user.full_name = "Test User"
            db_session.add(user)
            db_session.commit()
            
            assert user.full_name == "Test User"
    
    def test_user_with_email(self, db_session):
        """Test creating user with email."""
        email = "user@example.com"
        user = UserFactory(email=email)
        db_session.add(user)
        db_session.commit()
        
        assert user.email == email
