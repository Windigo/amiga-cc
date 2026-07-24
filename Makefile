CC = vc
CFLAGS = -c99 +aos68k
LDFLAGS = -lamiga -lauto
OUTDIR = out
TARGET = $(OUTDIR)/main
ADF = $(OUTDIR)/boot.adf
FS_UAE = /Applications/FS-UAE.app/Contents/MacOS/fs-uae
FS_UAE_CONFIG = Amiga-CC.fs-uae
FS_UAE_FLOPPY_CONFIG = Amiga-CC-Floppy.fs-uae
XDFTOOL = /Users/windigo/Library/Python/3.9/bin/xdftool
VASM = vasmm68k_mot
PYTHON = /Volumes/M4-Lexar/Development/amiga/projects/amiga-cc/.venv/bin/python3

all: $(TARGET)

run: $(TARGET)
	$(FS_UAE) "$(FS_UAE_CONFIG)" &

# Pure assembly colortest (no libraries, red background test)
colortest: $(OUTDIR)/colortest

$(OUTDIR)/colortest: tools/colortest.asm | $(OUTDIR)
	$(VASM) -Fhunkexe -o $@ $<

# Standard AmigaDOS bootable floppy
floppy: $(ADF)

floppy-run: $(ADF)
	$(FS_UAE) "$(FS_UAE_FLOPPY_CONFIG)" &

# Trackloader-based floppy: completely bypasses AmigaDOS
# Binary loaded by custom bootblock, no Shell/filesystem needed
floppy-trackloader: $(OUTDIR)/boot_trackloader.adf

floppy-trackloader-run: $(OUTDIR)/boot_trackloader.adf
	$(FS_UAE) "$(FS_UAE_FLOPPY_CONFIG)" &

$(TARGET): src/main.c | $(OUTDIR)
	$(CC) $(CFLAGS) -o $(TARGET) src/main.c $(LDFLAGS)

$(OUTDIR):
	mkdir -p $(OUTDIR)

$(ADF): $(TARGET)
	rm -f $(ADF)
	$(XDFTOOL) $(ADF) create size=880 ofs
	$(XDFTOOL) $(ADF) format Empty ofs
	$(XDFTOOL) $(ADF) makedir s
	printf 'main\n' > /tmp/_startup_seq && $(XDFTOOL) $(ADF) write /tmp/_startup_seq s/startup-sequence && rm -f /tmp/_startup_seq
	$(XDFTOOL) $(ADF) write $(TARGET) main
	$(XDFTOOL) $(ADF) boot install

# Trackloader ADF: bootblock loads binary from track 0 sector 2+
# Completely independent of AmigaDOS, Shell, or filesystem
$(OUTDIR)/boot_trackloader.adf: $(TARGET) tools/build_trackloader_adf.py
	$(PYTHON) tools/build_trackloader_adf.py $(TARGET) $@

clean:
	rm -rf $(OUTDIR)
