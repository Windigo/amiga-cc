#include <proto/intuition.h>
#include <proto/dos.h>
#include <proto/exec.h>
#include <proto/graphics.h>
#include <intuition/intuition.h>
#include <intuition/screens.h>
#include <graphics/view.h>

int main() {
    struct Screen   *scr  = NULL;
    struct Window   *win  = NULL;
    BOOL             running = TRUE;

    /* Open our own screen with CLI-style palette:
       1 bitplane, grey background, white foreground */
    struct NewScreen ns = {
        0, 0,                       /* LeftEdge, TopEdge */
        640, 256,                   /* Width, Height */
        4,                          /* Depth (1 bitplane = 2 colors, like CLI) */
        0, 1,                       /* DetailPen, BlockPen */
        HIRES,                      /* ViewModes */
        CUSTOMSCREEN,               /* Type */
        NULL,                       /* Font */
        (STRPTR)"Compilation successful!", /* Title */
        NULL,                       /* Gadgets */
        NULL                        /* CustomBitMap */
    };

    scr = (struct Screen *)OpenScreen(&ns);
    if (!scr)
        return RETURN_FAIL;

    /* Set palette to match CLI: color 0 = grey ($AAA), color 1 = white ($FFF)
       32-bit fixed-point: component = 4-bit-value * 0x11111111 */
    SetRGB32(&scr->ViewPort, 0, 0xAAAAAAAA, 0xAAAAAAAA, 0xAAAAAAAA);  /* grey */
    SetRGB32(&scr->ViewPort, 1, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);  /* white */

    /* Window on our own screen */
    struct NewWindow nw = {
        20, 20,
        580, 150,
        0, 1,
        IDCMP_CLOSEWINDOW,
        WFLG_SIZEGADGET | WFLG_DRAGBAR | WFLG_DEPTHGADGET | WFLG_CLOSEGADGET | WFLG_ACTIVATE,
        NULL, NULL,
        (STRPTR)"Compilation successful !",
        NULL, NULL,
        0, 0,
        600, 400,
        CUSTOMSCREEN
    };
    nw.Screen = scr;

    win = OpenWindow(&nw);
    if (win) {
        while (running) {
            struct IntuiMessage *msg;
            WaitPort(win->UserPort);
            while ((msg = (struct IntuiMessage *)GetMsg(win->UserPort))) {
                if (msg->Class == IDCMP_CLOSEWINDOW)
                    running = FALSE;
                ReplyMsg((struct Message *)msg);
            }
        }
        CloseWindow(win);
    }

    CloseScreen(scr);
    return 0;
}