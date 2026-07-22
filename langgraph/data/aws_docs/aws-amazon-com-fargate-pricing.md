# AWS Fargate Pricing

<!-- 출처: https://aws.amazon.com/fargate/pricing/ -->

# AWS Fargate Pricing

## Pricing overview

With AWS Fargate, there are no upfront costs and you pay only for the resources you use. You pay for the amount of vCPU, memory, and storage resources consumed by your containerized applications running on Amazon Elastic Container Service (ECS) or Amazon Elastic Kubernetes Service (EKS).

## AWS Pricing Calculator

Calculate your AWS Fargate and architecture cost in a single estimate.

## AWS Fargate Pricing

AWS Fargate pricing is calculated based on the vCPU, memory, Operating Systems, CPU Architecture1, and storage resources used from the time you start to download your container image until the Amazon ECS Task or Amazon EKS2 Pod terminates, rounded up to the nearest second.

1 Windows Operating System and ARM CPU Architecture are currently only available for Amazon ECS.
2 See the regions where EKS Fargate is available https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/

## Pricing Details

Pricing is based on requested vCPU, memory, Operating Systems, CPU Architecture1, and storage resources for the Task or Pod. The five dimensions are independently configurable.

1 Windows Operating System and ARM CPU Architecture are currently only available for Amazon ECS.

-
Linux/X86
-
Linux /ARM
-
Windows/X86

-
Linux/X86
-
-
Linux /ARM
-
-
Windows/X86
-

### Fargate Spot Pricing for Amazon ECS

Fargate Spot allows customers to run interrupt-tolerant Amazon ECS Tasks* on spare capacity at up to a 70% discount off the regular Fargate price. With Fargate Spot, you pay the Spot price that is in effect for the time period your Amazon ECS Tasks are running. Fargate Spot prices are set by AWS Fargate and adjust gradually based on long-term trends in supply and demand for Fargate Spot capacity. The following table displays the current Spot price for vCPU-hour and GB-hour for each region.

-
Spot Linux/X86
-
Spot Linux/ARM

-
Spot Linux/X86
-
-
Spot Linux/ARM
-

* Fargate Spot for Amazon ECS is currently only available for Linux Operating System and x86 /ARM CPU Architecture.

### Fargate Ephemeral Storage Pricing

20 GB of ephemeral storage is available for all Fargate Tasks and Pods by default—you only pay for any additional storage that you configure.

### Supported Configurations

| CPU
|
Memory Values |
|---|---|
| 0.25 vCPU | 0.5 GB, 1 GB, and 2 GB |
| 0.5 vCPU | Min. 1 GB and Max. 4 GB, in 1 GB increments |
| 1 vCPU | Min. 2 GB and Max. 8 GB, in 1 GB increments |
| 2 vCPU | Min. 4 GB and Max. 16 GB, in 1 GB increments |
| 4 vCPU | Min. 8 GB and Max. 30 GB, in 1 GB increments |
| 8 vCPU | Min. 16 GB and Max. 60 GB, in 4 GB increments |
| 16 vCPU | Min. 32 GB and Max. 120 GB, in 8 GB increments |
| 32vCPU | 60GB, 120GB, and 244GB |



### Duration

Pricing is calculated per second with a 1-minute minimum. Duration is calculated from the time you start to download your container image (Docker pull) until the task terminates, rounded up to the nearest second.

For Windows containers, billing is calculated per second with a 5-minute minimum.

### Compute Savings Plan for Amazon ECS & Amazon EKS

Take advantage of Savings Plans if you have a consistent amount of Fargate usage. Savings Plans offer savings of up to 50% on your AWS Fargate usage in exchange for a commitment to use a specific amount of compute (measure in dollars per hour) for a one- or three-year term.

### Additional Charges

You may incur additional charges if your containers use other AWS services or transfers data. For example, if your containers use Amazon CloudWatch Logs for application logging, you are billed for CloudWatch usage. You will also incur a charge for the public IPv4 addresses associated with your Amazon ECS Tasks or Amazon EKS Pod. Please visit the public IPv4 address section of the VPC pricing page for more details.

For more information about AWS service pricing, see the pricing section of the relevant AWS service detail pages. Links to pricing for some of the commonly used services are listed below.

**Data Transfer: **You are billed at standard AWS data transfer rates.

* on this page GB = 1024^3 bytes

### Pricing Examples

*All examples below are based on price in US East (N. Virginia).*

-
### Example 1

Let’s say your service uses 5 ECS Tasks that run for 10 minutes (600 seconds) every day for a month (30 days) during which each ECS Task uses 1 vCPU, 2GB memory, and 30 GB ephemeral storage. Using the Linux/X86 pricing for US East (N. Virginia) Region where CPU cost: $0.000011244 per vCPU second, memory cost: $0.000001235 per GB per second, and ephemeral storage cost: $0.0000000308 per GB per second

**Monthly CPU charges**Total vCPU charges = (# of Tasks) x (# vCPUs) x (price per CPU-second) x (CPU duration per day by second) x (# of days)


Total vCPU charges = 5 x 1 x 0.000011244 x 600 x 30 =**$1.01****Monthly memory charges**

Total memory charges = (# of Tasks) x (memory in GB) x (price per GB) x (memory duration per day by second) x (# of days)

Total memory charges = 5 x 2 x 0.000001235 x 600 x 30 =**$0.22****Monthly ephemeral storage charges**

Total ephemeral storage charges = (# of Tasks) x (additional ephemeral storage in GB) x (price per GB) x (memory duration per day by second) x (# of days)

Additional ephemeral storage in GB: 30 - 20 = 10

Total ephemeral storage charges = 5 x 10 x 0.0000000308 x 600 x 30 =**$0.03****Monthly Fargate compute charges**Monthly Fargate compute charges = (monthly CPU charges) + (monthly memory charges) + (monthly ephemeral storage charges)


__Monthly Fargate compute charges = $1.01 + $0.22 + $0.03 = $1.26__ -
### Example 2

Let’s say your service runs on Arm-based AWS Graviton2-powered Fargate to optimize on price-performance. The service uses 5 ECS Tasks for 10 minutes (600 seconds) every day for a month (30 days) during which each ECS Task uses 1 vCPU, 2GB memory, and 30 GB ephemeral storage. Using the pricing for Linux/ARM in US East (N. Virginia) Region where CPU cost: $0.0000089944 per vCPU second, memory cost: $0.0000009889 per GB per second, and ephemeral storage cost: $0.0000000308 per GB per second.

**Monthly CPU charges**Total vCPU charges = (# of Tasks) x (# vCPUs) x (price per CPU-second) x (CPU duration per day by second) x (# of days)


Total vCPU charges = 5 x 1 x 0.0000089944 x 600 x 30 =**$0.81****Monthly memory charges**

Total memory charges = (# of Tasks) x (memory in GB) x (price per GB) x (memory duration per day by second) x (# of days)

Total memory charges = 5 x 2 x 0.0000009889 x 600 x 30 =**$0.18****Monthly ephemeral storage charges**

Total ephemeral storage charges = (# of Tasks) x (additional ephemeral storage in GB) x (price per GB) x (memory duration per day by second) x (# of days)

Additional ephemeral storage in GB: 30 - 20 = 10

Total ephemeral storage charges = 5 x 10 x 0.0000000308 x 600 x 30 =**$0.03****Monthly Fargate compute charges**

Monthly Fargate compute charges = (monthly CPU charges) + (monthly memory charges) + (monthly ephemeral storage charges)

__Monthly Fargate compute charges = $0.81 + $0.18 + $0.03 = $1.02__ -
### Example 3

For example, let’s say your service uses 10 EKS Pods running for 1 hour (3600 seconds) every day for a month (30 days) where each EKS Pod uses 0.25 vCPU and 1 GB memory working out of the US East (N. Virginia) Region.

**Monthly CPU charges**

Total vCPU charges = (# of Pods) x (# vCPUs) x (price per CPU-second) x (CPU duration per day by second) x (# of days)

Total vCPU charges = 10 x 0.25 x 0.000011244 x 3600 x 30 =**$3.04****Monthly memory charges**

Total memory charges = (# of Pods) x (memory in GB) x (price per GB) x (memory duration per day by second) x (# of days)

Total memory charges = 10 x 1 x 0.000001235 x 3600 x 30 =**$1.33****Monthly Fargate compute charges**

Monthly Fargate compute charges = (monthly CPU charges) + (monthly memory charges)

__Monthly Fargate compute charges = $3.04 + $1.33 = $4.37__ -
### Example 4

For example, your service uses 10 ECS Tasks running Windows for 1 hour (3600 seconds) every day for one month (30 days), where each ECS Task uses 1 vCPU and 2GB memory.

**Monthly CPU charges**Total vCPU charges = (# of Tasks) x (# vCPUs) x (price per CPU-second) x (CPU duration per day by second) x (# of days)


Total vCPU charges = 10 x 1 x 0.0000254167 x 3600 x 30 =**$27.45****Monthly Windows OS charges**Total memory charges = (# of Tasks) x (# vCPUs) x (OS price per CPU-second) x (CPU duration per day by second) x (# of days)


Total Windows OS charges = 10 x 1 x 0.0000127778 x 3600 x 30 =**$13.80****Monthly memory charges**Total memory charges = (# of Tasks) x (memory in GB) x (price per GB) x (memory duration per day by second) x (# of days)


Total memory charges = 10 x 2 x 0.0000027778 x 3600 x 30 =**$6.00****Monthly Fargate compute charges**Monthly Fargate compute charges = (monthly CPU charges) + (monthly Windows OS charges) + (monthly memory charges)


__Monthly Fargate compute charges = $27.45 + $13.80 + $6.00 = $47.25__

## Additional pricing resources

Easily calculate your monthly costs with AWS.

Contact AWS specialists to get a personalized quote.

## Did you find what you were looking for today?

Let us know so we can improve the quality of the content on our pages