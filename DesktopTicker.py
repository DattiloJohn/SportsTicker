"""
Desktop ticker: a slim, borderless, always-on-top bar across the top of the screen.

    python DesktopTicker.py

Right-click the bar to switch league (MLB / NFL / NBA) or quit. Drag it to move it.
"""

import json

import webview

from src.desktop import BAR_HEIGHT_PX, TickerController, host_page


class Api:
    """What the page's JavaScript can call. Underscore attributes are hidden from JS."""

    def __init__(self, controller: TickerController, window_getter):
        self._controller = controller
        self._window_getter = window_getter

    def set_league(self, name: str) -> None:
        self._controller.set_league(name)

    def quit(self) -> None:
        self._controller.stop()
        self._window_getter().destroy()


def main() -> None:
    window = None

    def push(markup: str) -> None:
        window.evaluate_js(f"setTicker({json.dumps(markup)})")

    controller = TickerController(push)
    screen = webview.screens[0]

    window = webview.create_window(
        "Sports Ticker",
        html=host_page(controller.league),
        js_api=Api(controller, lambda: window),
        x=screen.x,
        y=screen.y,
        width=screen.width,
        height=BAR_HEIGHT_PX,
        frameless=True,
        easy_drag=True,
        on_top=True,
        resizable=False,
        background_color="#000000",
    )

    def worker() -> None:
        window.events.loaded.wait()      # the page must exist before we push into it
        # x=0 in create_window is treated as "unset" and centres the window instead
        window.move(screen.x, screen.y)
        controller.run()

    webview.start(worker)
    controller.stop()


if __name__ == "__main__":
    main()
