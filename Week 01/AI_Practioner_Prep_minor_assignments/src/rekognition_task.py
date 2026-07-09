"""
Task 1 — Image analysis with Amazon Rekognition.

Reads 2-3 images from an S3 bucket, calls detect_labels on each, and saves
the detected labels + confidence scores to rekognition_results.json.

Run in a region where Rekognition is available (e.g. eu-west-1). The bucket
must be in the SAME region as the API call, because detect_labels reads the
image directly from S3.
"""

import boto3, json                              # boto3 = AWS SDK for Python; json to format/save output

REGION = "eu-west-1"                             # region where Rekognition runs and the bucket lives
BUCKET = "hashim-ai-images-481719141347"         
images = ["dog.jpg", "street.jpg", "food.png"]   

rek = boto3.client("rekognition", region_name=REGION)   # create a Rekognition client in that region

results = {}                                    
for name in images:                              
    resp = rek.detect_labels(                    
        Image={"S3Object": {"Bucket": BUCKET, "Name": name}},  # point it at the image in S3
        MaxLabels=10,                            # return at most 10 labels
        MinConfidence=70,                        # only labels the model is >=70% confident about
    )
    results[name] = [                            # keep just the label name + rounded confidence
        {"label": l["Name"], "confidence": round(l["Confidence"], 2)}
        for l in resp["Labels"]                  # resp["Labels"] is the list Rekognition returned
    ]

print(json.dumps(results, indent=2))             
with open("rekognition_results.json", "w") as f: 
    json.dump(results, f, indent=2)              
print("\nSaved to rekognition_results.json")