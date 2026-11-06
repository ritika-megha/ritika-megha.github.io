"""Interaction checks against a built site and an isolated Chromium/Edge CDP session.

Requires websocket-client. Start the static preview at :4000 and a headless
Chromium-compatible browser with --remote-debugging-port=9222 first.
"""

import base64
import json
import os
import time
import urllib.request
from pathlib import Path

import websocket


class Browser:
    def __init__(self):
        with urllib.request.urlopen("http://127.0.0.1:9222/json") as response:
            pages = json.load(response)
        page = next(item for item in pages if item["type"] == "page")
        self.ws = websocket.create_connection(
            page["webSocketDebuggerUrl"], origin="http://localhost:9222", timeout=10
        )
        self.sequence = 0
        self.errors = []
        self.call("Page.enable")
        self.call("Runtime.enable")
        self.call("Network.enable")
        self.call("Network.setCacheDisabled", {"cacheDisabled": True})

    def call(self, method, params=None):
        self.sequence += 1
        self.ws.send(json.dumps({"id": self.sequence, "method": method, "params": params or {}}))
        while True:
            response = json.loads(self.ws.recv())
            if response.get("method") == "Runtime.exceptionThrown":
                self.errors.append(response["params"])
            if response.get("id") == self.sequence:
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result["result"].get("value")

    def wait(self, expression):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if self.evaluate(f"Boolean({expression})"):
                return
            time.sleep(0.05)
        raise AssertionError("Timed out: " + expression)

    def click(self, selector):
        self.evaluate(f"document.querySelector({json.dumps(selector)}).click()")

    def mouse(self, kind, x, y, button="none", buttons=0):
        self.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": button, "buttons": buttons, "clickCount": 1 if button != "none" else 0})

    def drag(self, start_x, end_x, y):
        self.mouse("mouseMoved", start_x, y)
        self.mouse("mousePressed", start_x, y, "left", 1)
        for step in range(1, 13):
            self.mouse("mouseMoved", start_x + (end_x - start_x) * step / 12, y, "none", 1)
            time.sleep(0.018)
        # Pause before release so this test checks displacement independently of momentum.
        time.sleep(0.13)
        self.mouse("mouseReleased", end_x, y, "left")

    def screenshot(self, path):
        result = self.call("Page.captureScreenshot", {"format": "png"})
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(base64.b64decode(result["data"]))


browser = Browser()
base_url = os.environ.get("PORTFOLIO_TEST_URL", "http://127.0.0.1:4000/")
checks = []


def check(label, expression):
    assert browser.evaluate(expression), label
    checks.append(label)


browser.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
boot_token = time.time()
browser.call("Page.addScriptToEvaluateOnNewDocument", {"source": f"window.portfolioTestBoot = {boot_token}; try {{ sessionStorage.removeItem('portfolio-project'); }} catch (_) {{}}"})
browser.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
window.portfolioTestAudio = {contexts: [], ticks: 0};
const NativeAudio = window.AudioContext;
window.AudioContext = class extends NativeAudio {
  constructor(...args) { super(...args); portfolioTestAudio.contexts.push(this); }
  createBufferSource() {
    const source = super.createBufferSource(), start = source.start.bind(source);
    source.start = (...args) => { portfolioTestAudio.ticks++; return start(...args); };
    return source;
  }
};
try { localStorage.setItem('portfolio-sound', 'off'); } catch (_) {}
"""})
browser.call("Page.navigate", {"url": base_url})
browser.wait(f"window.portfolioTestBoot === {boot_token} && document.readyState === 'complete'")
browser.wait("document.body && document.body.classList.contains('has-carousel') && document.querySelector('.disc[aria-current]')")
browser.wait("[...document.querySelectorAll('.disc[aria-current] img')].every(i => i.complete && i.naturalWidth > 0)")
project_count = browser.evaluate("document.querySelectorAll('.disc').length")
first_project = browser.evaluate("document.querySelector('.disc').dataset.title")
second_project = browser.evaluate("document.querySelectorAll('.disc')[1].dataset.title")
check("All configured projects render", "document.querySelectorAll('.disc').length >= 6")
check("Front-page social links", "document.querySelector('.project-info .social-links a[href=\"mailto:ritikamegha.vocation@gmail.com\"]') !== null")
def choose_theme(value):
    browser.evaluate(f"(() => {{const picker=document.querySelector('[data-theme-picker]'); picker.value={json.dumps(value)}; picker.dispatchEvent(new Event('change', {{bubbles:true}}));}})()")

choose_theme('auto')
browser.call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'dark'}]})
browser.wait("document.documentElement.dataset.theme === 'dark'")
check('Auto theme follows dark device setting', "document.querySelector('[data-theme-picker]').value === 'auto'")
browser.screenshot('docs/previews/desktop-dark.png')
choose_theme('light')
check('Light choice overrides dark device setting', "document.documentElement.dataset.theme === 'light'")
choose_theme('dark')
browser.call('Page.reload')
time.sleep(0.25)
browser.wait("document.readyState === 'complete' && document.body.classList.contains('has-carousel')")
check('Dark preference persists after reload', "document.documentElement.dataset.theme === 'dark' && document.querySelector('[data-theme-picker]').value === 'dark'")
browser.call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': 'light'}]})
check('Explicit dark choice ignores device changes', "document.documentElement.dataset.theme === 'dark'")
choose_theme('auto')
browser.wait("document.documentElement.dataset.theme === 'light'")
check('Auto theme follows light device setting', "getComputedStyle(document.documentElement).colorScheme === 'light'")
check('Small metadata is semibold', "Number(getComputedStyle(document.querySelector('.project-facts')).fontWeight) >= 600")
check("Initial selection matches configured project order", f"document.querySelector('#project-title').textContent === {json.dumps(first_project)}")
check("Previous disabled at start", "document.querySelector('#previous-project').disabled")
check("Selected destination matches project configuration", "(() => {const disc=document.querySelector('.disc[aria-current]'), link=document.querySelector('#open-project'); return link.href === disc.href && (disc.dataset.destination === 'internal' ? !link.hasAttribute('target') : link.target === '_blank');})()")
browser.screenshot("docs/previews/desktop.png")

browser.click("#next-project")
browser.wait("document.querySelector('#current-number').textContent === '02'")
check("Next updates project metadata", f"document.querySelector('#project-title').textContent === {json.dumps(second_project)}")
pages_before = {item['targetId'] for item in browser.call('Target.getTargets')['targetInfos'] if item['type'] == 'page'}
browser.click(".disc[data-index='3']")
browser.wait("document.querySelector('#current-number').textContent === '04'")
pages_after = {item['targetId'] for item in browser.call('Target.getTargets')['targetInfos'] if item['type'] == 'page'}
assert pages_after == pages_before, "Neighbor click opened a new tab."
checks.append("Neighbor click centers without opening a new tab")
browser.evaluate("document.querySelector('#carousel').focus()")
browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Home", "code": "Home"})
browser.wait("document.querySelector('#current-number').textContent === '01'")
time.sleep(0.5)

browser.evaluate("window.openAttempts = 0; document.querySelector('#carousel').addEventListener('click', event => { if (!event.defaultPrevented && event.target.closest('.disc')) window.openAttempts++; event.preventDefault(); });")
browser.drag(760, 430, 440)
browser.wait("document.querySelector('#current-number').textContent === '02'")
check("Drag does not open a project", "window.openAttempts === 0")
time.sleep(0.5)
browser.click(".disc[aria-current]")
check("Centered disc permits opening the project", "window.openAttempts === 1")
browser.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": 720, "y": 450, "deltaX": 0, "deltaY": 650})
browser.wait("Number(document.querySelector('#current-number').textContent) >= 3")
time.sleep(0.5)
checks.append("Wheel advances carousel")

browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "End", "code": "End"})
browser.wait(f"Number(document.querySelector('#current-number').textContent) === {project_count}")
check("Next disabled at end", "document.querySelector('#next-project').disabled")
if browser.evaluate("document.querySelector('.disc[href$=\"/work/testpage/\"]') !== null"):
    custom_index = browser.evaluate("Number(document.querySelector('.disc[href$=\"/work/testpage/\"]').dataset.index)")
    browser.click('.disc[href$="/work/testpage/"]')
    browser.wait(f"Number(document.querySelector('#current-number').textContent) === {custom_index + 1}")
    check("Custom page uses an internal destination in the live carousel", "document.querySelector('#open-project').href.endsWith('/work/testpage/') && !document.querySelector('#open-project').hasAttribute('target')")
    browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "End", "code": "End"})
    browser.wait(f"Number(document.querySelector('#current-number').textContent) === {project_count}")
browser.click("[data-dialog='index-dialog']")
check("Index opens and lists destinations", f"document.querySelector('#index-dialog').open && document.querySelectorAll('.project-index a').length === {project_count}")
browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
browser.wait("!document.querySelector('#index-dialog').open")
checks.append("Escape closes dialog")
browser.click("[data-dialog='about-dialog']")
check("About opens", "document.querySelector('#about-dialog').open")
browser.click("#about-dialog .close-dialog")

browser.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
browser.click("#previous-project")
browser.wait(f"Number(document.querySelector('#current-number').textContent) === {project_count - 1}")
checks.append("Reduced-motion navigation")

for width, height in [(1024, 768), (768, 1024), (390, 844), (320, 667), (844, 390)]:
    browser.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 600})
    time.sleep(0.12)
    check(f"No horizontal page overflow at {width}x{height}", "document.documentElement.scrollWidth <= innerWidth")
    check(f"View project link stays accessible at {width}x{height}", "(() => {const r=document.querySelector('#open-project').getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.top >= 0;})()")
    check(f"Social links fit at {width}x{height}", "[...document.querySelectorAll('.project-info .social-links a')].every(a => {const r=a.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth;})")
    check(f"Theme control fits at {width}x{height}", "(() => {const r=document.querySelector('[data-theme-picker]').getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth;})()")

browser.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
browser.call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1})
browser.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]})
browser.evaluate("document.querySelector('#carousel').focus()")
browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Home", "code": "Home"})
browser.wait("document.querySelector('#current-number').textContent === '01'")
time.sleep(0.6)
browser.evaluate("document.activeElement.blur()")
browser.screenshot("docs/previews/mobile.png")
check("No sound toggle is rendered", "document.querySelector('#carousel-sound') === null")
check("Touch regression starts on a disc", "document.elementFromPoint(270,530).closest('.disc') !== null")
browser.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 270, "y": 530}]})
# A small first movement transfers implicit capture from the disc to the stage.
# It must keep dragging rather than prematurely settling back to the first disc.
browser.call("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": 255, "y": 530}]})
time.sleep(0.08)
check("Capture transfer keeps touch drag active", "document.querySelector('#carousel').classList.contains('is-dragging')")
for x in [240, 220, 190, 160, 130, 100, 70]:
    browser.call("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": 530}]})
    time.sleep(0.03)
time.sleep(0.15)
browser.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
browser.wait("document.querySelector('#current-number').textContent === '02'")
checks.append("Touch swipe advances one project")
check("Touch release clears dragging state", "!document.querySelector('#carousel').classList.contains('is-dragging')")
check("Swipe plays ratchet ticks", "portfolioTestAudio.ticks > 1")
browser.wait("portfolioTestAudio.contexts.length === 1 && portfolioTestAudio.contexts[0].state === 'running'")
tick_count = browser.evaluate('portfolioTestAudio.ticks')
browser.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 90, "y": 530}]})
for x in [105, 130, 160, 190, 220, 250, 280]:
    browser.call("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": 530 - (x - 90) * 0.25}]})
    time.sleep(0.03)
time.sleep(0.15)
browser.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
browser.wait("document.querySelector('#current-number').textContent === '01'")
checks.append("Diagonal reverse swipe returns to previous project")
check("Sound stays on without a toggle or saved preference", f"portfolioTestAudio.ticks > {tick_count}")
for label, x, start_y, end_y, expected in [('up', 360, 550, 350, '02'), ('down', 360, 400, 600, '01'), ('over project details', 180, 300, 100, '02')]:
    page_scroll = browser.evaluate('scrollY')
    browser.call('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': start_y}]})
    for i in range(1, 13):
        browser.call('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': start_y + (end_y - start_y) * i / 12}]})
        time.sleep(0.03)
    time.sleep(0.15)
    browser.call('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    browser.wait(f"document.querySelector('#current-number').textContent === '{expected}'")
    check(f"Vertical swipe {label} moves discs without scrolling the page", f"scrollY === {page_scroll}")
check("Pinch zoom remains permitted", "getComputedStyle(document.querySelector('#carousel')).touchAction === 'pinch-zoom'")

browser.call("Emulation.setScriptExecutionDisabled", {"value": True})
browser.call("Page.reload")
browser.wait("document.readyState === 'complete'")
check("No-JavaScript project links remain available", f"getComputedStyle(document.querySelector('.project-fallback')).display !== 'none' && document.querySelectorAll('.project-fallback a').length === {project_count}")
browser.call("Emulation.setScriptExecutionDisabled", {"value": False})
assert not browser.errors, browser.errors
checks.append("No uncaught JavaScript exceptions")
print(json.dumps({"passed": len(checks), "checks": checks}, indent=2))
browser.ws.close()
