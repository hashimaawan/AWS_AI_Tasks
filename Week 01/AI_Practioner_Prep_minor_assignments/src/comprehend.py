"""
Task 2 — Sentiment analysis with Amazon Comprehend.

Sends a list of sample tweets to detect_sentiment and prints each one's
overall sentiment (POSITIVE / NEGATIVE / NEUTRAL / MIXED) with the confidence
breakdown across all four categories.

Run in a region where Comprehend is available (e.g. eu-west-1). No S3 needed —
the text is passed directly to the API.
"""

import boto3                                     # AWS SDK for Python

REGION = "eu-west-1"
comp = boto3.client("comprehend", region_name=REGION)   # create a Comprehend client

tweets = [                                        # sample texts to analyse (swap in your own)
    "I absolutely love the new update, best release this year!",
    "Terrible experience, my order never arrived and support ignored me.",
    "The weather today is fine, nothing much to report.",
    "Not sure how I feel about the redesign, some parts better, some worse.",
]

for t in tweets:                                 
    r = comp.detect_sentiment(Text=t, LanguageCode="en")   # call DetectSentiment (text + language)
    s = r["SentimentScore"]                      
    print(f"{r['Sentiment']:9} | pos={s['Positive']:.2f} neg={s['Negative']:.2f} "
          f"neu={s['Neutral']:.2f} mixed={s['Mixed']:.2f} | {t}")   # winning sentiment + scores + text