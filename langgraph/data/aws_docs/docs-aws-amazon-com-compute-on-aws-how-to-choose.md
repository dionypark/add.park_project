# Choosing an AWS compute service for your workload

<!-- 출처: https://docs.aws.amazon.com/compute-on-aws-how-to-choose/ -->

# Choosing an AWS compute service for your workload

Find the AWS compute services and tools that are the best fit for your needs and your organization.

## Overview of AWS compute services

AWS compute services are designed to meet the varied demands of modern applications, from small-scale projects to enterprise-grade solutions. These services provide scalable computing power that helps you to build, deploy, and manage applications. Whether you need to launch virtual machines, run containerized applications, or run code without managing servers, AWS compute services provide the flexibility to match your specific workload needs.

## Key concepts

Choosing the right AWS compute service involves balancing the following factors to match your specific workload needs, technical requirements, and business objectives to help you optimize for performance, cost, and ease of management.

### Workload type and requirements

As you choose AWS compute services, the foundation lies in understanding your specific workload characteristics and performance requirements. Different application types demand distinct compute capabilities - batch processing jobs need robust, scalable capacity that can be scaled down after completion, while web applications require high availability and dynamic scaling to handle fluctuating traffic. Machine learning workloads present unique challenges with computationally intensive training phases requiring specialized hardware like GPUs, followed by inference phases needing highly available, low-latency environments. Performance optimization involves matching CPU/GPU power, memory capacity, storage I/O, and network bandwidth to your application's specific demands, whether that's compute-optimized instances for complex calculations or memory-optimized instances for large databases.

### Scalability and management considerations

Scalability and management overhead are critical factors that significantly impact operational efficiency. AWS offers both vertical scaling (adding more power to existing resources) and horizontal scaling (adding more instances), with services like Auto Scaling and serverless offerings providing automatic adjustment capabilities.

Management overhead varies dramatically across services - from hands-on EC2 instance management requiring dedicated operations teams to serverless solutions like AWS Lambda that abstract away infrastructure concerns entirely. Services like AWS Elastic Beanstalk provide a middle ground, handling OS patches and runtime management while allowing you to focus on application code. The key is balancing your organization's operational capacity and need for control against the convenience of managed services.

## Use cases

Match the right compute service to your workload needs for optimal performance and cost efficiency.

To get the most from your investment in these services, it's important to choose the right services for the right task or use case, whether it involves processing simple web app requests or running complex, data-intensive algorithms. You can also use multiple types of compute solutions in a single workload, as each one has its own advantages. Here are some common use cases and services that can help:

Deploy and scale full-stack applications while minimizing infrastructure management tasks. This approach automates application operations and infrastructure provisioning, allowing development teams to concentrate on writing code and implementing business logic.

Run your code in response to events without managing any infrastructure. Your code runs only when needed, and scales automatically from a few requests per day to thousands per second, with you paying only for the compute time consumed.

Deploy, manage, and scale containerized applications without worrying about the complexity of the underlying infrastructure. Container orchestration services handle tasks like scheduling, cluster management, and service discovery, allowing you to focus on application development rather than operational overhead.

Deploy containerized applications without provisioning or managing the underlying servers. The compute resources automatically scale to match your application's needs, eliminating capacity planning and infrastructure management while you focus on container configuration and application code.

Run batch computing workloads efficiently without managing the underlying infrastructure. Computing resources are automatically provisioned based on volume and specific requirements of your jobs, with scheduling and resource allocation handled dynamically while you focus on analyzing results.

## Compare services

Now that you know how to evaluate your compute options, you're ready to choose which AWS compute services might be a good fit for your organizational requirements.

The following graphic shows categories of compute services available in AWS, and lists services in each category.

AWS compute services provide secure and resizable compute capacity in the cloud. AWS offers a range of compute services to meet various application requirements. These include Amazon EC2 for resizable virtual servers, AWS Elastic Beanstalk for deploying web applications on your choice of a number of popular platforms, Lambda for serverless computing, Amazon ECS and Amazon EKS for container orchestration, and AWS Fargate for serverless containers.

AWS Batch facilitates batch computing. AWS hybrid and edge services such as Local Zones and AWS Outposts bring AWS infrastructure and services to metropolitan areas, on-premises locations, and edge sites, addressing requirements for low latency, digital sovereignty, and local data processing. Additionally, Amazon EC2 Auto Scaling automatically adjusts capacity. These services cater to different workload needs, from basic virtual machines (VMs) to fully managed serverless and container solutions.

Compute category | What is it optimized for? | Compute services |
|---|---|---|
Amazon EC2 | Providing scalable high-performance computing resources for CPU-intensive workloads. | |
Container services | Helping your teams focus on building applications rather than the runtime environment or managing a control plane. | |
Serverless compute | Minimizing your AWS management overhead, allowing you to focus on implementing your business logic. | |
On-premises and edge compute | Allowing you to run familiar AWS interfaces to your premises and the edge, providing lower latency
and local data processing needs. | |
Cost and savings optimization | Helping you reduce your costs for your workloads. | |
Elastic Load Balancing | Increasing the availability and fault tolerance of your applications. |

## Start building

You should now have a clear understanding of each AWS compute service (and the supporting AWS tools and services) and which one might be the best fit for your organization and use case.

To explore how to use and learn more about each of the available AWS compute services, we have provided a pathway to learn how each of the services work. The following section provides links to in-depth documentation, hands-on tutorials, and resources to get you started.

**Tutorial: Get started with Amazon EC2 Linux instances**

Use this tutorial to get started with Amazon EC2. You'll learn how to launch, connect to, and use a Linux instance.

**Tutorial: Get started with Amazon EC2 Windows instances**

Use this tutorial to get started with Amazon EC2. You'll learn how to launch, connect to, and use a Windows instance.

**Amazon EC2 instance types**

This guide provides an overview of the various families of EC2 instance types and discusses the appropriate application for each family.

**Get Started with Amazon EC2 Graviton instances**

This guide will help you get started with Amazon EC2 Graviton instances and provides steps-by-step instructions to migrate your workload to Graviton.

**Get started with Amazon EC2 Auto Scaling**

In this tutorial, you set up an Auto Scaling group, terminate your instance, and verify the instance was removed from service and replaced.

**Tutorial: Scale the size of your Auto Scaling Group**

In this tutorial, you learn how to scale your Auto Scaling group using either manual scaling, scheduled scaling, dynamic scaling, or predictive scaling.

**Amazon EC2 Auto Scaling FAQs**

Dive deep into the intricacies of EC2 Auto Scaling by reviewing the FAQ.

**Get started with EC2 Image Builder**

This guide will help you set up your environment and create an automated image pipeline for the first time.

**Building golden images using Amazon EC2 Image Builder workshop**

This workshop will guide you through creating an EC2 Image Builder pipeline and then developing your own custom components.

**Implementing up-to-date images with automated EC2 Image Builder pipelines**

This blog post demonstrates how to automatically keep your base or standard images current, incorporating patches and any other changes using EC2 Image Builder pipelines.

**Get started with AWS Elastic Beanstalk**

This tutorial walks you through creating, exploring, updating, and deleting an Elastic Beanstalk application. It takes less than an hour to complete.

**Security best practices for AWS Elastic Beanstalk**

This guide provides you with general guidelines for securing your Elastic Beanstalk application.

**Creating an ECS managed Docker environment with the Elastic Beanstalk console**

In this tutorial, you’ll implement an ECS managed Docker environment that uses two containers.

**Launch a Linux virtual machine with Amazon Lightsail**

In this tutorial, you create an Amazon Linux instance in Amazon Lightsail in seconds. After the instance is up and running, you connect to it via SSH within the Lightsail console using the browser-based SSH terminal.

## Resources

### Learn

Explore whitepapers to help you get started and learn best practices for compute services and use cases.### Build

Explore vetted solutions and architectural guidance for common use cases for compute.### Discover

Explore reference architecture diagrams for compute on AWS.