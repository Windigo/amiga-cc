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
    struct RastPort *rp;
    BOOL             running = TRUE;

    /* Open our own screen */
    struct NewScreen ns = {
        0, 0,
        640, 256,
        2,                          /* 2 bitplanes = 4 colors */
        0, 1,                       /* DetailPen, BlockPen */
        HIRES,
        CUSTOMSCREEN,
        NULL,
        (STRPTR)"Hello World",
        NULL,
        NULL
    };

    scr = (struct Screen *)OpenScreen(&ns);
    if (!scr)
        return RETURN_FAIL;

    /* Set palette: background = grey, text = white */
    SetRGB32(&scr->ViewPort, 0, 0xAAAAAAAA, 0xAAAAAAAA, 0xAAAAAAAA);  /* grey */
    SetRGB32(&scr->ViewPort, 1, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);  /* white */

    struct NewWindow nw = {
        40, 40,
        400, 100,
        0, 1,
        IDCMP_CLOSEWINDOW,
        WFLG_SIZEGADGET | WFLG_DRAGBAR | WFLG_DEPTHGADGET | WFLG_CLOSEGADGET | WFLG_ACTIVATE,
        NULL, NULL,
        (STRPTR)"Hello World",
        NULL, NULL,
        0, 0,
        640, 256,
        CUSTOMSCREEN
    };
    nw.Screen = scr;

    win = OpenWindow(&nw);
    if (win) {
        rp = win->RPort;

        /* Draw "Hello World!" in white on grey */
        SetAPen(rp, 1);             /* foreground = pen 1 (white) */
        SetBPen(rp, 0);             /* background = pen 0 (grey) */
        Move(rp, 30, 30);           /* position */
        Text(rp, "Hello World!", 12);

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
