"""Verify homepage resources and interactions using an installed Chromium browser."""
from __future__ import annotations

import argparse
import hashlib
import io
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
import urllib.parse
import zipfile

from playwright.sync_api import sync_playwright

WEB = Path(__file__).resolve().parent
CHECKS = WEB / ".checks"


class DocumentAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids = []
        self.resources = []
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        for key in ("src", "href"):
            url = values.get(key)
            if not url:
                continue
            if url.startswith("#"):
                self.anchors.append(url[1:])
            elif not urllib.parse.urlparse(url).scheme:
                self.resources.append(urllib.parse.unquote(url.split("#")[0]))


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", type=Path)
    args = parser.parse_args()
    audit = DocumentAudit()
    audit.feed((WEB / "index.html").read_text(encoding="utf-8"))
    assert len(audit.ids) == len(set(audit.ids)), "Duplicate IDs"
    assert all(anchor in audit.ids for anchor in audit.anchors), "Broken anchor"
    assert all((WEB / resource).is_file() for resource in audit.resources), "Missing resource"
    for region in range(1, 5):
        for stage in range(1, 5):
            assert (WEB / "assets" / f"roi-{region}-stage-{stage}.webp").is_file()
    comparison_manifest = json.loads((WEB / "assets/comparison-manifest.json").read_text(encoding="utf-8"))
    assert len(comparison_manifest["assets"]) == 12
    for asset in comparison_manifest["assets"]:
        assert [asset["width"], asset["height"]] == comparison_manifest["dimensions"]
        assert hashlib.sha256((WEB / asset["asset"]).read_bytes()).hexdigest() == asset["sha256"]
    CHECKS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(WEB)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/"
    report = {"static_resources": "passed", "unique_ids": len(audit.ids), "viewports": []}
    errors = []
    failures = []
    executable = args.browser
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    if executable is None and edge.is_file():
        executable = edge
    try:
        with sync_playwright() as playwright:
            options = {"headless": True}
            if executable:
                options["executable_path"] = str(executable)
            browser = playwright.chromium.launch(**options)
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("requestfailed", lambda request: failures.append(request.url))
            page.on("response", lambda response: failures.append(f"{response.status} {response.url}") if response.status >= 400 else None)
            response = page.goto(base, wait_until="networkidle")
            assert response and response.ok
            assert page.locator("h1").inner_text() == "LiDAR2CAD"
            page.add_style_tag(content="html{scroll-behavior:auto!important}*{transition:none!important}")
            assert page.locator("main > section").first.get_attribute("id") == "comparison"
            assert page.locator("header.hero .hero-showcase").count() == 0
            assert page.locator(".comparison-inputs [data-comparison]").count() == 3
            assert page.locator(".comparison-baselines [data-comparison]").count() == 7
            reveal = page.locator("#hero-reveal")
            compare = page.locator(".hero-compare")
            assert reveal.is_enabled()
            reveal.focus()
            reveal.press("End")
            assert reveal.input_value() == "100"
            assert compare.evaluate("el => el.style.getPropertyValue('--reveal')") == "100%"
            reveal.press("Home")
            assert reveal.input_value() == "0"
            reveal.press("ArrowRight")
            assert reveal.input_value() == "1"
            assert "1% LiDAR point cloud" in reveal.get_attribute("aria-valuetext")
            compare.evaluate("el => el.scrollIntoView({block:'start'})")
            bounds = compare.bounding_box()
            assert bounds
            page.mouse.move(bounds["x"] + bounds["width"] * .25, bounds["y"] + bounds["height"] * .6)
            page.mouse.down()
            page.mouse.move(bounds["x"] + bounds["width"] * .75, bounds["y"] + bounds["height"] * .6, steps=6)
            page.mouse.up()
            assert 74 <= int(reveal.input_value()) <= 76
            reveal.evaluate("el => { el.value = '48'; el.dispatchEvent(new Event('input', {bubbles: true})); el.blur(); }")
            assert compare.evaluate("el => el.style.getPropertyValue('--reveal')") == "48%"
            report["hero_comparison"] = "pointer drag, range keyboard controls, and accessible values passed"
            pairs = {"cloud": "LiDAR point cloud", "lidar": "LiDAR-only", "design": "Design CAD", "hough": "P. Hough", "contour": "DP-Contour", "ransac": "RANSAC", "skeleton": "Morph-Skel", "lsd": "LSD", "fld": "FLD", "edlines": "EDLines"}
            for key, label in pairs.items():
                button = page.locator(f'[data-comparison="{key}"]')
                button.click()
                page.wait_for_function("key => document.querySelector('[data-comparison=' + key + ']').getAttribute('aria-pressed') === 'true' && document.querySelector('.hero-compare').getAttribute('aria-busy') === 'false'", arg=key)
                page.wait_for_function("Array.from(document.querySelectorAll('.hero-compare img')).every(i => i.complete && i.naturalWidth === 1800 && i.naturalHeight === 1480)")
                assert page.locator('[data-comparison][aria-pressed="true"]').count() == 1
                assert page.locator(".compare-before").get_attribute("src").endswith(f"compare-{key}.webp")
                assert page.locator(".before-label").inner_text() == label
                assert page.locator(".after-label").inner_text() == "Complete reconstruction"
                expected_complete = "compare-complete-annotated.webp" if key == "design" else "compare-complete.webp"
                assert page.locator(".compare-after").get_attribute("src").endswith(expected_complete)
                assert reveal.input_value() == "48"
                assert label in reveal.get_attribute("aria-valuetext")
            page.evaluate("""() => {
              ['design','hough','fld','lidar'].forEach(key => document.querySelector('[data-comparison=' + key + ']').click());
            }""")
            page.wait_for_function("document.querySelector('[data-comparison=lidar]').getAttribute('aria-pressed') === 'true' && document.querySelector('.hero-compare').getAttribute('aria-busy') === 'false'")
            assert page.locator(".compare-before").get_attribute("src").endswith("compare-lidar.webp")
            assert page.locator(".before-label").inner_text() == "LiDAR-only"
            page.locator('[data-comparison="cloud"]').click()
            page.wait_for_function("document.querySelector('.before-label').textContent === 'LiDAR point cloud'")
            report["comparison_choices"] = "all ten pairs passed; the Design CAD pair uses matching annotated views; all assets are aligned at 1800x1480"
            report["comparison_placement"] = "title-only hero; comparison appears before section 01"
            fullscreen = page.locator(".fullscreen-button")
            assert fullscreen.is_visible()
            fullscreen.click()
            page.wait_for_function("document.querySelector('.fullscreen-button').getAttribute('aria-pressed') === 'true'")
            assert page.evaluate("document.fullscreenElement === document.querySelector('.comparison-showcase')"), "Native fullscreen did not activate"
            fullscreen_bounds = page.locator(".comparison-showcase").bounding_box()
            assert fullscreen_bounds and abs(fullscreen_bounds["width"] - page.evaluate("innerWidth")) <= 1
            assert fullscreen_bounds["height"] <= page.evaluate("innerHeight") + 1
            assert reveal.is_visible() and fullscreen.is_visible()
            reveal.focus()
            reveal.press("End")
            assert compare.evaluate("el => el.style.getPropertyValue('--reveal')") == "100%"
            reveal.press("Home")
            assert compare.evaluate("el => el.style.getPropertyValue('--reveal')") == "0%"
            reveal.evaluate("el => { el.value = '48'; el.dispatchEvent(new Event('input', {bubbles: true})); }")
            page.screenshot(path=str(CHECKS / "comparison-fullscreen.png"), animations="disabled")
            fullscreen.click()
            page.wait_for_function("!document.fullscreenElement && document.querySelector('.fullscreen-button').getAttribute('aria-pressed') === 'false'")
            fullscreen.click()
            page.wait_for_function("document.fullscreenElement !== null")
            page.keyboard.press("Escape")
            page.wait_for_function("!document.fullscreenElement && document.querySelector('.fullscreen-button').getAttribute('aria-pressed') === 'false'")
            # Exercise the in-page fallback used when fullscreen is unavailable.
            page.locator(".comparison-showcase").evaluate("el => Object.defineProperty(el, 'requestFullscreen', {configurable: true, value: () => Promise.reject(new Error('Test unsupported fullscreen'))})")
            fullscreen.click()
            page.wait_for_function("document.querySelector('.comparison-showcase').classList.contains('is-expanded')")
            assert page.locator(".comparison-showcase").get_attribute("aria-modal") == "true"
            fullscreen.press("Shift+Tab")
            assert reveal.evaluate("el => el === document.activeElement")
            reveal.press("Tab")
            assert fullscreen.evaluate("el => el === document.activeElement")
            page.keyboard.press("Escape")
            assert not page.locator(".comparison-showcase").evaluate("el => el.classList.contains('is-expanded')")
            assert "comparison-expanded" not in (page.locator("body").get_attribute("class") or "")
            page.locator(".comparison-showcase").evaluate("el => delete el.requestFullscreen")
            report["comparison_fullscreen"] = "native enter, button exit, Escape, working slider, and keyboard-contained fallback passed"
            for width, height in ((1440, 1000), (1024, 900), (768, 1024), (390, 844), (320, 700)):
                page.set_viewport_size({"width": width, "height": height})
                page.evaluate("window.scrollTo(0, 0)")
                dimensions = page.evaluate("({viewport: innerWidth, document: document.documentElement.scrollWidth})")
                assert dimensions["document"] <= dimensions["viewport"], f"Page overflow at {width}: {dimensions}"
                size_ratio = page.locator(".comparison-showcase").evaluate("el => el.getBoundingClientRect().width / el.parentElement.getBoundingClientRect().width")
                assert abs(size_ratio - .8) < .002, f"Window not reduced by 20% at {width}: {size_ratio}"
                if width >= 1024:
                    rows = page.evaluate("""() => ({
                      inputs: Array.from(document.querySelectorAll('.comparison-inputs button')).map(el => el.getBoundingClientRect().top),
                      methods: Array.from(document.querySelectorAll('.comparison-baselines button')).map(el => el.getBoundingClientRect().top)
                    })""")
                    assert len(set(rows["inputs"])) == 1 and len(set(rows["methods"])) == 1
                    assert rows["methods"][0] > rows["inputs"][0]
                report["viewports"].append({"width": width, "height": height, "horizontal_overflow": False})
                page.screenshot(path=str(CHECKS / f"homepage-{width}.png"), full_page=False, animations="disabled")
                page.locator(".site-nav").evaluate("el => el.style.visibility = 'hidden'")
                page.locator("#comparison").screenshot(path=str(CHECKS / f"comparison-{width}.png"), animations="disabled")
                page.locator(".site-nav").evaluate("el => el.style.visibility = ''")
                if width == 390:
                    fullscreen.click()
                    page.wait_for_function("document.querySelector('.fullscreen-button').getAttribute('aria-pressed') === 'true'")
                    assert reveal.is_visible() and fullscreen.is_visible()
                    page.screenshot(path=str(CHECKS / "comparison-fullscreen-mobile.png"), animations="disabled")
                    fullscreen.click()
                    page.wait_for_function("document.querySelector('.fullscreen-button').getAttribute('aria-pressed') === 'false'")
                    page.locator('[data-comparison="edlines"]').click()
                    page.wait_for_function("document.querySelector('.before-label').textContent === 'EDLines'")
                    page.locator('[data-comparison="cloud"]').click()
                    page.wait_for_function("document.querySelector('.before-label').textContent === 'LiDAR point cloud'")
                    page.locator(".comparison-baselines").evaluate("el => el.scrollLeft = 0")

            report["comparison_layout"] = "desktop two-row selectors, mobile scrollable baseline choices, and rapid switching passed"
            report["comparison_size"] = "centered at 80% of content width at all five viewport sizes"

            page.set_viewport_size({"width": 1440, "height": 1000})
            page.locator("#examples").scroll_into_view_if_needed()
            for region in range(1, 5):
                page.locator(f'[data-region="{region}"]').click()
                assert page.locator(f'[data-region="{region}"]').get_attribute("aria-pressed") == "true"
                assert page.locator('[data-region][aria-pressed="true"]').count() == 1
                page.wait_for_function("Array.from(document.querySelectorAll('#roi-comparison img')).every(i => i.complete && i.naturalWidth > 0)")
                for stage in range(1, 5):
                    assert page.locator(f'[data-stage="{stage}"]').get_attribute("src") == f"assets/roi-{region}-stage-{stage}.webp"
                assert f"eva-0{region}" in page.locator("#region-note").inner_text()
            report["roi_switching"] = "all four regions and 16 images passed"
            page.locator("#examples [data-zoom]").first.click()
            assert page.locator("dialog").evaluate("element => element.open")
            page.keyboard.press("Escape")
            assert not page.locator("dialog").evaluate("element => element.open")
            assert "dialog-open" not in (page.locator("body").get_attribute("class") or "")
            page.locator("#examples [data-zoom]").nth(1).click()
            page.locator(".close-dialog").click()
            assert not page.locator("dialog").evaluate("element => element.open")
            report["image_dialog"] = "open, Escape, close button passed"

            for section_id in ("comparison", "overview", "method", "examples", "results", "mechanism", "generalization", "output", "protocols", "resources"):
                section = page.locator("#" + section_id)
                section.scroll_into_view_if_needed()
                page.wait_for_function("id => Array.from(document.querySelectorAll('#' + id + ' img')).every(i => i.complete && i.naturalWidth > 0)", arg=section_id)
                # Hide only the sticky navigation while taking section captures.
                page.locator(".site-nav").evaluate("el => el.style.visibility = 'hidden'")
                section.screenshot(path=str(CHECKS / f"section-{section_id}.png"), animations="disabled")
                page.locator(".site-nav").evaluate("el => el.style.visibility = ''")
            report["all_section_images"] = "loaded; ten sections captured for visual review"
            sensitivity_ratio = page.locator(".sensitivity-figures").evaluate("el => el.getBoundingClientRect().width / el.parentElement.getBoundingClientRect().width")
            provenance_ratio = page.locator(".provenance-figure").evaluate("el => el.getBoundingClientRect().width / parseFloat(getComputedStyle(el.parentElement).gridTemplateColumns.split(' ')[0])")
            assert abs(sensitivity_ratio - .8) < .002
            assert abs(provenance_ratio - .8) < .002
            for selector in ('.sensitivity-figures [data-zoom]', '.provenance-figure [data-zoom]'):
                for button in page.locator(selector).all():
                    button.click()
                    assert page.locator("dialog").evaluate("el => el.open")
                    page.keyboard.press("Escape")
            report["compact_charts"] = "three charts reduced by 20% on desktop; click-to-enlarge preserved"
            page.locator("#protocols details").nth(2).locator("summary").click()
            assert page.locator("#protocols details").nth(2).evaluate("element => element.open")
            report["protocol_accordion"] = "passed"
            pdf_response = context.request.get(base + "assets/LiDAR2CAD-paper.pdf")
            assert pdf_response.ok and pdf_response.headers.get("content-type", "").startswith("application/pdf")
            assert pdf_response.body().startswith(b"%PDF-")
            report["paper_pdf"] = "200 OK; valid PDF header"
            release_path = WEB / "assets/releases/release.json"
            if release_path.is_file():
                release = json.loads(release_path.read_text(encoding="utf-8"))
                archive_checks = []
                for package in release["packages"]:
                    downloaded = context.request.get(base + package["url"])
                    assert downloaded.ok, package["filename"]
                    payload = downloaded.body()
                    assert len(payload) == package["bytes"]
                    assert hashlib.sha256(payload).hexdigest() == package["sha256"]
                    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                        assert archive.testzip() is None
                    assert page.locator('a[download][href="' + package["url"] + '"]').count() >= 1
                    archive_checks.append(package["filename"])
                with page.expect_download() as info:
                    page.locator('#resources a[download]').first.click()
                assert info.value.suggested_filename == release["packages"][0]["filename"]
                report["release_downloads"] = {"archives": archive_checks, "sha256": "matched", "browser_download": "passed"}
            page.set_viewport_size({"width": 390, "height": 844})
            for selector in (".sensitivity-figures", ".provenance-figure"):
                ratio = page.locator(selector).evaluate("el => el.getBoundingClientRect().width / el.parentElement.getBoundingClientRect().width")
                assert abs(ratio - 1) < .002
            report["compact_charts_mobile"] = "full-width charts retained for small-screen readability"
            page.locator('[data-region="2"]').click()
            page.locator("#examples").screenshot(path=str(CHECKS / "mobile-examples.png"), animations="disabled")
            for table in page.locator(".table-wrap").all():
                assert table.evaluate("el => el.scrollWidth > el.clientWidth")
            report["mobile_tables"] = "contained horizontal scrolling"
            context.close()
            offline = browser.new_context(java_script_enabled=False, viewport={"width": 1280, "height": 900})
            static_page = offline.new_page()
            static_page.goto((WEB / "index.html").as_uri(), wait_until="load")
            assert static_page.locator("h1").inner_text() == "LiDAR2CAD"
            assert static_page.locator(".metric").count() == 4
            assert static_page.locator("#hero-reveal").is_disabled()
            assert static_page.locator("[data-comparison]:disabled").count() == 10
            assert not static_page.locator(".fullscreen-button").is_visible()
            report["no_javascript_file_open"] = "passed"
            offline.close()
            file_context = browser.new_context(viewport={"width": 1280, "height": 900})
            file_page = file_context.new_page()
            file_page.goto((WEB / "index.html").as_uri(), wait_until="load")
            file_page.locator('[data-comparison="design"]').click()
            file_page.wait_for_function("document.querySelector('.before-label').textContent === 'Design CAD'")
            assert file_page.locator(".compare-before").get_attribute("src").endswith("compare-design.webp")
            assert file_page.locator(".compare-after").get_attribute("src").endswith("compare-complete-annotated.webp")
            file_page.locator('[data-region="3"]').click()
            assert "eva-03" in file_page.locator("#region-note").inner_text()
            file_context.close()
            report["interactive_file_open"] = "passed"
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    assert not errors, f"Browser errors: {errors}"
    assert not failures, f"Failed resources: {failures}"
    report["browser_errors"] = errors
    report["failed_requests"] = failures
    (CHECKS / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
