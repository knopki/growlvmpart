# growlvmpart
Quick and dirty python script to automatically detecting disk resize, expand lvm partitions and fs.

Working only with one scenario: you need to grow FS if free space less then barrier, FS is on LV, PV is in MBR/GPT(not tested) partition, lying on hypervisor's disk that can be resized online.

Not well tested. May be buggy.

## Requirements
* python 2.7
* growpart
* parted
* lvm utils

## Usage

```
./growlvmpart.py <mount point> <minimal free space> <maximum free space>
```
For example:
```
./growlvmpart.py /var/lib/docker 1500m 4g
```
Size in bytes. You can use some units [bkmgt].

## Algorithm
1. Exit if free space on FS greater then ```<minimum free space>```
2. Rescan schi devices and hosts
3. Resize underlying partition
4. Resize PV
5. Resize LV and FS to size ```<used space> + <maximum free space>```
