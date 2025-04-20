from pydantic import BaseModel
from typing import List, Optional

class Events(BaseModel):
    name: str
    price: Optional[int]
    nb_participants : Optional[int]
    date : Optional[str]
    description: Optional[str]
    music_type : Optional[str]

class Offer(BaseModel):
    name: str
    description: str
    target_group: str  # Par exemple, "particuliers", "entreprises", "artistes", etc.
    price: Optional[int]

class Neologisms(BaseModel):
    name: str
    interpretation : str
    components : List[str]

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
    events: List[Events]
    offers: List[Offer]
    member_statuses: List[MemberStatus]  # Ajout des statuts des membres
    neologisms: List[Neologisms]
    contact: Contact
    communication: Communication
    hash: str
    file_name:str
