from pydantic import BaseModel, Field
from typing import Optional, List

class Person(BaseModel):
    name: str = Field(..., description="Nom complet de la personne")
    role: Optional[str] = Field(None, description="Rôle dans l'organisation ou événement")
    email: Optional[str] = Field(None, description="Adresse email de la personne")
    phone: Optional[str] = Field(None, description="Numéro de téléphone")

class Event(BaseModel):
    name: str = Field(..., description="Nom de l'événement ou concert")
    date: Optional[str] = Field(None, description="Date de l'événement (format ISO)")
    location: Optional[str] = Field(None, description="Lieu de l'événement")
    description: Optional[str] = Field(None, description="Description ou genre de l'événement")

class Collaboration(BaseModel):
    partner_name: str = Field(..., description="Nom du partenaire ou collaborateur")
    type: Optional[str] = Field(None, description="Type de partenariat (sponsor, co-organisation, artiste invité)")
    contact: Optional[str] = Field(None, description="Contact principal pour cette collaboration")

class ConcertOrganizerGraph(BaseModel):
    hash: str 
    file_name: str
    name: str = Field(..., description="Nom officiel de l'organisation")
    legal_status: Optional[str] = Field(None, description="Statut juridique")
    registration_number: Optional[str] = Field(None, description="Numéro SIREN, RNA")
    address: Optional[str] = Field(None, description="Adresse du siège")
    country: Optional[str] = Field(None, description="Pays")
    website: Optional[str] = Field(None, description="Site web")
    email: Optional[str] = Field(None, description="Email de contact")
    phone_number: Optional[str] = Field(None, description="Numéro de téléphone")
    objectives: Optional[List[str]] = Field(None, description="Intentions et objectifs déclarés")
    offers: Optional[List[str]] = Field(None, description="Services ou activités proposés")
    events: Optional[List[Event]] = Field(None, description="Liste des événements organisés")
    people: Optional[List[Person]] = Field(None, description="Personnes associées à l'organisation")
    collaborations: Optional[List[Collaboration]] = Field(None, description="Partenaires et collaborations")
