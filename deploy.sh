#!/bin/bash

echo "Deploying to S3..."
aws s3 sync . s3://mics295-capstone-website --exclude ".git/*" --exclude "*.sh" --exclude "*.yml" --exclude "*.md"
echo "Deployment complete!"
echo "Website URL: http://mics295-capstone-website.s3-website-us-east-1.amazonaws.com"
