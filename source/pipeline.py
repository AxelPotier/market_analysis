import study_text
import pandas as pd
import langchain
from typing import List
import pickle
import logging



def set_logger():
    logger = logging.getLogger('__pipeline__')
    logger_handler = logging.StreamHandler()
    logger.addHandler(logger_handler)
    formatter = logging.Formatter("%(asctime)s;%(levelname)s;%(message)s", "%Y-%m-%d %H:%M:%S")
    logger_handler.setFormatter(formatter)
    logger.setLevel(20)
    return logger

logger = set_logger()

class PipeLine:

    def __init__(self ):
        self.folder = None
        self.df = None

    # @staticmethod
    def run_pipeline( self, list_dic_folders : List[dict],
                  path_prompt: str,
                  list_dic_scrap_directory_path: List[dict] 
        )-> None :
        '''
        dic_folders : contains a list of dictionary with a folder_path and 
            and a cache name for the temporary information. 
        
        '''
        # the folder

        # Study texts
        df = None
        for dic in list_dic_folders:
            folder_path = dic['folder_path']
            cache_file = dic['cache_file']
            st= study_text.StudyText(path_prompt, cache_file )
            st.analyze_texts_in_folder( folder_path )
            if df :
                df = pd.concat([df,st.df])
            else :
                df = st.df
                print(st.df.columns)
            logger.info(f'Study of {dic["folder_path"]} completed')
            
        
        df_augmented_data = pd.DataFrame(pickle.load(open(list_dic_scrap_directory_path,'rb')) )

        list_col = [col for col in df.columns if col \
                               not in df_augmented_data.columns or col == 'file_name']

        self.df = df_augmented_data.merge(df[list_col],on='file_name', how='left')
        
        pickle.dump(self.df,open('df_test.p','wb'))

        # Transform the dataset

        return None