from zywtool.zywtool import *  # noqa: F403

if __name__ == "__main__":
    import sys
    import tkinter as tk

    from zywtool.zywtool import App, core
    if len(sys.argv) >= 3 and sys.argv[1] == "--stats":
        core.print_stats(sys.argv[2])
    else:
        root = tk.Tk()
        App(root)
        root.mainloop()
