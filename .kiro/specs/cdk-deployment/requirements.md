# Requirements Document

## Introduction

This document defines the requirements for deploying the Semester Capacity Planner application to AWS using CDK (TypeScript). The deployment uses a serverless architecture: React frontend served from S3 via CloudFront, and the Python FastAPI backend running on Lambda behind an HTTP API Gateway. CloudFront acts as the single entry point, routing `/api/*` requests to the backend and everything else to the frontend static assets.

## Glossary

- **CDK_Stack**: The AWS CDK TypeScript stack that defines all infrastructure resources for the deployment
- **Frontend_Bucket**: The S3 bucket that stores the built React application static assets
- **CloudFront_Distribution**: The AWS CloudFront distribution that serves as the single entry point for all traffic
- **Backend_Lambda**: The AWS Lambda function running the FastAPI application via the Mangum ASGI adapter
- **API_Gateway**: The AWS HTTP API Gateway that routes HTTP requests to the Backend Lambda
- **OAC**: Origin Access Control, the CloudFront mechanism for secure private access to the S3 bucket
- **Deployment_Construct**: The CDK BucketDeployment construct that uploads frontend assets to S3

## Requirements

### Requirement 1: CDK Project Structure

**User Story:** As a developer, I want a well-structured CDK TypeScript project in the `infra/` directory, so that I can manage infrastructure as code with standard tooling.

#### Acceptance Criteria

1. THE CDK_Stack SHALL be defined in a TypeScript project located in the `infra/` directory at the project root
2. WHEN the CDK project is initialized, THE CDK_Stack SHALL include a `package.json` with AWS CDK v2 dependencies, a `tsconfig.json` for TypeScript compilation, and a `cdk.json` pointing to the app entry point
3. THE CDK_Stack SHALL use a single app entry point at `infra/bin/app.ts` that instantiates the deployment stack
4. THE CDK_Stack SHALL define all resources in a single stack file at `infra/lib/deployment-stack.ts`

### Requirement 2: Frontend Static Hosting

**User Story:** As a user, I want the React frontend served from a CDN, so that I get fast page loads from any location.

#### Acceptance Criteria

1. THE CDK_Stack SHALL create the Frontend_Bucket as a private S3 bucket with public access blocked
2. THE CDK_Stack SHALL configure OAC on the CloudFront_Distribution to grant read access to the Frontend_Bucket
3. WHEN the CDK stack is deployed, THE Deployment_Construct SHALL upload the contents of `frontend/dist/` to the Frontend_Bucket
4. THE CloudFront_Distribution SHALL serve the Frontend_Bucket as the default origin for all paths not matching `/api/*`
5. WHEN a request path does not match an existing S3 object, THE CloudFront_Distribution SHALL return `index.html` with a 200 status code to support client-side routing

### Requirement 3: Backend Lambda Deployment

**User Story:** As a developer, I want the FastAPI backend deployed as a Lambda function, so that it scales automatically and incurs no cost when idle.

#### Acceptance Criteria

1. THE CDK_Stack SHALL create the Backend_Lambda using Python 3.12 runtime
2. THE Backend_Lambda SHALL bundle the `backend/` directory source code along with its pip dependencies from `requirements.txt`
3. THE Backend_Lambda SHALL use the Mangum adapter as its handler entry point
4. THE Backend_Lambda SHALL have an IAM policy granting `bedrock:InvokeModel` permission
5. THE Backend_Lambda SHALL have a memory allocation and timeout suitable for AI inference workloads (minimum 512 MB memory, 30-second timeout)

### Requirement 4: API Gateway Configuration

**User Story:** As a developer, I want an HTTP API Gateway routing requests to the Lambda function, so that the backend is accessible via standard HTTP with low overhead.

#### Acceptance Criteria

1. THE CDK_Stack SHALL create the API_Gateway as an AWS HTTP API (API Gateway v2)
2. THE API_Gateway SHALL integrate with the Backend_Lambda using a Lambda proxy integration
3. THE API_Gateway SHALL route all HTTP methods and paths to the Backend_Lambda

### Requirement 5: CloudFront Traffic Routing

**User Story:** As a user, I want a single URL that serves both the frontend and API, so that there are no cross-origin issues and the deployment is simple.

#### Acceptance Criteria

1. THE CloudFront_Distribution SHALL define a behavior for the path pattern `/api/*` that forwards requests to the API_Gateway origin
2. THE CloudFront_Distribution SHALL forward all HTTP methods (GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD) for the `/api/*` behavior
3. THE CloudFront_Distribution SHALL disable caching for the `/api/*` behavior to ensure API responses are always fresh
4. THE CloudFront_Distribution SHALL use the default CloudFront domain name (no custom domain)

### Requirement 6: Deployment Output

**User Story:** As a developer, I want the CloudFront URL output after deployment, so that I can immediately access the deployed application.

#### Acceptance Criteria

1. WHEN the CDK stack deploys successfully, THE CDK_Stack SHALL output the CloudFront_Distribution URL as a CloudFormation output
2. THE CDK_Stack SHALL name the output clearly (e.g., `DistributionUrl`) so it is identifiable in the deployment logs

