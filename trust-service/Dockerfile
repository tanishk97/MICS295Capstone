FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.11

# Install cosign
RUN curl -sSL -o /usr/local/bin/cosign https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64 && \
    chmod +x /usr/local/bin/cosign

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy handler
COPY handler.py ${LAMBDA_TASK_ROOT}/

CMD [ "handler.handler" ]
