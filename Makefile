CC = vc
CFLAGS = -c99 +aos68k
LDFLAGS = -lamiga -lauto
OUTDIR = out
TARGET = $(OUTDIR)/main
FS_UAE = /Applications/FS-UAE.app/Contents/MacOS/fs-uae
FS_UAE_CONFIG = Amiga-CC.fs-uae

all: $(TARGET)

run: $(TARGET)
	$(FS_UAE) "$(FS_UAE_CONFIG)" &

$(TARGET): src/main.c | $(OUTDIR)
	$(CC) $(CFLAGS) -o $(TARGET) src/main.c $(LDFLAGS)

$(OUTDIR):
	mkdir -p $(OUTDIR)

clean:
	rm -rf $(OUTDIR)