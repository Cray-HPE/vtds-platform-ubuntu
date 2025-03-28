# vtds-platform-ubuntu

The ubuntu platform layer implementation for vTDS.

## Description

This repo provides the code and a base configuration to deploy the
platform layer of a Virtual Test and Development System (vTDS) cluster

Each platform implementation contains implementation specific code and
a fully defined base configuration capable of deploying the platform
resources of the cluster. The base configuration here, if used
unchanged, installs on the Provider Layer deployed Virtual Blades
the software packages needed to support KVM based virtual
machines and to define VxLAN based overlay networks. It also
installs the `sushy-tools` Redfish BMC emulator to provide
emulation of Redfish for virtual machines created under KVM
using libvirt.

The core driver mechanism and a brief introduction to the vTDS
architecture and concepts can be found in the [vTDS Core Project
Repository](https://github.com/Cray-HPE/vtds-core/tree/main).
