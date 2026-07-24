CC = vc
CFLAGS = -c99 +aos68k
LDFLAGS = -lamiga -lauto
OUTDIR = out
TARGET = $(OUTDIR)/window
FS_UAE = /Applications/FS-UAE.app/Contents/MacOS/fs-uae
FS_UAE_CONFIG = Amiga-CC.fs-uae

all: $(TARGET)

run: $(TARGET)
	$(FS_UAE) "$(FS_UAE_CONFIG)" &

$(TARGET): window.c | $(OUTDIR)
	$(CC) $(CFLAGS) -o $(TARGET) window.c $(LDFLAGS)

$(OUTDIR):
	mkdir -p $(OUTDIR)

clean:
	rm -rf $(OUTDIR)
