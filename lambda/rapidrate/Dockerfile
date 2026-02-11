# RapidRate Lambda Container Image
# Monte Carlo simulation for actuarial pricing

FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for XGBoost
RUN dnf install -y gcc-c++ cmake && \
    dnf clean all

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy function code
COPY handler.py ${LAMBDA_TASK_ROOT}/
COPY monte_carlo.py ${LAMBDA_TASK_ROOT}/
COPY models.py ${LAMBDA_TASK_ROOT}/

# Set the handler
CMD ["handler.lambda_handler"]
