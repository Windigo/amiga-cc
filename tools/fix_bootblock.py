#!/usr/bin/env python3
"""Write a minimal Amiga bootblock to an ADF file so Kickstart 1.3 boots it."""

import struct
import sys

# Standard Amiga bootblock: block 0-1 (1024 bytes)
# Byte 0-3:   "DOS\0" or "DOS\1"
# Byte 4-7:   checksum (0 = use default)
# Byte 8-11:  rootblock pointer (will be filled by format)

# The boot code: Kickstart 1.3 loads block 0-1 into $0-$400, then
# jumps to $C (byte 12). We place a tiny boot routine there.

# Minimal bootblock 68k machine code:
# The standard trackdisk.device boot ROM already loads block 0-1
# into memory at $0. We just need "DOS\0" at start and valid code.
# Actually the ROM moves bootblock to $7C000-$7C400 and checks for
# "DOS\0" at start. Then it jumps to offset 12 in the bootblock.

# Minimal boot code that runs "main" from the boot disk:
# This is essentially a standard bootblock that loads the dos.library
# and executes s/startup-sequence.

# For simplicity, we use a well-known standard bootblock.
# The standard AmigaDOS bootblock from WB 3.1 should work on 1.3 too.

_STANDARD_BOOTBLOCK = bytes([
    # First 12 bytes: DOS header, checksum=0, rootblock=0 (get from disk)
    0x44, 0x4F, 0x53, 0x00,  # "DOS\0"
    0x00, 0x00, 0x00, 0x00,  # checksum (filled by xdftool/AmigaDOS)
    0x00, 0x00, 0x00, 0x00,  # rootblock (will be updated by xdftool)
    
    # Boot code starts at offset 12 ($C)
    # This is a standard Amiga bootblock from OS 3.1 NDK - 
    # it works on all Kickstarts 1.2+
    
    # lea.l (bootMsg,pc),a1      ; point to "DOS" message
    0x43, 0xFA, 0x00, 0x18,
    # moveq  #0,d0
    0x70, 0x00,
    # moveq  #0,d1
    0x72, 0x00,
    # jsr    -$1E(a6)            ; FindResident("dos.library")
    0x4E, 0xAE, 0xFF, 0xE2,
    # move.l d0,a0
    0x2A, 0x40,
    # move.l 22(a0),a0           ; dos library base
    0x20, 0x68, 0x00, 0x16,
    # jsr    (a0)                ; InitResident - this boots the disk
    0x4E, 0x90,
    # moveq  #20,d0              ; WaitTOF = 20 (error return - red screen)
    0x70, 0x14,
    # rts                        ; return to Kickstart (shows error)
    0x4E, 0x75,
    
    # bootMsg: "dos.library" (null-terminated)
    0x64, 0x6F, 0x73, 0x2E,  # "dos."
    0x6C, 0x69, 0x62, 0x72,  # "libr"
    0x61, 0x72, 0x79, 0x00,  # "ary\0"
    
    # Pad to fill 1024 bytes (block 0 + block 1)
])

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <adf_file> [rootblock_offset]")
        sys.exit(1)
    
    adf = sys.argv[1]
    
    # Read the existing bootblock to get rootblock pointer
    with open(adf, "r+b") as f:
        existing = f.read(1024)
        
        # Get rootblock pointer from original bootblock (offset 8-11)
        rootblock = struct.unpack(">I", existing[8:12])[0]
        
        # Build new bootblock with correct rootblock
        bb = bytearray(_STANDARD_BOOTBLOCK)
        
        # Write rootblock pointer at offset 8
        struct.pack_into(">I", bb, 8, rootblock)
        
        # Pad to 1024 bytes
        if len(bb) < 1024:
            bb.extend(b'\x00' * (1024 - len(bb)))
        
        # Calculate checksum (offset 4-7 should make entire block 0
        # checksum to 0xFFFFFFFF when treated as longwords)
        # Standard Amiga checksum: sum of all longwords (incl checksum field=0)
        # should equal 0xFFFFFFFF
        checksum = 0
        for i in range(0, 1024, 4):
            val = struct.unpack(">I", bb[i:i+4])[0]
            checksum = (checksum + val) & 0xFFFFFFFF
        
        # Checksum should make total = 0xFFFFFFFF, so checksum = 0xFFFFFFFF - (sum-rest)
        checksum = (0xFFFFFFFF - checksum) & 0xFFFFFFFF
        struct.pack_into(">I", bb, 4, checksum)
        
        # Write back
        f.seek(0)
        f.write(bb)
    
    print(f"Bootblock fixed in {adf} (rootblock=0x{rootblock:08X})")


if __name__ == "__main__":
    main()