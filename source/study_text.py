import os
from pydantic import BaseModel
from typing import List, Optional
from mistralai import Mistral
from pathlib import Path
import json 


## 
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

class Association(BaseModel):
    association_name: str
    objectives: List[str]
    activities: List[Activity]
    offers: List[Offer]
    member_statuses: List[MemberStatus]  # Ajout des statuts des membres
    contact: Contact
    communication: Communication




def read_files_from_folder(folder):
    files = [f for f in os.listdir(folder) if f.endswith('.txt')]
    file_contents = {}
    for file in files:
        file_path = os.path.join(folder, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            file_contents[file] = f.read()
    return file_contents


def study_text(
        folder_name : str
         ):
    '''
    Objective : retrieves the  texts and outputs the json.
    
    '''
    
    ## settings of mistral
    api_key = "wm1af0pJ92Pj1tLbTSztHxeey62ru479"
    model = "mistral-large-latest"

    # Retrieving the prompt
    chemin_du_script = Path(__file__).parent  # Cela donne le chemin du fichier study_text.py
    chemin_prompt = "../source/prompt.txt"

    with open(chemin_prompt,"r",encoding="utf-8") as f:
        prompt = f.read()

    list_dic = []
    for file in os.listdir(folder_name):

        # Retrieving the text
        file_path = os.path.join(folder_name,file)
        if os.path.isfile(file_path):
            with open(file_path,'r',encoding='utf-8') as f:
                text = f.read()
        print(text[:10])

        client = Mistral(api_key=api_key)
        

        chat_response = client.chat.parse(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": prompt
                },
                {
                    "role": "user", 
                    "content": text
                },
            ],
            response_format=Association
        )
        dic = json.loads(chat_response.choices[0].message.content)
        list_dic.append(dic)
    return list_dic