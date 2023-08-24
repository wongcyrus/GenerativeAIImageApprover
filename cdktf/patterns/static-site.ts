import { Construct } from "constructs";
import { GoogleStorageBucket } from "../.gen/providers/google-beta/google-storage-bucket";
import { GoogleStorageBucketObject } from "../.gen/providers/google-beta/google-storage-bucket-object";
import { GoogleStorageBucketIamMember } from "../.gen/providers/google-beta/google-storage-bucket-iam-member";

import { StringResource } from "../.gen/providers/random/string-resource";
import { RandomProvider } from "../.gen/providers/random/provider";
import { GoogleProjectService } from "../.gen/providers/google-beta/google-project-service";

export interface StaticSitePatternProps {
  readonly project: string;
  readonly region: string;
  readonly mainPageSuffix?: string;
  readonly notFoundPage?: string;
  readonly indexPagePath?: string;
  readonly notFoundPagePath?: string;
  readonly randomProvider: RandomProvider;
}

export class StaticSitePattern extends Construct {
  public static apis = [
    "storage-api.googleapis.com",
    "storage-component.googleapis.com",
  ];
  public readonly siteBucket: GoogleStorageBucket;
  constructor(scope: Construct, id: string, props: StaticSitePatternProps) {
    super(scope, id);
    const bucketSuffix = new StringResource(this, "bucketPrefix", {
      length: 8,
      special: false,
      upper: false,
    });

    const services = [];
    for (const api of StaticSitePattern.apis) {
      services.push(
        new GoogleProjectService(this, `${api.replaceAll(".", "")}`, {
          project: props.project,
          service: api,
          disableOnDestroy: false,
        })
      );
    }
    this.siteBucket = new GoogleStorageBucket(this, "sourceBucket", {
      name: "website-" + props.region + bucketSuffix.result,
      project: props.project,
      location: props.region,
      storageClass: "REGIONAL",
      forceDestroy: true,
      // uniformBucketLevelAccess: true,
      website: {
        mainPageSuffix: props.mainPageSuffix ?? "index.html",
        notFoundPage: props.notFoundPage ?? "404.html",
      },
      cors: [
        {
          origin: ["*"],
          method: ["GET", "HEAD", "PUT", "POST", "DELETE"],
          responseHeader: ["*"],
          maxAgeSeconds: 3600,
        },
      ],
      dependsOn: services,
    });

    new GoogleStorageBucketIamMember(this, "bucketIamMember", {
      bucket: this.siteBucket.id,
      role: "roles/storage.legacyObjectReader",
      member: "allUsers",
    });

    if (props.indexPagePath) {
      new GoogleStorageBucketObject(this, "indexPage", {
        bucket: this.siteBucket.name,
        name: "index.html",
        source: props.indexPagePath,
        contentType: "text/html",
      });
    }
    if (props.notFoundPagePath) {
      new GoogleStorageBucketObject(this, "notFoundPage", {
        bucket: this.siteBucket.name,
        name: "404.html",
        source: props.notFoundPagePath,
        contentType: "text/html",
      });
    }
  }
}
