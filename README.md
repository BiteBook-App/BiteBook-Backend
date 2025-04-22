# BiteBook-Backend Setup Guide

## Prerequisites

Before proceeding, ensure that you have the following installed on your system:

- Python (>= 3.8) -> I am using Python 3.11.7
- `pip` (Python package manager)
- `venv` (Python virtual environment module)
- Firebase Admin SDK private key (detailed below)

---

## Setup Instructions

### 1. Create a Virtual Environment
To keep dependencies isolated, create a virtual environment:

```sh
python -m venv venv
```

To activate, run:

On **Mac**:
```sh
source venv/bin/activate
```

On **Windows**:
```sh
venv\Scripts\activate
```

### 2. Install Dependencies
To install all dependencies, run:
```sh
pip install -r requirements.txt && playwright install
```

### 3. env File
Create a GroqCloud account and generate an API key. Set up env file with GROQ_API_KEY={value here}. 

### 3. Firebase Configuration
In order for the service to access the BiteBook's Firebase project, you must include a private key.

To do this,
1. Navigate to the Firebase console
2. Go to the `Project Settings`
3. Go to `Service Accounts`
4. Click **Generate new private key**.
5. Rename this `.json` as `bitebook-admin-credential.json` and place it in `./BiteBook-Backend/firebase-admin-sdk/`.

### 4. Run the Application
In the root directory, run the following command to start up FastAPI
```sh
uvicorn main:app --reload
```

Once the server starts, you can access the GraphQL endpoint at `http://127.0.0.1:8000/graphql`.

Accessing this URL on a browser will open up the GraphQL playground, where you can test the endpoint within a UI.

### 5. Running Unit Tests
In the root directory, run the following command to run unit tests that validate the core features of BiteBook's GraphQL backend.
```sh
pytest
```

To run the unit tests without deprecation warnings, run the following:
```sh
pytest -W ignore::DeprecationWarning
```
