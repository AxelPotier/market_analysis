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

def get_text(url: str) -> None:
    """
    Extracts text content from a given URL.

    :param url: The URL of the webpage to extract text from.
    :return: The extracted text content or None if an error occurs.
    """
    try:
        response = requests.get(url)
        response.encoding = 'utf-8'
        response.raise_for_status()  # Check if the request was successful
        soup = BeautifulSoup(response.text, "html.parser")
        # Remove scripts and styles before extracting text
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text()
    except Exception as e:
        print(f"Error with URL {url}: {e}")
        return None

def get_internal_links(url_base: str) -> set:
    """
    Finds all internal links on a given base URL.

    :param url_base: The base URL to find internal links from.
    :return: A set of internal links.
    """
    try:
        response = requests.get(url_base)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        links = set()
        for a_tag in soup.find_all("a", href=True):
            link = a_tag['href']
            # Combine with the base URL to get an absolute link
            full_link = urljoin(url_base, link)
            if full_link.startswith(url_base):  # Only take internal links
                links.add(full_link)
        return links
    except Exception as e:
        print(f"Error with base URL {url_base}: {e}")
        return set()

def save_dict_to_text_files(data_dict: dict, output_folder: str, base_url: str) -> None:
    """
    Save the contents of a dictionary into multiple text files.

    :param data_dict: A dictionary where the keys are URLs and values are the file contents.
    :param output_folder: Path to the folder where files will be saved.
    :param base_url: The base URL used to generate filenames.
    :return: None
    """
    # Create the folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Pattern for naming the files based on the URL
    pattern = r"{}\/(.*)".format(re.escape(base_url))

    # Iterate through the dictionary and save each value to a file
    for url, content in data_dict.items():
        file_name = re.search(pattern, url).group(1).replace('/', '_')
        # Ensure the file has a .txt extension
        if not file_name.endswith(".txt"):
            file_name += ".txt"
        # Define the full path of the file
        file_path = os.path.join(output_folder, file_name)

        # Write the content to the file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
    print(f"All files have been saved in {output_folder}")

def anonymize_text(text: str) -> str:
    """
    Anonymize sensitive information in a text, such as emails, phone 
    numbers, credit card numbers, and personal identifiers.

    :param text: The input text to anonymize.
    :return: The anonymized text.
    """
    # Mask email addresses
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[EMAIL REDACTED]', text)

    # Mask phone numbers
    text = re.sub(r'\b\d{10,}\b', '[PHONE NUMBER REDACTED]', text)  # Numbers with 10 or more digits
    text = re.sub(r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}', '[PHONE NUMBER REDACTED]', text)
    
    # Mask credit card numbers
    text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CREDIT CARD REDACTED]', text)
    
    # Mask dates (standard formats like DD/MM/YYYY or YYYY-MM-DD)
    text = re.sub(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b', '[DATE REDACTED]', text)
    text = re.sub(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b', '[DATE REDACTED]', text)

    # Mask proper names (simple example based on capitalization)
    text = re.sub(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', '[NAME REDACTED]', text)

    return text

def url_to_filename(url: str) -> str:
    """
    Converts a URL to a valid filename.

    :param url: The URL to convert.
    :return: A valid filename derived from the URL.
    """
    # Parse the URL
    parsed_url = urlparse(url)

    # Remove the scheme and domain
    path = parsed_url.path

    # Replace invalid characters
    filename = re.sub(r'[^a-zA-Z0-9_-]', '_', path.strip('/'))

    # Limit the length of the filename (e.g., 50 characters)
    filename = filename[:50]

    return filename

def get_text_from_urls(list_tuple_filename_url: List[tuple], folder_name: str, gen_filename: bool) -> None:
    """
    Retrieves all the text of the website for each URL.

    :param list_tuple_filename_url: A list of tuples (filename, url).
    :param folder_name: The name of the directory where the texts are saved.
    :param gen_filename: Generates a filename based on the URL if chosen.
    :return: None
    """
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"The folder '{folder_name}' has been created.")
    else:
        print(f"The folder '{folder_name}' already exists.")

    for file_name, url_base in list_tuple_filename_url:
        # Step 1: Find all internal links
        links = get_internal_links(url_base)
        print(f"Links found: {len(links)}")

        # Step 2: Extract the text from each page
        results = {}
        for link in links:
            print(f"Extracting text from: {link}")
            text = get_text(link)
            if text:
                results[link] = text

        # Step 3: Clean dictionary
        dic = {}
        for key, item in results.items():
            print(key)
            dic[key] = " ".join(item.split())

        # Step 4: Concatenate the texts
        text = "".join([item for key, item in dic.items()])

        # Step 5: Save the results
        if gen_filename:
            file_name = re.sub(r'[^a-zA-Z0-9_-]', '_', url_base.strip('/'))

        file_path = os.path.join(folder_name, file_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    return None

def get_text_from_url(url_base: str, file_name: str, folder_name: str) -> None:
    """
    Retrieves all the text of the website for a given URL.

    :param url_base: The base URL to retrieve text from.
    :param file_name: The name of the file to save the text.
    :param folder_name: The name of the directory where the texts are saved.
    :return: None
    """
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"The folder '{folder_name}' has been created.")
    else:
        print(f"The folder '{folder_name}' already exists.")

    # Step 1: Find all internal links
    links = get_internal_links(url_base)
    print(f"Links found: {len(links)}")

    # Step 2: Extract the text from each page
    results = {}
    for link in links:
        print(f"Extracting text from: {link}")
        text = get_text(link)
        if text:
            results[link] = text

    # Step 3: Clean dictionary
    dic = {}
    for key, item in results.items():
        print(key)
        dic[key] = " ".join(item.split())

    # Step 4: Concatenate the texts
    text = "".join([item for key, item in dic.items()])

    # Step 5: Save the results
    if file_name is None:
        file_name = re.sub(r'[^a-zA-Z0-9_-]', '_', url_base.strip('/'))

    file_path = os.path.join(folder_name, file_name)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    return None

def get_texts_from_list_dic(list_dic: List[dict], folder_name: str) -> None:
    """
    Retrieve the texts based on a dictionary with keys: filename and URL.

    :param list_dic: The list of dictionaries with the URLs and filenames to save.
    :param folder_name: The name of the folder for saving the texts.
    :return: None
    """
    for dic in list_dic:
        get_text_from_url(dic['url'], dic['file_name'], folder_name)
    return None

## --------------------------------------------------------------------
## Scrapping functions specific for "https://music-hdf.org/annuaire?tt"
##---------------------------------------------------------------------

def scrap_hdf_music() -> List[dict]:
    """
    Scraps and retrieves relevant information from hdf_music.

    :return: A list of dictionaries with the scraped information.
        with keys : name, status, localisation, functions, url_suffix, description,url,website_type,file_name 
    """
    # URL of the directory
    url_annuaire = "https://music-hdf.org/annuaire?tt"
    base_url = "https://music-hdf.org"
    response = requests.get(url_annuaire)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, "html.parser")

    # Get target HTML paragraph
    links = soup.find_all("a", class_="structure-liste")
    dic = {}

    # Get the URL and information
    list_dic_prod_live_entities = [
        (dic := get_dic_from_summary(link.text.strip())).update({"url_suffix": link.get("href")}) or dic
        for link in links if "Prod live : Organisateur" in link.text.strip()  # Only the organizer
    ]
    
    for dic in list_dic_prod_live_entities:
        url_summary = "".join([base_url, '/', dic['url_suffix']])
        response_temp = requests.get(url_summary)
        response_temp.encoding = 'utf-8'
        soup_temp = BeautifulSoup(response_temp.text, "html.parser")
        try:
            url_entity = soup_temp.find_all("a", class_='inline-link')[0].get('href')
        except:
            url_entity = None
        try:
            description = soup_temp.find("div", class_="col-5").get_text(strip=True)
        except:
            description = None

        dic.update({'description': description, "url": url_entity})
    # TODO: Tester ce bloc - ajout du type de site internet.
    [ dic.update({'website_type': get_website_type(dic['url'])}) if is_valid_url(dic['url']) else dic.update({'website_type': None}) for dic in list_dic_prod_live_entities]

    return list_dic_prod_live_entities

def get_dic_from_summary(text: str) -> dict:
    """
    Retrieves the summaries about the entities in the directory of hdf.

    :param text: A summary of the entity.
    :return: A dictionary with the extracted information.
    """
    # Clean the text by removing unnecessary characters
    text = text.replace("\xa0", " ").strip()
    
    # Extract the name (first element before the status)
    match_name = re.match(r"^(.*?)\s+\n", text)
    name = match_name.group(1).strip() if match_name else ""

    # Extract the status (word between the name and 'à Lieu')
    match_status = re.search(r"\n\s*(.*?)\s*\n\s*à", text)
    status = match_status.group(1).strip() if match_status else ""

    # Extract the location (after 'à' and before the functions)
    match_location = re.search(r"à\s*([^\n]+)", text)
    location = match_location.group(1).strip() if match_location else ""

    # Extract the functions (everything that follows)
    functions = re.findall(r"×\s*(.*?)\s*(?:\n|$)", text)
    functions_str = ", ".join(functions)

    # Add the extracted data to the dictionary
    dic = {'name': name, 'status': status, 
           'localisation': location, 'functions': functions_str,
           # TODO: Tester ce bloc - ajout du traitement des erreurs réseau
           'file_name': sanitize_filename(dic['name']) } 

    return dic

def sanitize_filename(filename, max_length=255):
    # Définition des caractères interdits (Windows + Linux)
    forbidden_chars = r'[\/:*?"<>|]'  
    # Remplace les caractères interdits par "_"
    sanitized = re.sub(forbidden_chars, "_", filename)
    # Remplace les espaces multiples par un seul underscore
    sanitized = re.sub(r'\s+', '_', sanitized).strip('_')
    # Tronque si dépasse la longueur max (255 en général)
    return sanitized[:max_length]
    


def get_website_type(url):
    # Dictionnaire de classification des sites
    SITE_CATEGORIES = {
        "facebook.com": "Facebook",
        "instagram.com": "Instagram",
        "twitter.com": "Twitter",
        "linkedin.com": "LinkedIn",
        "youtube.com": "YouTube",
        "tiktok.com": "TikTok",
        "soundcloud.com": "SoundCloud",
        "bandcamp.com": "Bandcamp"
    }
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace("www.", "")  # Supprime "www." si présent
    return SITE_CATEGORIES.get(domain, "Site personnel")  # Si inconnu, classé en "Site personnel"

def is_valid_url(url):
    return validators.url(url)  # Retourne True si valide, sinon False