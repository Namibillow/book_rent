##  Project for Human Machine Dialogue 

This repository is for the Human Machine Dialogue course final project.

I have created a library help service bot using rasa v2.8.16, rasa-sdk v2.8.3 and python v3.8.12.

Not all the files required to run this are included for privacy and size reasons.

For the saved train models and database, please go [model link](https://drive.google.com/file/d/1lkjmRDv0zTPRCsUGg_7doWFCOf4BrCtv/view?usp=sharing) and [database link](https://drive.google.com/file/d/18EGvl_QHsgO1SZE2cqC2ew4B09Utt1Zn/view?usp=sharing).

### To quickly exaplin what's contained in this repo: 

- **data/nlu.yml** contains training examples for the NLU model  
- **data/stories/** contains files for training stories for the Core model 
- **data/rules.yml** contains files for training rules for the Core model 
- **actions/actions.py** contains some custom actions
- **config.yml** contains the model configuration
- **domain.yml** contains the domain (intents, repsponses, entities, etc.) of the assistant  
- **utils/** contains files used to create data
- **tests/** contains files for testing examples & stories used for testing 
- **endpoints.yml** contains the webhook configuration for the custom action  
- ***_test_results/** contains test results for NLU & Dialogue models 
