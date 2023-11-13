# vtds-platform-common
The common vTDS Platform layer plugin
## Description
This repository provides an implementation of the vTDS Platform layer that should
be usable in most vTDS configurations to provide a set of Virtual Blades, external
network connections, and Blade Interconnect networks on which to build a vTDS cluster.
The contents include an implementation of the Platform API and a base configuration. The
Platform API implementation will run on any Provider layer implementation and manage the
configured set of Virtual Blades. The base configuration can be used unchanged to build
a platform consisting of an application specified number of Virtual Blade hosts running
Ubuntu linux and interconnected by an application specified set of Blade Interconnect
networks. User supplied configuration overlays can alter that configuration as needed.
Configuration of things like Virtual Blades, Virtual Nodes, Blade Interconnect networks
and Virtual Node Interconnect networks and so forth are driven by layers above this in
the vTDS architecture.

The core driver mechanism and a brief introduction to the vTDS architecture and concepts
can be found in the [vTDS Core Project Repository](https://github.com/Cray-HPE/vtds-core/tree/main).
