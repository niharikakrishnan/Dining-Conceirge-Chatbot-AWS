import json
import boto3
import random
from opensearchpy import OpenSearch, RequestsHttpConnection

#Setting values to be referenced later in the program
port = 443
ssl = True
certs = True
service = "es"
region = 'us-west-2'
username = " "
password = " "
dynamodbTable = 'yelp-restaurants'
email_id = "abc@gmail.com"
host = "search-yelp-pfcdlcbx2hj4p5mpq6hi2n4fou.us-west-2.es.amazonaws.com" 
sns_queue = "https://sqs.us-west-2.amazonaws.com/144502575213/diningsqs"


#Function to receive message from SQS queue
def get_sqsQueueMessage():
    sqs = boto3.client('sqs')
    sqs_message = sqs.receive_message( 
        QueueUrl = sns_queue, 
        MaxNumberOfMessages = 1, 
        MessageAttributeNames = ['All'],
        VisibilityTimeout = 0, 
        WaitTimeSeconds = 0
    )
    message = sqs_message['Messages'][0]
    return sqs, message

   
#Function to retrieve slots from SQS queue message
def get_slots(message):
    cuisine     = message['MessageAttributes'].get('cuisine').get('StringValue')
    location    = message['MessageAttributes'].get('location').get('StringValue')
    date        = message['MessageAttributes'].get('date').get('StringValue')
    dining_time = message['MessageAttributes'].get('dining_time').get('StringValue')
    people      = message['MessageAttributes'].get('people').get('StringValue')
    email       = message['MessageAttributes'].get('email').get('StringValue')
    
    return cuisine, location, date, dining_time, people, email


#Function to establish OpenSearch connection
def connect_openSearch():
    os = OpenSearch(
        hosts=[{'host': host,'port': port}], 
        http_auth=(username, password), 
        use_ssl = ssl, 
        verify_certs=certs, 
        connection_class=RequestsHttpConnection
    )
    return os
 
   
#Function to perform OpenSearch query using index: restaurants and filter based on cuisines
def get_id(os, cuisine):
    response = os.search(
        index="restaurants", 
        body={"query": {"match": {"cuisine": cuisine}}}
        )
    
    candidates_list = []
    id_list = []
    for item in response['hits']['hits']:
        id_list.append(item["_id"])
    
    suggestion_id_list = random.sample(id_list, 3)
    return suggestion_id_list


#Function to connect to DynamoDB Table
def connect_dynamoDBTable():
    db = boto3.resource('dynamodb')
    table = db.Table(dynamodbTable)
    return table

#Function to fetch three random restaurants details of a particular cuisine from OpenSearch result
def get_restaurant(table, suggestion_id_list):
    restaurant_list=[]
    for suggestion_id in suggestion_id_list:
        restaurant_dict={}
        restaurant_details = table.get_item(
        Key={
            'id': suggestion_id,
            }
        )
        restaurant_dict["name"] = restaurant_details["Item"]["name"]
        restaurant_dict["rating"] = restaurant_details["Item"]["rating"]
        restaurant_dict["address"] = restaurant_details["Item"]["address"]
        restaurant_dict["review_count"] = restaurant_details["Item"]["review_count"]
        restaurant_list.append(restaurant_dict)
    return restaurant_list


#Function to provide template from sending message by email
def get_message(restaurant_list, cuisine, location, date, dining_time, people, email):
    email_message = "Here are a few {} cuisine recommendations in {} for {} people, on {} at {}. ".format(cuisine, location, people, date, dining_time)
    for restaurant_dict in restaurant_list:
        email_message = email_message + "Restaurant: {}. It has {} reviews with an average {} rating. The address is: {}.".format(restaurant_dict['name'], restaurant_dict['review_count'], restaurant_dict['rating'], restaurant_dict['address'])
    
    email_message = email_message + "Your recommendations was sent to: {} . Enjoy your meal!".format(email)
    return email_message


#Function that uses SES to send emails for recommendations
def send_email(email, email_message):
    ses = boto3.client('ses')

    response = ses.send_email(
    Source = email_id,
    Destination = {
        'ToAddresses': [email]
    },
    ReplyToAddresses = [email_id],
    Message={
        'Subject': {
            'Data': 'Dining Conceirge Recommendations',
            'Charset': 'utf-8'
        },
        'Body': {
            'Text': {
                'Data': email_message,
                'Charset': 'utf-8'
            },
            'Html': {
                'Data': email_message,
                'Charset': 'utf-8'
                    }
                }
            }
    )

#Function to delete message from SQS queue
def delete_SQSEntry(sqs, sns_queue, message):
    receipt_handle = message['ReceiptHandle']
    sqs.delete_message(
        QueueUrl=sns_queue,
        ReceiptHandle=receipt_handle
        )
    

#Main lambda function that retrieves message from SQS and performs OpenSearch to fetch restaurant recommendations    
def lambda_handler(event, context):
    sqs, message = get_sqsQueueMessage()
    
    cuisine, location, date, dining_time, people, email = get_slots(message)
    
    os = connect_openSearch()
    suggestion_id_list = get_id(os, cuisine)

    table = connect_dynamoDBTable()
    restaurant_list = get_restaurant(table, suggestion_id_list)
    
    email_message = get_message(restaurant_list, cuisine, location, date, dining_time, people, email)
    send_email(email, email_message)
    
    delete_SQSEntry(sqs, sns_queue, message)
    
    return {
        'statusCode': 200,
        'body': email_message
    }
