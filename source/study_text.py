import os
from typing import List, Optional
from mistralai import Mistral
from pathlib import Path
import json 
import pandas as pd
import pickle
import hashlib
from columns_definition import Entity
from langchain.text_splitter import CharacterTextSplitter



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

    
    def update_prompt(
            self,
            path_prompt: str 
            )-> None:
        with open(path_prompt,"r",encoding="utf-8") as f:
            self.prompt = f.read()


    def load_results(self):
        """Charge les résultats existants pour éviter de recalculer."""
        if os.path.exists(self.cache_file):
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
                if len(text)<10**5:
                    dic = self.study_text_with_mistral(text, text_hash, file)
                else :
                    dic = self.study_long_text(text, text_hash, file)
                pickle.dump(dic,open('dic.p','wb'))
                self.df.loc[len(self.df)] = dic
                self.save_results()

            except Exception as e:
                print(f"Error processing {file}: {e}")



    def study_text_with_mistral(
        self,
        text: str,
        text_hash:str,
        file_name:str
        )-> dict:
        '''
        Objective : study a text using a specific model.
        
        '''
        api_key = "wm1af0pJ92Pj1tLbTSztHxeey62ru479"
        model = "mistral-large-latest"


        prompt = self.prompt + f"\\\n hash column : {text_hash}" + \
                    f"\\\n file name : {file_name}"\
                    +f"\n\n le texte à étudier: \n\n"\
                    + text + f"\n_n fin du texte"
                
        print(text[:10])

        client = Mistral(api_key=api_key)
        
        chat_response = client.chat.parse(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": prompt
                },
                # {
                #     "role": "user", 
                #     "content": text
                # },
            ],
            response_format=Entity
        )
        dic = json.loads(chat_response.choices[0].message.content)
        return dic
    
    def study_long_text(
        self,
        text: str,
        text_hash:str,
        file_name:str
        )->dict:
        '''
        Objective : this function chunks a long text and applies the study function
            on each chunk and combine the results.
        
        Params : text : text to analyse.
                 text_hash : hash of the full text.
                 file_name : name of the file.   
        '''
        
        ## Chunking the text
        text_splitter = CharacterTextSplitter(
            separator = ".",
            chunk_size = 30000,
            chunk_overlap  = 100
        )
        docs = text_splitter.create_documents([text])

        ## Study each chunk.
        list_dic = []
        for doc in docs:
            text = doc.page_content
            list_dic.append(self.study_text_with_mistral(text, text_hash, file_name))
        
        ##format a text composed of the dictionnaries.
        formatted_text = "".join([str(dic) for dic in list_dic])
        ## run the llm on the formatted text keepin the hash from the full text
        dic = self.study_text_with_mistral(formatted_text, text_hash, file_name)

        return dic

    # @staticmethod
    def augment_data_frame_with_other_informations(self,df_new_informations, left_on, right_on):
        '''
        Obective : introduce the new data frame in the attribute dataframe.
        
        params : 
        '''
        df_new_informations = self.df.merge(df_new_informations, left_on = 'text_name',
                                            right_on=right_on, how = 'left') 
        return df_new_informations
     

    def restudy_a_list_of_texts(
            self, 
            list_of_text_names: List[str],
            folder_path:str
            )->None:
        '''
        Objective : Study the texts in the provided list.

        Params : list_of_text_names : a list with the name of the files that will
                    be  studied.
                folder_path : name of the folder where the files are.
        '''
        

        ## settings of mistral
        api_key = "wm1af0pJ92Pj1tLbTSztHxeey62ru479"
        model = "mistral-large-latest"
        list_text_names = set(self.df["text_name"])
        

        for file in os.listdir(folder_path):
            
            if file in list_of_text_names:
                # Retrieving the text
                file_path = os.path.join(folder_path,file)

                if os.path.isfile(file_path):
                    with open(file_path,'r',encoding='utf-8') as f:
                        text = f.read()

                ## delete the last record
                if file in list_text_names:
                    print(f" Restudy {file} (processed earlier)")
                    self.df.drop( self.df[self.df['text_name']==file].index ,inplace= True)
        

                else : 
                    try :
                        text_hash = self.compute_hash(text)
                        if len(text) < 10**5:
                            dic = self.study_text_with_mistral(text, text_hash, file)
                        else :
                            dic = self.study_long_text(text, text_hash, file)

                        pickle.dump(dic,open('dic.p','wb'))
                        self.df.loc[len(self.df)] = dic
                        self.save_results()

                    except Exception as e:
                        print(f"Error processing {file}: {e}")
            else :
                continue
    

