from sqlalchemy import String,ForeignKey,Boolean,Integer
from sqlalchemy.orm import Mapped,mapped_column
from backend.database import Base
from backend.models.pet import TABLE_OPTIONS
class PetTextVisibility(Base):
 __tablename__='pet_text_visibility'
 __table_args__=(TABLE_OPTIONS,)
 text_id:Mapped[str]=mapped_column(ForeignKey('pet_formal_text.id',ondelete='RESTRICT'),primary_key=True)
 pet_id:Mapped[str]=mapped_column(ForeignKey('pet_profile.id',ondelete='RESTRICT'),nullable=False)
 hidden:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
 revision:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 operation_id:Mapped[str]=mapped_column(String(64),nullable=False)
