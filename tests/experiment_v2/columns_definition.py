from pydantic import BaseModel
from typing import List, Optional

class Activity(BaseModel):
    name: str
    price: Optional[int]

class Offer(BaseModel):
    name: str
    description: str
    target_group: str  # Par exemple, "particuliers", "entreprises", "artistes", etc.
    price: Optional[int]

class MemberStatus(BaseModel):  
    status: str  # Par exemple, "membre adhérent", "artiste soutenu", "client", etc.
    description: str
    price: Optional[int]

class Contact(BaseModel):
    email: str

class Communication(BaseModel):
    facebook_likes: Optional[int]
    facebook_follower: Optional[int]
    instagram_publication: Optional[int]
    instagram_followers: Optional[int]

class Entity(BaseModel):
    association_name: str
    objectives: List[str]
    activities: List[Activity]
    offers: List[Offer]
    member_statuses: List[MemberStatus]  # Ajout des statuts des membres
    contact: Contact
    communication: Communication
    hash: str
    text_name:str