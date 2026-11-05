"""Durable account deletion fence; retained until the owning account is removed."""
from sqlalchemy import BigInteger,String
from sqlalchemy.orm import Mapped,mapped_column
from backend.database import Base
from backend.models.pet import TABLE_OPTIONS
PET_LIFECYCLE_TABLE_NAMES=frozenset({'pet_account_lifecycle'})
class PetAccountLifecycle(Base):
 __tablename__='pet_account_lifecycle'
 __table_args__=(TABLE_OPTIONS,)
 user_id:Mapped[int]=mapped_column(BigInteger,primary_key=True)
 operation_id:Mapped[str]=mapped_column(String(96),nullable=False)
 state:Mapped[str]=mapped_column(String(24),nullable=False)
