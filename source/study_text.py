import os
from typing import List, Optional
from mistralai import Mistral
from pathlib import Path
import json 
import pandas as pd
import pickle
import hashlib
from columns_definition import Entity



def read_files_from_folder(folder):
    files = [f for f in os.listdir(folder) if f.endswith('.txt')]
    file_contents = {}
    for file in files:
        file_path = os.path.join(folder, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            file_contents[file] = f.read()
    return file_contents

class StudyText:

    def __init__(self, path_prompt, cache_file = "df.p" ):
        
        with open(path_prompt,"r",encoding="utf-8") as f:
            self.prompt = f.read()

        self.cache_file = cache_file
        self.load_results()


    def load_results(self):
        """Charge les résultats existants pour éviter de recalculer."""
        if os.path.exists("df.p"):
            self.df = pickle.load(open(self.cache_file,'rb'))
        else : 
            self.df = pd.DataFrame(columns=Entity.model_fields.keys())
                                #    ['activities', 'association_name',
                                #            	'communication',	'contact',	'member_statuses',
                                #                 	'objectives',	'offers','hash'] )
            
        return None
            
    def save_results(self):
        """Saves the results in a pickle"""
        pickle.dump(self.df,open(self.cache_file,'wb'))
        return None

    def compute_hash(self, text):
        """Calcule un hash unique pour un texte donné."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    

    def analyze_texts_in_folder(self, folder_path):
        '''
        Objective: analyze the text within the folder.

        Params: folder_path : the path of the folder containing the files
                        to be read.
        '''
         ## settings of mistral
        api_key = "wm1af0pJ92Pj1tLbTSztHxeey62ru479"
        model = "mistral-large-latest"
        processed_hashes = set(self.df["hash"])

        for file in os.listdir(folder_path):

            # Retrieving the text
            file_path = os.path.join(folder_path,file)
            if os.path.isfile(file_path):
                with open(file_path,'r',encoding='utf-8') as f:
                    text = f.read()

            text_hash = self.compute_hash(text)

            if text_hash in processed_hashes:
                print(f"Skipping {file} (already processed)")
                continue
            
            try :
                prompt = self.prompt + f"\\\n hash column : {text_hash}" + \
                      f"\\\n file name : {file}"
                
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
                    response_format=Entity
                )
                dic = json.loads(chat_response.choices[0].message.content)
                pickle.dump(dic,open('dic.p','wb'))
                self.df.loc[len(self.df)] = dic
                self.save_results()

            except Exception as e:
                print(f"Error processing {file}: {e}")

    # @staticmethod
    def augment_data_frame_with_other_informations(self,df_new_informations, right_on):
        '''
        Obective : introduce the new data frame in the attribute dataframe.
        '''
        df_new_informations = self.df.merge(df_new_informations, left_on = 'text_name',
                                            right_on=right_on, how = 'left') 
        return df_new_informations


    # def study_text(
    #         folder_name : str
    #         ):
    #     '''
    #     Objective : retrieves the  texts and outputs the json.
        
    #     '''
        
    #     ## settings of mistral
    #     api_key = "wm1af0pJ92Pj1tLbTSztHxeey62ru479"
    #     model = "mistral-large-latest"

    #     # Retrieving the prompt
    #     chemin_du_script = Path(__file__).parent  # Cela donne le chemin du fichier study_text.py
    #     chemin_prompt = "../source/prompt.txt"

    #     with open(chemin_prompt,"r",encoding="utf-8") as f:
    #         prompt = f.read()

    #     list_dic = []
    #     for file in os.listdir(folder_name):

    #         # Retrieving the text
    #         file_path = os.path.join(folder_name,file)
    #         if os.path.isfile(file_path):
    #             with open(file_path,'r',encoding='utf-8') as f:
    #                 text = f.read()
    #         print(text[:10])

    #         client = Mistral(api_key=api_key)
            

    #         chat_response = client.chat.parse(
    #             model=model,
    #             messages=[
    #                 {
    #                     "role": "system", 
    #                     "content": prompt
    #                 },
    #                 {
    #                     "role": "user", 
    #                     "content": text
    #                 },
    #             ],
    #             response_format=Association
    #         )
    #         dic = json.loads(chat_response.choices[0].message.content)
    #         list_dic.append(dic)
    #     return list_dic