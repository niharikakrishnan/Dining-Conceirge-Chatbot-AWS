import boto3

#Main function that interacts with the front-end and connects with lex 
def lambda_handler(event, context):
    text = (event.get("messages")[0].get("unstructured").get("text"))
    client = boto3.client('lex-runtime')
    response = client.post_text(botName='dininglexbot', botAlias='dc_chatbot', userId= "nk2982", inputText= text)
        
    return {
        'statusCode': 200,
        'headers': { 
            "Access-Control-Allow-Origin": "*" 
        },
        'messages' : [{"type" :"unstructured","unstructured":{"text": response.get("message")}}]
    }