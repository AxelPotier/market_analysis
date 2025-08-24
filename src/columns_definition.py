from pydantic import BaseModel, Field
from typing import Optional, List

class Person(BaseModel):
    name: str = Field(..., description="Nom complet de la personne")
    role: Optional[str] = Field("", description="Rôle dans l'organisation ou événement")
    email: Optional[str] = Field("", description="Adresse email de la personne")
    phone: Optional[str] = Field("", description="Numéro de téléphone")

class Event(BaseModel):
    name: str = Field(..., description="Nom de l'événement ou concert")
    date: Optional[str] = Field("", description="Date de l'événement (format ISO)")
    location: Optional[str] = Field("", description="Lieu de l'événement")
    description: Optional[str] = Field("", description="Description ou genre de l'événement")

class Collaboration(BaseModel):
    partner_name: str = Field(..., description="Nom du partenaire ou collaborateur")
    type: Optional[str] = Field("", description="Type de partenariat (sponsor, co-organisation, artiste invité)")
    contact: Optional[str] = Field("", description="Contact principal pour cette collaboration")

class ConcertOrganizerGraph(BaseModel):
    hash: str 
    file_name: str
    name: str = Field(..., description="Nom officiel de l'organisation")
    legal_status: Optional[str] = Field("", description="Statut juridique")
    registration_number: Optional[str] = Field("", description="Numéro SIREN, RNA")
    address: Optional[str] = Field("", description="Adresse du siège")
    country: Optional[str] = Field("", description="Pays")
    website: Optional[str] = Field("", description="Site web")
    email: Optional[str] = Field("", description="Email de contact")
    phone_number: Optional[str] = Field("", description="Numéro de téléphone")
    objectives: Optional[List[str]] = Field([], description="Intentions et objectifs déclarés")
    offers: Optional[List[str]] = Field([], description="Services ou activités proposés")
    events: Optional[List[Event]] = Field([], description="Liste des événements organisés")
    people: Optional[List[Person]] = Field([], description="Personnes associées à l'organisation")
    collaborations: Optional[List[Collaboration]] = Field([], description="Partenaires et collaborations")
