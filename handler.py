from pano.decompiler import decompile
import json


def decompile_bytecode(event, context):
    data = json.loads(event['body'])
    bytecode = data["bytecode"]
    result = decompile(bytecode)
    return {"statusCode": 200, "body": json.dumps(result)}
