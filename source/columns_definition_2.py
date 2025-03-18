from pydantic import BaseModel
from typing import List, Optional
import json


class Activity(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None

class Offer(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_group: Optional[str] = None
    price: Optional[int] = None

class MemberStatus(BaseModel):
    status: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None

class Contact(BaseModel):
    email: Optional[str] = None

class Communication(BaseModel):
    facebook_likes: Optional[int] = None
    facebook_follower: Optional[int] = None
    instagram_publication: Optional[int] = None
    instagram_followers: Optional[int] = None

class Entity(BaseModel):
    association_name: Optional[str] = None
    objectives: List[str] = []
    activities: List[Activity] = []
    offers: List[Offer] = []
    member_statuses: List[MemberStatus] = []
    contact: Contact = Contact()
    communication: Communication = Communication()
    hash: Optional[str] = None
    text_name: Optional[str] = None

def save_entity_to_json(entity: Entity, file_path: str):
    # Convert the Entity object to a JSON string
    entity_json = entity.model_dump_json(indent=2)

    # Write the JSON string to a file
    with open(file_path, 'w') as file:
        file.write(entity_json)


def remove_none_values(data):
    if isinstance(data, dict):
        return {k: remove_none_values(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [remove_none_values(i) for i in data]
    else:
        return data