import os
from typing import List, Optional
from mistralai import Mistral
from pathlib import Path
import json 
import pandas as pd
import pickle
import hashlib

## the output format to be used
# ---------------------------
from columns_definition_new import Entity 
# ----------------------------
from langchain.text_splitter import CharacterTextSplitter

def read_files_from_folder(folder: str) -> dict:
    """
    Reads all text files from a specified folder and returns their contents.

    :param folder: Path to the folder containing text files.
    :return: Dictionary with filenames as keys and file contents as values.
    """
    files = [f for f in os.listdir(folder) if f.endswith('.txt')]
    file_contents = {}
    for file in files:
        file_path = os.path.join(folder, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            file_contents[file] = f.read()
    return file_contents

class StudyText:
    """
    A class to study and analyze text files using the Mistral model.
    
    Attributes:
        prompt (str): The prompt text used for analysis.
        cache_file (str): The file path for caching results.
        df (pd.DataFrame): DataFrame to store analysis results.
    """

    def __init__(self, path_prompt: str, cache_file: str = "df.p"):
        """
        Initializes the StudyText class with a prompt and cache file.

        :param path_prompt: Path to the prompt file.
        :param cache_file: Path to the cache file (default is "df.p").
        """
        with open(path_prompt, "r", encoding="utf-8") as f:
            self.prompt = f.read()

        self.cache_file = cache_file
        self.load_results()

    def update_prompt(self, path_prompt: str) -> None:
        """
        Updates the prompt text from a specified file.

        :param path_prompt: Path to the new prompt file.
        """
        with open(path_prompt, "r", encoding="utf-8") as f:
            self.prompt = f.read()

    def load_results(self) -> None:
        """
        Loads existing results from the cache file to avoid recalculating.
        """
        if os.path.exists(self.cache_file):
            self.df = pickle.load(open(self.cache_file, 'rb'))
        else:
            self.df = pd.DataFrame(columns=Entity.model_fields.keys())
        return None

    def save_results(self) -> None:
        """
        Saves the current results to the cache file.
        """
        pickle.dump(self.df, open(self.cache_file, 'wb'))
        return None

    def compute_hash(self, text: str) -> str:
        """
        Computes a unique hash for a given text.

        :param text: The text to hash.
        :return: The SHA-256 hash of the text.
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def analyze_texts_in_folder(self, folder_path: str) -> None:
        """
        Analyzes all text files in a specified folder.

        :param folder_path: Path to the folder containing text files.
        """
        processed_hashes = set(self.df["hash"])

        for file in os.listdir(folder_path):
            # Retrieving the text
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()

            text_hash = self.compute_hash(text)

            if text_hash in processed_hashes:
                print(f"Skipping {file} (already processed)")
                continue

            try:
                if len(text) < 10**5:
                    dic = self.study_text_with_mistral(text, text_hash, file)
                else:
                    dic = self.study_long_text(text, text_hash, file)
                pickle.dump(dic, open('dic.p', 'wb'))
                self.df.loc[len(self.df)] = dic
                self.save_results()

            except Exception as e:
                print(f"Error processing {file}: {e}")

    def study_text_with_mistral(self, text: str, text_hash: str, file_name: str) -> dict:
        """
        Analyzes a text using the Mistral model.

        :param text: The text to analyze.
        :param text_hash: The hash of the text.
        :param file_name: The name of the file containing the text.
        :return: A dictionary with the analysis results.
        """
        api_key = "wm1af0pJ92Pj1tLbTSztHxeey62ru479"
        model = "mistral-large-latest"

        prompt = self.prompt + f"\\\n hash column : {text_hash}" + \
                 f"\\\n file name : {file_name}" + \
                 f"\n\n le texte à étudier: \n\n" + text + f"\n_n fin du texte"

        print(text[:10])

        client = Mistral(api_key=api_key)

        chat_response = client.chat.parse(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
            ],
            response_format=Entity
        )
        dic = json.loads(chat_response.choices[0].message.content)
        return dic

    def study_long_text(self, text: str, text_hash: str, file_name: str) -> dict:
        """
        Analyzes a long text by chunking it and combining the results.

        :param text: The text to analyze.
        :param text_hash: The hash of the full text.
        :param file_name: The name of the file containing the text.
        :return: A dictionary with the combined analysis results.
        """
        # Chunking the text
        text_splitter = CharacterTextSplitter(
            separator=".",
            chunk_size=30000,
            chunk_overlap=100
        )
        docs = text_splitter.create_documents([text])

        # Study each chunk
        list_dic = []
        for doc in docs:
            text = doc.page_content
            list_dic.append(self.study_text_with_mistral(text, text_hash, file_name))

        # Format a text composed of the dictionaries
        formatted_text = "".join([str(dic) for dic in list_dic])
        # Run the LLM on the formatted text keeping the hash from the full text
        dic = self.study_text_with_mistral(formatted_text, text_hash, file_name)

        return dic

    def augment_data_frame_with_other_informations(self, df_new_informations: pd.DataFrame, left_on: str, right_on: str) -> pd.DataFrame:
        """
        Introduces new data into the existing DataFrame.

        :param df_new_informations: The new DataFrame with additional information.
        :param left_on: Column name in the existing DataFrame to merge on.
        :param right_on: Column name in the new DataFrame to merge on.
        :return: The augmented DataFrame.
        """
        df_new_informations = self.df.merge(df_new_informations, left_on='text_name',
                                            right_on=right_on, how='left')
        return df_new_informations

    def restudy_a_list_of_texts(self, list_of_text_names: List[str], folder_path: str) -> None:
        """
        Re-analyzes a list of specified text files.

        :param list_of_text_names: List of filenames to re-analyze.
        :param folder_path: Path to the folder containing the text files.
        """
        # Settings of Mistral
        api_key = "wm1af0pJ92Pj1tLbTSztHxeey62ru479"
        model = "mistral-large-latest"
        list_text_names = set(self.df["text_name"])

        for file in os.listdir(folder_path):
            if file in list_of_text_names:
                # Retrieving the text
                file_path = os.path.join(folder_path, file)

                if os.path.isfile(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()

                # Delete the last record
                if file in list_text_names:
                    print(f" Restudy {file} (processed earlier)")
                    self.df.drop(self.df[self.df['text_name'] == file].index, inplace=True)

                else:
                    try:
                        text_hash = self.compute_hash(text)
                        if len(text) < 10**5:
                            dic = self.study_text_with_mistral(text, text_hash, file)
                        else:
                            dic = self.study_long_text(text, text_hash, file)

                        pickle.dump(dic, open('dic.p', 'wb'))
                        self.df.loc[len(self.df)] = dic
                        self.save_results()

                    except Exception as e:
                        print(f"Error processing {file}: {e}")
            else:
                continue


