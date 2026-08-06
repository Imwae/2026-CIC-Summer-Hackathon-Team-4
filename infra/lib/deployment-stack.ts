import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import { HttpApi } from '@aws-cdk/aws-apigatewayv2-alpha';
import { HttpLambdaIntegration } from '@aws-cdk/aws-apigatewayv2-integrations-alpha';
import { Construct } from 'constructs';
import * as path from 'path';

export class DeploymentStack extends cdk.Stack {
  public readonly backendFunction: lambda.Function;
  public readonly httpApi: HttpApi;
  public readonly frontendBucket: s3.Bucket;
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Backend Lambda Function
    this.backendFunction = new lambda.Function(this, 'BackendFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../backend'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output',
          ],
        },
      }),
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
    });

    // Grant Bedrock InvokeModel permission
    this.backendFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: ['*'],
      })
    );

    // ─── HTTP API Gateway ──────────────────────────────────────────────
    const lambdaIntegration = new HttpLambdaIntegration('LambdaIntegration', this.backendFunction);

    this.httpApi = new HttpApi(this, 'HttpApi', {
      defaultIntegration: lambdaIntegration,
    });

    // ─── Frontend S3 Bucket ────────────────────────────────────────────
    this.frontendBucket = new s3.Bucket(this, 'FrontendBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Upload frontend build output to the S3 bucket
    new s3deploy.BucketDeployment(this, 'FrontendDeployment', {
      sources: [s3deploy.Source.asset(path.join(__dirname, '../../frontend/dist'))],
      destinationBucket: this.frontendBucket,
    });

    // ─── CloudFront Distribution ───────────────────────────────────────
    const apiGatewayOrigin = new origins.HttpOrigin(
      `${this.httpApi.httpApiId}.execute-api.${this.region}.amazonaws.com`
    );

    this.distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(this.frontendBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
      additionalBehaviors: {
        '/api/*': {
          origin: apiGatewayOrigin,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        },
      },
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
        },
      ],
    });

    // ─── Stack Outputs ─────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'DistributionUrl', {
      value: `https://${this.distribution.distributionDomainName}`,
      description: 'CloudFront distribution URL for the deployed application',
    });
  }
}
