# California State Procurement Data — EDA & MongoDB Loader

Cleans and loads California procurement data (2012–2015) into MongoDB for use with an AI agent.

## Setup

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Get the data
Download the CSV from Kaggle:
https://www.kaggle.com/datasets/samuelcortinhas/california-state-procurement-data

Place the CSV file in the same folder as the notebook:
```
procurement-assistant/
├── PURCHASE ORDER DATA EXTRACT 2012-2015_0.csv
└── explore_data.ipynb
```

### 3. Start MongoDB
Make sure MongoDB is running locally on port 27017.
Install guide: https://www.mongodb.com/docs/manual/installation/

### 4. Run the notebook
```
jupyter notebook explore_data.ipynb
```
