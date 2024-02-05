# vtds-platform-ubuntu

The ubuntu platform layer implementation for vTDS.

## Description

This repo provides the code and a base configuration to deploy the
platform layer of a Virtual Test and Development System (vTDS) cluster

Each platform implementation contains implementation specific code and
a fully defined base configuration capable of deploying the platform
resources of the cluster. The base configuration here, if used
unchanged, defines the resources needed to construct a vTDS platform
consisting of Ubuntu based linux VMs connected across the provider's
network using virtual layer 2 networks encapsulated across the
provider's IP interconnect.

The core driver mechanism and a brief introduction to the vTDS
architecture and concepts can be found in the [vTDS Core Project
Repository](https://github.com/Cray-HPE/vtds-core/tree/main).
