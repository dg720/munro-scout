import json
import time
import os
import requests
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

INPUT_FILE = "munro_list.json"
OUTPUT_FILE = "munro_descriptions.json"
GPX_DIR = "gpx_files"
SAVE_EVERY = 5
MAX_WORKERS = 3

os.makedirs(GPX_DIR, exist_ok=True)


def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_route_page_url(driver):
    try:
        h2s = driver.find_elements(By.TAG_NAME, "h2")
        for h2 in h2s:
            if "Detailed route description and map" in h2.text:
                sibling = h2.find_element(By.XPATH, "following-sibling::p[1]/b/a")
                return sibling.get_attribute("href")
    except Exception:
        pass
    return None


def extract_description_from_route_page(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "walk_desc"))
        )

        title = driver.title.strip()

        desc_paragraphs = driver.find_elements(By.CSS_SELECTOR, "#walk_desc .desc p")
        description = "\n\n".join(
            p.text.strip() for p in desc_paragraphs if p.text.strip()
        )

        summary = ""
        try:
            summary_heading = driver.find_element(
                By.XPATH, "//h2[normalize-space(text())='Summary']"
            )
            summary_paragraph = summary_heading.find_element(
                By.XPATH, "following-sibling::p[1]"
            )
            summary = summary_paragraph.text.strip()
        except Exception:
            pass

        def get_section_text(header):
            try:
                h2 = driver.find_element(
                    By.XPATH, f"//h2[normalize-space(text())='{header}']"
                )
                p = h2.find_element(By.XPATH, "following-sibling::p[1]")
                return p.text.strip()
            except Exception:
                return ""

        terrain = get_section_text("Terrain")
        public_transport = get_section_text("Public Transport")
        start_raw = get_section_text("Start")
        start = start_raw.split("Open in Google Maps")[0].strip().rstrip(".")

        stats = {"distance": "", "time": "", "grade": 0, "bog": 0}
        try:
            dl_items = driver.find_elements(By.CSS_SELECTOR, "#col dl dt")
            for dt in dl_items:
                label = dt.text.strip().lower()
                try:
                    dd = dt.find_element(
                        By.XPATH, "following-sibling::dd[1]"
                    ).text.strip()
                except Exception:
                    dd = ""
                if "distance" in label and "km" in dd:
                    try:
                        stats["distance"] = float(dd.split("km")[0].strip())
                    except ValueError:
                        stats["distance"] = ""
                elif "time" in label:
                    if "-" in dd:
                        times = dd.split("-")
                        try:
                            h1 = float(times[0].strip().split()[0])
                            h2 = float(times[1].strip().split()[0])
                            stats["time"] = round((h1 + h2) / 2, 2)
                        except Exception:
                            stats["time"] = dd
                    else:
                        try:
                            stats["time"] = float(dd.split()[0])
                        except Exception:
                            stats["time"] = dd
        except Exception:
            pass

        try:
            stats["grade"] = len(driver.find_elements(By.CSS_SELECTOR, ".grade img"))
            stats["bog"] = len(driver.find_elements(By.CSS_SELECTOR, ".bog img"))
        except Exception:
            stats["grade"] = 0
            stats["bog"] = 0

        gpx_path = ""
        try:
            gpx_link = driver.find_element(
                By.XPATH, "//a[contains(@href, 'download.php')]"
            )
            download_page_url = urljoin(
                "https://www.walkhighlands.co.uk", gpx_link.get_attribute("href")
            )

            driver.get(download_page_url)
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//a[contains(@href, '.gpx') and contains(text(), 'I STILL WANT TO DOWNLOAD')]",
                    )
                )
            )
            direct_gpx_link = driver.find_element(
                By.XPATH,
                "//a[contains(@href, '.gpx') and contains(text(), 'I STILL WANT TO DOWNLOAD')]",
            )
            gpx_url = direct_gpx_link.get_attribute("href")

            safe_name = os.path.basename(gpx_url).replace(".gpx", "")
            gpx_filename = os.path.join(GPX_DIR, f"{safe_name}.gpx")

            if not os.path.exists(gpx_filename):
                r = requests.get(gpx_url)
                r.raise_for_status()
                with open(gpx_filename, "wb") as f:
                    f.write(r.content)
            gpx_path = gpx_filename
        except Exception as e:
            print(f"⚠️ GPX file not found on page: {e}")

        return (
            title,
            summary,
            description,
            terrain,
            public_transport,
            start,
            stats,
            gpx_path,
        )

    except Exception as e:
        print(f"⚠️ Failed to extract from {url}: {e}")
        return (
            "",
            "",
            "",
            "",
            "",
            "",
            {"distance": "", "time": "", "grade": 0, "bog": 0},
            "",
        )


def process_munro(munro):
    name = munro["name"]
    url = munro["url"]
    print(f"➡️  Starting: {name}")

    driver = setup_driver()
    try:
        driver.get(url)
        time.sleep(random.uniform(0.5, 1))
        route_page_url = get_route_page_url(driver)

        if route_page_url:
            title, summary, desc, terrain, pub_transport, start, stats, gpx_path = (
                extract_description_from_route_page(driver, route_page_url)
            )
        else:
            print(f"⚠️ No route link found on {url}")
            title, summary, desc, terrain, pub_transport, start, stats, gpx_path = (
                "",
                "",
                "",
                "",
                "",
                "",
                {"distance": "", "time": "", "grade": 0, "bog": 0},
                "",
            )

        enriched_munro = {
            **munro,
            "title": title,
            "summary": summary,
            "description": desc,
            "terrain": terrain,
            "public_transport": pub_transport,
            "start": start,
            "distance": stats["distance"],
            "time": stats["time"],
            "grade": stats["grade"],
            "bog": stats["bog"],
            "gpx_file": gpx_path,
        }

    except Exception as e:
        print(f"⚠️ Error processing {url}: {e}")
        enriched_munro = {
            **munro,
            "title": "",
            "summary": "",
            "description": "",
            "terrain": "",
            "public_transport": "",
            "start": "",
            "distance": "",
            "time": "",
            "grade": 0,
            "bog": 0,
            "gpx_file": "",
        }
    finally:
        driver.quit()

    return enriched_munro


def main():
    print("📥 Loading Munro list...")
    munros = load_json(INPUT_FILE)
    existing_data = load_json(OUTPUT_FILE)

    enriched_by_url = {m["url"]: m for m in existing_data if m.get("description")}
    remaining = [m for m in munros if m["url"] not in enriched_by_url]

    print(f"🔗 Total Munros: {len(munros)}")
    print(f"✅ Already processed: {len(enriched_by_url)}")
    print(f"🧭 Remaining: {len(remaining)}\n")

    enriched = list(enriched_by_url.values())

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_munro, munro): munro for munro in remaining}
        for i, future in enumerate(as_completed(futures), start=1):
            enriched_munro = future.result()
            enriched.append(enriched_munro)

            if i % SAVE_EVERY == 0 or i == len(remaining):
                save_json(enriched, OUTPUT_FILE)
                print(f"💾 Saved {i} of {len(remaining)}")

    print(f"\n🎉 Done. Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
