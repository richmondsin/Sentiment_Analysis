from var_config import *

from flask import Flask, render_template, request, jsonify
import traceback
import psycopg2
import requests
import json

app = Flask(__name__)

def generate_bearer_token(API_KEY):
    url = 'https://iam.cloud.ibm.com/identity/token'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'urn:ibm:params:oauth:grant-type:apikey',
        'apikey': API_KEY
    }
    response = requests.post(url, headers=headers, data=data)
    response_json = response.json()
    bearer_token = response_json.get('access_token')
    return bearer_token

bearer_token = generate_bearer_token(API_KEY)

def create_table():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute(
    '''
    CREATE TABLE IF NOT EXISTS sentiments (
        id SERIAL PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        company TEXT,
        country TEXT,
        customer_service TEXT,
        satisfaction INT
    )
    '''
    )
    conn.commit()
    cursor.close()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            company = request.form['company']
            country = request.form['country']
            customer_service = request.form['customer_service']
            insert_sentiment(first_name, last_name, company, country, customer_service)
        except Exception as e:
            traceback.print_exc()
            return jsonify({'error': str(e)})
    return render_template('index.html')


def get_sentiment(customer_service):
    url = "https://us-south.ml.cloud.ibm.com/ml/v1-beta/generation/text?version=2023-05-29"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {bearer_token}'
    }
    data = {
        "model_id": "ibm/mpt-7b-instruct2",
        "input": f"Classify the customer service comment as 1 or 0\\n\\nCustomer Service:\\n{customer_service}\\n\\nClassification:\\n",
        "parameters": {
            "decoding_method": "greedy",
            "max_new_tokens": 1,
            "min_new_tokens": 0,
            "stop_sequences": [],
            "repetition_penalty": 1
        },
        "project_id": PROJECT_ID
    }
    response = requests.post(url, headers=headers, json=data)
    response_json = response.json()
    generated_text = response_json.get('results')[0].get('generated_text')
    satisfaction = None
    if generated_text:
        satisfaction = generated_text.strip('"')
    if satisfaction.lower() in ["1", "0", "null"]:
        return satisfaction.lower()
    return None


def insert_sentiment(first_name, last_name, company, country, customer_service):
    satisfaction = get_sentiment(customer_service)
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO sentiments (first_name, last_name, company, country, customer_service, satisfaction)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''',
        (first_name, last_name, company, country, customer_service, satisfaction)
    )
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == '__main__':
    create_table()
    app.run()