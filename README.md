# growlvmpart
Quick and dirty python script to automatically detecting disk resize, expand lvm partitions and fs.

Working only with one scenario: you need to grow FS if free space less then barrier, FS is on LV, PV is in MBR/GPT(not tested) partition, lying on hypervisor's disk that can be resized online.

Not well tested. May be buggy.

## Requirements
* python2
* lvm2
* parted
* util-linux
* your FS utils

## Usage

```
./growlvmpart.py --path <mount point> --min <minimal free space> [--max <maximum free space>]
```
For example:
```
./growlvmpart.py --path /var/lib/docker --min 1500m --max 4g
```
Size in bytes. You can use some units [bkmgt].

## Algorithm
1. Exit if free space on FS greater then ```<minimum free space>```
2. Rescan schi devices and hosts
3. Resize underlying partition
4. Resize PV
5. Resize LV and FS to size ```<used space> + <maximum free space>```
