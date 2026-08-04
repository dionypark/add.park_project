# Amazon EBS volume types

<!-- 출처: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-volume-types.html -->

Amazon EBS provides the following volume types, which differ in performance characteristics and price, so that you can tailor your storage performance and cost to the needs of your applications.

###### Important

There are several factors that can affect the performance of EBS volumes, such as instance configuration, I/O characteristics, and workload demand. To fully use the IOPS provisioned on an EBS volume, use EBS–optimized instances. For more information about getting the most out of your EBS volumes, see Amazon EBS volume performance.

For more information about pricing, see Amazon EBS
Pricing

**Volume types**

## Solid state drive (SSD) volumes

SSD-backed volumes are optimized for transactional workloads involving frequent read/write
operations with small I/O size, where the dominant performance attribute is IOPS. SSD-backed
volume types include **General Purpose SSD** and **Provisioned IOPS SSD
**. The following is a summary of the use cases and characteristics of SSD-backed
volumes.

| Amazon EBS General Purpose SSD volumes | Amazon EBS Provisioned IOPS SSD volumes | |||
|---|---|---|---|---|
Volume type |
`gp3` 6 |
`gp2` |
`io2` Block Express |
`io1` |
Durability |
99.8% - 99.9% durability (0.1% - 0.2% annual failure rate) | 99.999% durability (0.001% annual failure rate) | 99.8% - 99.9% durability (0.1% - 0.2% annual failure rate) | |
Use cases |
|
Workloads that require:
|
|
|
Volume size |
1 GiB - 64 TiB | 1 GiB - 16 TiB | 4 GiB - 64 TiB | 4 GiB - 16 TiB |
Max IOPS |
80,000 3 (25.6 KiB I/O 4) |
16,000 (16 KiB I/O 4) |
256,000 3 (16 KiB I/O 4) |
64,000 (16 KiB I/O 4) |
Max throughput |
2,000 MiB/s | 250 MiB/s 1 |
4,000 MiB/s | 1,000 MiB/s 2 |
Amazon EBS Multi-attach |
Not supported | Supported | ||
NVMe reservations |
Not supported | Supported | Not supported | |
Boot volume |
Supported |

1 The throughput limit is between 128 MiB/s and 250
MiB/s, depending on the volume size. For more information, see gp2 volume performance. Volumes created before **December 3,
2018** that have not been modified since creation might not reach full performance
unless you modify the volume.

2 To achieve maximum throughput of 1,000 MiB/s, the volume must
be provisioned with 64,000 IOPS and it must be attached to a
Nitro-based instance. Volumes created before **December
6, 2017** that have not been modified since creation might not reach full performance
unless you modify the volume.

3
Nitro-based instances support volumes provisioned with up to 256,000 IOPS. Other instance
types can be attached to volumes provisioned with up to 64,000 IOPS, but can achieve up to 32,000
IOPS.

4 Represents the required I/O size to reach maximum IOPS within
the volume's throughput limit.

5 `io2`

Block Express volumes are designed to deliver an average
latency of under 500 microseconds for 16KiB I/O operations.

6 On Outposts, gp3 volumes support sizes up to 16 TiB, IOPS up to
16,000, and throughput up to 1,000 MiB/s.

For more information about the SSD-backed volume types, see the following:

## Hard disk drive (HDD) volumes

HDD-backed volumes are optimized for large streaming workloads where the dominant
performance attribute is throughput. HDD volume types include **
Throughput Optimized HDD** and **Cold HDD**. The following
is a summary of the use cases and characteristics of HDD-backed volumes.

| Throughput Optimized HDD volumes | Cold HDD volumes | |
|---|---|---|
Volume type |
`st1` |
`sc1` |
Durability |
99.8% - 99.9% durability (0.1% - 0.2% annual failure rate) | |
Use cases |
|
|
Volume size |
125 GiB - 16 TiB | |
Max IOPS per volume (1 MiB I/O) |
500 | 250 |
Max throughput per volume |
500 MiB/s | 250 MiB/s |
Amazon EBS Multi-attach |
Not supported | |
Boot volume |
Not supported |

For more information about the Hard disk drives (HDD) volumes, see Amazon EBS Throughput Optimized HDD and Cold HDD volumes.

## Previous generation volumes

Magnetic (`standard`

) volumes are previous generation volumes that are backed by magnetic
drives. They are suited for workloads with small datasets where data is accessed infrequently
and performance is not of primary importance. These volumes deliver approximately 100 IOPS on
average, with burst capability of up to hundreds of IOPS, and they can range in size from 1 GiB
to 1 TiB.

###### Tip

Magnetic is a previous generation volume type. If you need higher performance or performance consistency than previous-generation volumes can provide, we recommend using one of the current generation volume types.

The following table describes previous-generation EBS volume types.

| Magnetic | |
|---|---|
Volume type |
`standard` |
Use cases |
Workloads where data is infrequently accessed |
Volume size |
1 GiB-1 TiB |
Max IOPS per volume |
40–200 |
Max throughput per volume |
40–90 MiB/s |
Boot volume |
Supported |