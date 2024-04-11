import { Construct } from "constructs";
import { App, TerraformOutput, TerraformStack } from "cdktf";
import { GoogleBetaProvider } from "./.gen/providers/google-beta/provider/index";
import { ArchiveProvider } from "./.gen/providers/archive/provider";
import { DataGoogleBillingAccount } from "./.gen/providers/google-beta/data-google-billing-account";
import { GoogleProject } from "./.gen/providers/google-beta/google-project";
import { StaticSitePattern } from "./patterns/static-site";
import { RandomProvider } from "./.gen/providers/random/provider";

import * as dotenv from "dotenv";
import path = require("path");
import { CloudFunctionDeploymentConstruct } from "./components/cloud-function-deployment-construct";
import { CloudFunctionConstruct } from "./components/cloud-function-construct";
import { DatastoreConstruct } from "./components/datastore-construct";
import { GoogleStorageBucketIamMember } from "./.gen/providers/google-beta/google-storage-bucket-iam-member";
import { GoogleDatastoreIndex } from "./.gen/providers/google-beta/google-datastore-index";
import { GoogleProjectIamMember } from "./.gen/providers/google-beta/google-project-iam-member";
import { GoogleProjectService } from "./.gen/providers/google-beta/google-project-service";

dotenv.config();

class ImageGenStack extends TerraformStack {
  async buildStack() {
    const projectId = process.env.PROJECTID!;
    // const suffix = process.env.SUFFIX ?? "";
    const randomProvider = new RandomProvider(this, "random", {});
    const archiveProvider = new ArchiveProvider(this, "archive", {});
    new GoogleBetaProvider(this, "google");

    const billingAccount = new DataGoogleBillingAccount(
      this,
      "billing-account",
      {
        billingAccount: process.env.BillING_ACCOUNT!,
      }
    );

    const project = new GoogleProject(this, "project", {
      projectId: projectId,
      name: projectId,
      billingAccount: billingAccount.id,
      skipDelete: false,
    });
    const staticSitePattern1 = new StaticSitePattern(this, "static-site1", {
      project: project.projectId,
      region: process.env.REGION!,
      indexPagePath: path.join(
        __dirname,
        "assets",
        process.env.REGION!,
        "index.html"
      ),
      notFoundPagePath: path.join(
        __dirname,
        "assets",
        process.env.REGION!,
        "404.html"
      ),
      randomProvider: randomProvider,
    });

    const staticSitePattern2 = new StaticSitePattern(this, "static-site2", {
      project: project.projectId,
      region: process.env.REGION!,
      indexPagePath: path.join(
        __dirname,
        "assets",
        process.env.REGION!,
        "index.html"
      ),
      notFoundPagePath: path.join(
        __dirname,
        "assets",
        process.env.REGION!,
        "404.html"
      ),
      randomProvider: randomProvider,
    });


    const cloudFunctionDeploymentConstruct = new CloudFunctionDeploymentConstruct(
      this,
      "cloud-function-deployment",
      {
        project: project.projectId,
        region: process.env.REGION!,
        archiveProvider: archiveProvider,
        randomProvider: randomProvider,
      }
    );

    //For the first deployment, it takes a while for API to be enabled.
    // await new Promise((r) => setTimeout(r, 30000));

    const approvalImagecloudFunctionConstruct = await CloudFunctionConstruct.create(
      this,
      "approvalimage",
      {
        functionName: "approvalimage",
        runtime: "python311",
        entryPoint: "approvalimage",
        timeout: 600,
        availableMemory: "512Mi",
        makePublic: true,
        cloudFunctionDeploymentConstruct: cloudFunctionDeploymentConstruct,
        environmentVariables: {
          SECRET_KEY: process.env.SECRET_KEY!,
          GMAIL: process.env.GMAIL!,
          APP_PASSWORD: process.env.APP_PASSWORD!,
          IMAGE_BUCKET: staticSitePattern1.siteBucket.name,
          APPROVED_IMAGE_BUCKET: staticSitePattern2.siteBucket.name,
        }
      }
    );


    const rejectImagecloudFunctionConstruct = await CloudFunctionConstruct.create(
      this,
      "rejectimage",
      {
        functionName: "rejectimage",
        runtime: "python311",
        entryPoint: "rejectimage",
        timeout: 600,
        availableMemory: "512Mi",
        makePublic: true,
        cloudFunctionDeploymentConstruct: cloudFunctionDeploymentConstruct,
        environmentVariables: {
          SECRET_KEY: process.env.SECRET_KEY!,
          GMAIL: process.env.GMAIL!,
          APP_PASSWORD: process.env.APP_PASSWORD!,
        }
      }
    );

    new GoogleProjectService(this, "aiplatformService", {
      project: project.id,
      service: "aiplatform.googleapis.com",
      disableOnDestroy: false,
    });
    const genImagecloudFunctionConstruct = await CloudFunctionConstruct.create(
      this,
      "genimage",
      {
        functionName: "genimage",
        runtime: "python311",
        entryPoint: "genimage",
        timeout: 600,
        availableMemory: "512Mi",
        makePublic: true,
        cloudFunctionDeploymentConstruct: cloudFunctionDeploymentConstruct,
        environmentVariables: {
          ENABLE: "TRUE",
          SECRET_KEY: process.env.SECRET_KEY!,
          ENCRYPT_KEY: process.env.ENCRYPT_KEY!,
          MODEL_GARDEN_REGION: process.env.MODEL_GARDEN_REGION!,
          IMAGE_BUCKET: staticSitePattern1.siteBucket.name,
          APPROVED_IMAGE_BUCKET: staticSitePattern2.siteBucket.name,
          GMAIL: process.env.GMAIL!,
          APP_PASSWORD: process.env.APP_PASSWORD!,
          APPROVAL_URL: approvalImagecloudFunctionConstruct.cloudFunction.url,
          REJECT_URL: rejectImagecloudFunctionConstruct.cloudFunction.url,
          APPROVER_EMAILS: process.env.APPROVER_EMAILS!,
          RATE_LIMIT_PER_MINUTE: process.env.RATE_LIMIT_PER_MINUTE!,
        }
      }
    );

    const emailhashcloudFunctionConstruct = await CloudFunctionConstruct.create(
      this,
      "emailhash",
      {
        functionName: "emailhash",
        runtime: "python311",
        entryPoint: "emailhash",
        timeout: 600,
        availableMemory: "512Mi",
        makePublic: true,
        cloudFunctionDeploymentConstruct: cloudFunctionDeploymentConstruct,
        environmentVariables: {
          SECRET_KEY: process.env.SECRET_KEY!,
          ENCRYPT_KEY: process.env.ENCRYPT_KEY!,
          IMAGE_BUCKET: staticSitePattern1.siteBucket.name,
          GEN_IMAGE_URL: genImagecloudFunctionConstruct.cloudFunction.url,
        }
      }
    );

    const datastore = await DatastoreConstruct.create(this, "datastore", {
      project: project.projectId,
      servicesAccount: genImagecloudFunctionConstruct.serviceAccount,
    });
    await DatastoreConstruct.create(this, "approvalImagedatastore", {
      project: project.projectId,
      servicesAccount: approvalImagecloudFunctionConstruct.serviceAccount,
    });

    await DatastoreConstruct.create(this, "rejectImagedatastore", {
      project: project.projectId,
      servicesAccount: rejectImagecloudFunctionConstruct.serviceAccount,
    });

    new GoogleDatastoreIndex(this, "datastore-index", {
      project: project.projectId,
      kind: "GenImageJob",
      properties: [
        {
          name: "email",
          direction: "DESCENDING",
        },
        {
          name: "modify_time",
          direction: "DESCENDING",
        },
      ],
      dependsOn: datastore.services,
    });

    new GoogleStorageBucketIamMember(this, "static-site-iam-member", {
      bucket: staticSitePattern1.siteBucket.name,
      role: "roles/storage.legacyBucketWriter",
      member:
        "serviceAccount:" + genImagecloudFunctionConstruct.serviceAccount.email,
    });

    new GoogleStorageBucketIamMember(this, "static-site2-iam-member", {
      bucket: staticSitePattern2.siteBucket.name,
      role: "roles/storage.legacyBucketWriter",
      member:
        "serviceAccount:" + approvalImagecloudFunctionConstruct.serviceAccount.email,
    });

    new GoogleProjectIamMember(this, "AiplatformProjectIamMember", {
      project: project.id,
      role: "roles/aiplatform.user",
      member: "serviceAccount:" + genImagecloudFunctionConstruct.serviceAccount.email,
    });

    new TerraformOutput(this, "gen-image-url", {
      value:
        "https://storage.googleapis.com/" +
        staticSitePattern1.siteBucket.name +
        "/index.html?key=" +
        process.env.SECRET_KEY! +
        "&api=" +
        genImagecloudFunctionConstruct.cloudFunction.url,
    });

    new TerraformOutput(this, "emailhash-url", {
      value: emailhashcloudFunctionConstruct.cloudFunction.url + "?key=" + process.env.SECRET_KEY! + "&email=xxx&reviewer_email=abcd",
    });
  }
  constructor(scope: Construct, id: string) {
    super(scope, id);

    // define resources here
  }
}

async function buildStack(scope: Construct, id: string) {
  const stack = new ImageGenStack(scope, id);
  await stack.buildStack();
}

async function createApp(): Promise<App> {
  const app = new App();
  await buildStack(app, "cdktf");
  return app;
}

createApp().then((app) => app.synth());
