# Jardin du thé

Given a list with the black and green teas, generate a Google Spreadsheet with the data of each tea and the ingredients, extracted from the description in the web.

The ingredients are extracted and normalized using GPT4, so could be errors.

A google sheet with name "Jardin du the" should be shared with the [service account created](https://pygsheets.readthedocs.io/en/stable/authorization.html#service-account)
to interact with Google sheets.

Execution:
```
pipenv install
OPENAI_API_KEY=YOUR_OPENAI_API_KEY pipenv run tea-data.py green_teas.url
OPENAI_API_KEY=YOUR_OPENAI_API_KEY pipenv run tea-data.py black_teas.url
```
