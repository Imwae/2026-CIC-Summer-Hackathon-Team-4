# Implementation Plan: CDK Deployment

## Overview

Implement a single-stack AWS CDK TypeScript deployment for the Semester Capacity Planner. Tasks are ordered so each builds on the previous: project scaffolding first, then Lambda + API Gateway, then S3 + CloudFront, then wiring the behaviors together, and finally the handler wrapper.

## Tasks

- [ ] 1. Create CDK project structure
  - [ ] 1.1 Initialize CDK TypeScript project in `infra/`
    - Create `infra/package.json` with `aws-cdk-lib`, `constructs`, `@aws-cdk/aws-apigatewayv2-alpha`, `@aws-cdk/aws-apigatewayv2-integrations-alpha`, and dev dependencies (`typescript`, `ts-node`, `jest`, `ts-jest`, `aws-cdk-lib/assertions`)
    - Create `infra/tsconfig.json` with strict TypeScript config targeting ES2020
    - Create `infra/cdk.json` with `"app": "npx ts-node --prefer-ts-exts bin/app.ts"`
    - Create `infra/bin/app.ts` that instantiates `DeploymentStack`
    - Create `infra/lib/deployment-stack.ts` with an empty stack class
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 2. Implement Backend Lambda and API Gateway
  - [ ] 2.1 Add Lambda construct to `DeploymentStack`
    - In `infra/lib/deployment-stack.ts`, create a `lambda.Function` with Python 3.12 runtime
    - Use `Code.fromAsset('../backend', { bundling: ... })` with a pip install bundling command that installs dependencies from `requirements.txt` into the asset
    - Set handler to `handler.handler`
    - Configure 512 MB memory, 30-second timeout
    - Add IAM policy statement granting `bedrock:InvokeModel` on `*`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ] 2.2 Add HTTP API Gateway to `DeploymentStack`
    - Create an `HttpApi` (API Gateway v2) with a default stage
    - Add a Lambda proxy integration using `HttpLambdaIntegration`
    - Add a catch-all route (`ANY /{proxy+}`) pointing to the Lambda integration
    - _Requirements: 4.1, 4.2, 4.3_

- [ ] 3. Implement Frontend Hosting
  - [ ] 3.1 Add S3 bucket and BucketDeployment to `DeploymentStack`
    - Create a private S3 bucket with `blockPublicAccess: BlockPublicAccess.BLOCK_ALL` and `removalPolicy: RemovalPolicy.DESTROY` (for easy teardown)
    - Add `BucketDeployment` sourcing from `'../frontend/dist'`
    - _Requirements: 2.1, 2.3_

  - [ ] 3.2 Add CloudFront distribution with S3 origin
    - Create an `S3OriginAccessControl` for the bucket
    - Create a `Distribution` with the S3 bucket as the `defaultBehavior` origin (using `S3BucketOrigin.withOriginAccessControl`)
    - Set `defaultRootObject: 'index.html'`
    - Add `errorResponses` for 403 and 404 that return `/index.html` with status 200
    - _Requirements: 2.2, 2.4, 2.5_

- [ ] 4. Add CloudFront API behavior and outputs
  - [ ] 4.1 Add API Gateway origin behavior to CloudFront
    - Add an `additionalBehaviors` entry for `/api/*` using an `HttpOrigin` pointing to the API Gateway URL (extract domain from the HttpApi URL)
    - Set `allowedMethods: AllowedMethods.ALLOW_ALL`
    - Set `cachePolicy: CachePolicy.CACHING_DISABLED`
    - Set `originRequestPolicy: OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ] 4.2 Add CloudFormation output for the distribution URL
    - Add a `CfnOutput` named `DistributionUrl` with the distribution's `distributionDomainName`
    - _Requirements: 6.1, 6.2_

- [ ] 5. Create Lambda handler wrapper
  - [ ] 5.1 Create `backend/handler.py`
    - Create the Mangum wrapper file: `from mangum import Mangum` and `from backend.main import app` then `handler = Mangum(app)`
    - Verify the import path works with the bundled Lambda layout (may need `from main import app` instead depending on bundling)
    - _Requirements: 3.3_

- [ ] 6. Checkpoint - Verify CDK synthesis
  - Ensure `cd infra && npx cdk synth` succeeds without errors. Ask the user if questions arise.

- [ ]* 7. Add CDK assertion tests
  - [ ]* 7.1 Write CDK snapshot/assertion tests
    - Create `infra/test/deployment-stack.test.ts`
    - Assert Lambda exists with Python 3.12 runtime, 512 MB memory, 30s timeout
    - Assert S3 bucket has public access blocked
    - Assert CloudFront distribution has two origins and error responses configured
    - Assert API Gateway exists with Lambda integration
    - Assert IAM policy grants `bedrock:InvokeModel`
    - Assert `DistributionUrl` output exists
    - _Requirements: 1.1–6.2_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The CDK project uses TypeScript; the Lambda handler is Python
- `mangum` is already in `backend/requirements.txt`
- The frontend must be built (`npm run build` in `frontend/`) before deployment so `frontend/dist/` exists
- The Lambda bundling command handles `pip install` into the asset directory

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "3.1", "5.1"] },
    { "id": 2, "tasks": ["2.2", "3.2"] },
    { "id": 3, "tasks": ["4.1"] },
    { "id": 4, "tasks": ["4.2"] },
    { "id": 5, "tasks": ["7.1"] }
  ]
}
```
