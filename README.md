##  Project for Human Machine Dialogue 

This repository is for the Human Machine Dialogue course final project.

Using rasa v2.8.16, rasa-sdk v2.8.3 and python v3.8.12.

I have created a library help service bot. 

However, not all the files are included for privacy and size reasons.

### To quickly exaplin what's contained in this repo: 

- **data/nlu.yml** contains training examples for the NLU model  
- **data/stories/** contains files for training stories for the Core model 
- **data/rules.yml** contains files for training rules for the Core model 
- **actions/actions.py** contains some custom actions
- **config.yml** contains the model configuration
- **domain.yml** contains the domain of the assistant  
- **utils/** contains files used to create data
- **tests/** contains files for testing examples & stories used for testing 
- **endpoints.yml** contains the webhook configuration for the custom action  
