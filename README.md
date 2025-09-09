# MICS295Capstone
MICS Capstone Project - Hello World Web Application

## Overview
Simple HTML application deployed to AWS S3 with automated CI/CD using GitHub Actions.

## Architecture
- **Frontend**: Static HTML page
- **Hosting**: AWS S3 static website hosting
- **CI/CD**: GitHub Actions with self-hosted runner
- **Deployment**: Automated sync to S3 on push to main branch

## Website URL
http://mics295-capstone-website.s3-website-us-east-1.amazonaws.com

## Manual Deployment
```bash
./deploy.sh
```

## Files
- `index.html` - Main HTML page
- `deploy.sh` - Deployment script
- `.github/workflows/deploy.yml` - GitHub Actions workflow
- `infrastructure.yml` - CloudFormation template (for future use)
- `buildspec.yml` - CodeBuild specification (for future use)
