from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import json
import time

URL = "https://www.walkhighlands.co.uk/munros/munros-a-z"
OUTPUT_FILE = "munro_list.json"


def fetch_munro_list():
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # enable for silent runs
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    driver.get(URL)

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#arealist tbody a, #areamap tbody a")
            )
        )
    except TimeoutException:
        print("❌ Timed out waiting for Munro links.")
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        driver.quit()
        raise

    raw_links = driver.find_elements(
        By.CSS_SELECTOR, "#arealist tbody a, #areamap tbody a"
    )
    print(f"✅ Found {len(raw_links)} Munro links")

    munros = []
    seen = set()

    for link in raw_links:
        name = link.text.strip()
        href = link.get_attribute("href")

        if name and href:
            slug = href.split("/")[-1].strip()
            full_url = f"https://www.walkhighlands.co.uk/munros/{slug}"

            if full_url not in seen:
                munros.append({"name": name, "url": full_url})
                seen.add(full_url)
                print(f"🔗 {name} → {full_url}")

    driver.quit()
    return munros


def save_to_json(data, filename=OUTPUT_FILE):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("🚀 Fetching Munro list...")
    munros = fetch_munro_list()
    print(f"✅ Found {len(munros)} Munros")
    save_to_json(munros)
    print(f"💾 Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
