## A module with my functions for the query of url
import requests
from bs4 import BeautifulSoup
import pandas as pd
import pickle
import numpy as np
from urllib.parse import urljoin
import os
from typing import List
import re
from urllib.parse import urlparse

# # URL de base
# url_base = 'https://www.artpointm.com/'

# Fonction pour extraire le texte d'une page donnée
def get_text(
        url: str
        )-> None:
    try:
        response = requests.get(url)
        response.encoding = 'utf-8'
        response.raise_for_status()  # Vérifie si la requête a réussi
        soup = BeautifulSoup(response.text, "html.parser")
        # Supprimer les scripts et styles avant d'extraire le texte
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text()
    except Exception as e:
        print(f"Erreur avec l'URL {url}: {e}")
        return None

# Fonction pour trouver tous les liens internes
def get_internal_links(url_base):
    try:
        response = requests.get(url_base)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        liens = set()
        for a_tag in soup.find_all("a", href=True):
            lien = a_tag['href']
            # Combiner avec l'URL de base pour obtenir un lien absolu
            lien_complet = urljoin(url_base, lien)
            if lien_complet.startswith(url_base):  # Ne prendre que les liens internes
                liens.add(lien_complet)
        return liens
    except Exception as e:
        print(f"Erreur avec l'URL de base {url_base}: {e}")
        return set()


def save_dict_to_text_files(data_dict, output_folder, base_url):
    """
    Save the contents of a dictionary into multiple text files.

    Args:
        data_dict (dict): A dictionary where the keys are filenames
        and values are the file contents.
        
        output_folder (str): Path to the folder where files will be saved.

    Returns:
        None
    """
    # Create the folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # pattern for naming the files based on the url.
    pattern = r"{}\/(.*)".format(re.escape(base_url))

    # Iterate through the dictionary and save each value to a file
    for url, content in data_dict.items():
        file_name = re.search(pattern, url).group(1).replace('/','_')
        # Ensure the file has a .txt extension
        if not file_name.endswith(".txt"):
            file_name += ".txt"
        # Define the full path of the file
        file_path = os.path.join(output_folder, file_name)

        # Write the content to the file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
    print(f"All files have been saved in {output_folder}")


def anonymize_text(text):
    """
    Anonymize sensitive information in a text, such as emails, phone 
        numbers, credit card numbers, and personal identifiers.
    Args:
        text (str): The input text to anonymize.

    Returns:
        str: The anonymized text.
    """
    # Mask email addresses
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[EMAIL REDACTED]', text)

    # Mask phone numbers
    text = re.sub(r'\b\d{10,}\b', '[PHONE NUMBER REDACTED]', text)  # Numbers with 10 or more digits
    text = re.sub(r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}', \
                  '[PHONE NUMBER REDACTED]', text)
    # Mask credit card numbers
    text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CREDIT CARD REDACTED]', text)
    # Mask dates (standard formats like DD/MM/YYYY or YYYY-MM-DD)
    text = re.sub(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b', '[DATE REDACTED]', text)
    text = re.sub(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b', '[DATE REDACTED]', text)

    # Mask proper names (simple example based on capitalization)
    text = re.sub(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', '[NAME REDACTED]', text)

    return text




def url_to_filename(url):
    # Analyser l'URL
    parsed_url = urlparse(url)

    # Supprimer le schéma et le domaine
    path = parsed_url.path

    # Remplacer les caractères non valides
    filename = re.sub(r'[^a-zA-Z0-9_-]', '_', path.strip('/'))

    # Limiter la longueur du nom de fichier (par exemple, 50 caractères)
    filename = filename[:50]

    return filename


def get_text_from_urls(
        list_tuple_filename_url : List[tuple],
        folder_name : str,
        gen_filename :bool
        )-> None:
    '''
    Objective: retrieves all the text of the website for each url.

    Params : list_tuple_url_filename : is a list of tuple
            (filename,url).
            folder_name : is the name of the directory where
            the texts are saved.
            gen_filename : Generates a filename based on the url if chosen.
    '''
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"Le dossier '{folder_name}' a été créé.")
    else:
        print(f"Le dossier '{folder_name}' existe déjà.")

    for file_name,url_base in list_tuple_filename_url:
        # Étape 1 : Trouver tous les liens internes
        liens = get_internal_links(url_base)
        print(f"Liens trouvés : {len(liens)}")

        # Étape 2 : Extraire le texte de chaque page
        resultats = {}
        for lien in liens:
            print(f"Extraction du texte de : {lien}")
            texte = get_text(lien)
            if texte:
                resultats[lien] = texte

        ## Etape 3 : clean dictionnary
        dic = {}
        for key, item in resultats.items():
            print(key)
            dic[key] = " ".join(item.split())


        ## Etape 4 : concatenate the texts
        text = "".join([ item for key, item in dic.items() ])
        
        ## Etape 5 : Save the results.
        # file_name = url_to_filename(url_base)

        ## generation of the name based on the url.
        if gen_filename:
            file_name = re.sub(r'[^a-zA-Z0-9_-]', '_', url_base.strip('/'))

        file_path = os.path.join(folder_name, file_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    return None




def get_text_from_url(
        url_base :str,
        file_name:str,
        folder_name : str
        )-> None:
    '''
    Objective: retrieves all the text of the website for each url.

    Params : list_tuple_url_filename : is a list of tuple
            (filename,url).
            folder_name : is the name of the directory where
            the texts are saved.
            gen_filename : Generates a filename based on the url if chosen.
    '''
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"Le dossier '{folder_name}' a été créé.")
    else:
        print(f"Le dossier '{folder_name}' existe déjà.")

    # Étape 1 : Trouver tous les liens internes
    liens = get_internal_links(url_base)
    print(f"Liens trouvés : {len(liens)}")

    # Étape 2 : Extraire le texte de chaque page
    resultats = {}
    for lien in liens:
        print(f"Extraction du texte de : {lien}")
        texte = get_text(lien)
        if texte:
            resultats[lien] = texte

    ## Etape 3 : clean dictionnary
    dic = {}
    for key, item in resultats.items():
        print(key)
        dic[key] = " ".join(item.split())


    ## Etape 4 : concatenate the texts
    text = "".join([ item for key, item in dic.items() ])
    
    ## Etape 5 : Save the results.
    # file_name = url_to_filename(url_base)

    ## generation of the name based on the url.
    if file_name is None:
        file_name = re.sub(r'[^a-zA-Z0-9_-]', '_', url_base.strip('/'))

    file_path = os.path.join(folder_name, file_name)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    return None


def get_texts_from_list_dic(
        list_dic : List[dict],
        folder_name:str
    )-> None:
    '''
    Objective : Retrieve the texts based on a dictionary with keys: 
    filename and url.

    Parameters:
        list_dic: the list of dictionnaries with the urls and filename 
        to save.
        folder_name: the name of the folder for saving the texts.    
    '''
    for dic in list_dic:
        get_text_from_url(dic['url'],dic['file_name'], folder_name)
    return None



## --------------------------------------------------------------------
## Scrapping functions specific for "https://music-hdf.org/annuaire?tt"
##---------------------------------------------------------------------

def scrap_hdf_music():
    '''
    Objective : Scraps and retrieve relevants informations from hdf_music.
    '''

    ## url_hdf
    url_annuaire = "https://music-hdf.org/annuaire?tt"
    base_url = "https://music-hdf.org"
    response = requests.get(url_annuaire)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, "html.parser")

    ## Get target html paragraph
    liens = soup.find_all("a", class_="structure-liste")
    dic={}

    ## get the url and informations
    list_dic_prod_live_entities = [
        (dic := get_dic_from_summary(lien.text.strip())).update({"url_suffix": lien.get("href")}) or dic
        for lien in liens if "Prod live : Organisateur" in lien.text.strip() ## !!Only the organizer of
        ]
    
    for dic in list_dic_prod_live_entities:
        url_summary="".join([base_url,'/',dic['url_suffix']])
        response_temp = requests.get(url_summary)
        response_temp.encoding = 'utf-8'
        soup_temp = BeautifulSoup(response_temp.text, "html.parser")
        try :
            url_entity = soup_temp.find_all("a", class_='inline-link')[0].get('href')
        except:
            url_entity = None
        try:
            description = soup_temp.find("div", class_="col-5").get_text(strip=True)
        except:
            description=None

        dic.update({'description': description, "url":url_entity})

    return list_dic_prod_live_entities
    

def get_dic_from_summary(text):
    '''
    Objective : function that retrieves the summaries about the
    entities in the directory of hdf.

    Parameters : text is a summary of the entity. 
    '''
    # Nettoyage du texte en supprimant les caractères inutiles
    text = text.replace("\xa0", " ").strip()
    
    # Extraction du nom (premier élément avant le statut)
    match_nom = re.match(r"^(.*?)\s+\n", text)
    nom = match_nom.group(1).strip() if match_nom else ""

    # Extraction du statut (mot entre le nom et 'à Lieu')
    match_statut = re.search(r"\n\s*(.*?)\s*\n\s*à", text)
    statut = match_statut.group(1).strip() if match_statut else ""

    # Extraction du lieu (après 'à' et avant les fonctions)
    match_lieu = re.search(r"à\s*([^\n]+)", text)
    lieu = match_lieu.group(1).strip() if match_lieu else ""

    # Extraction des fonctions (tout ce qui suit)
    fonctions = re.findall(r"×\s*(.*?)\s*(?:\n|$)", text)
    fonctions_str = ", ".join(fonctions)

    # Ajouter les données extraites à la liste
    dic = { 'name': nom, 'status' : statut, 'localisation': lieu, 'functions' : fonctions_str } 

    return dic

