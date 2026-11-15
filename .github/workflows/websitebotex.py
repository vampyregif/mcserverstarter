import os
import sys
import time
import psutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

os.system("pkill -9 chrome")
for process in psutil.process_iter(attrs=["pid", "name"]):
    if process.info["name"] and "chrome" in process.info["name"].lower():
        try:
            psutil.Process(process.info["pid"]).terminate()
        except psutil.NoSuchProcess:
            pass

USER_DATA_DIR = "/tmp/seedloaf-session"
MARKER_FILE = f"{USER_DATA_DIR}/.valid_session"

if os.path.exists(MARKER_FILE):
    os.remove(MARKER_FILE)

options = Options()
options.binary_location = "/opt/chrome/chrome"
options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
options.add_argument("--profile-directory=Default")
options.add_argument("--headless=new")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

service = Service("/usr/local/bin/chromedriver")
driver = webdriver.Chrome(options=options, service=service)

# Match ONLY visible Start, Unarchive, or Stop buttons (by text, aria-label, or title)
CONTROL_BUTTON_XPATH = (
    "//button["
    "contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start') or "
    "contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'unarchive') or "
    "contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'stop') or "
    "contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start') or "
    "contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'stop') or "
    "contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start') or "
    "contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'stop')"
    "]"
)


def save_debug(name="debug"):
    try:
        driver.save_screenshot(f"{name}.png")
        with open(f"{name}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"Saved {name}.png and {name}.html (URL: {driver.current_url})")
    except Exception as e:
        print(f"Failed to save debug files: {e}")


def get_button_label(el):
    return (
        el.text.strip()
        or el.get_attribute("aria-label")
        or el.get_attribute("title")
        or ""
    ).strip()


def run_loginflow(usernamesec, passwordsec):
    if not usernamesec or not passwordsec:
        print("❌ USERNAME or PASSWORD environment variables are empty.")
        sys.exit(1)

    username = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "identifier-field"))
    )
    print("At username screen:", driver.current_url)
    username.clear()
    username.send_keys(usernamesec)
    username.send_keys(Keys.RETURN)
    time.sleep(3)

    errors = driver.find_elements(By.ID, "error-identifier")
    if errors and errors[0].is_displayed():
        print("❌ Username is incorrect:", errors[0].text)
        sys.exit(1)

    password = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "password-field"))
    )
    print("At password screen:", driver.current_url)
    password.clear()
    password.send_keys(passwordsec)
    password.send_keys(Keys.RETURN)
    print("Submitted password, waiting for redirect...")

    for _ in range(15):
        time.sleep(1)
        url = driver.current_url
        if "accounts.seedloaf.com" not in url:
            break
        if "factor-two" in url:
            print("❌ Blocked by Clerk 2FA / New Device email verification:", url)
            save_debug("factor_two")
            sys.exit(1)
        pw_errors = driver.find_elements(By.ID, "error-password")
        if pw_errors and pw_errors[0].is_displayed():
            print("❌ Password is incorrect:", pw_errors[0].text)
            sys.exit(1)

    print("URL after password submit:", driver.current_url)


def open_world_controls():
    try:
        return WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH, CONTROL_BUTTON_XPATH))
        )
    except Exception:
        # If /dashboard shows a World Overview card first, click into the world link
        world_links = driver.find_elements(
            By.CSS_SELECTOR, "a[href*='/dashboard/'], a[href*='/world'], a[href*='/server']"
        )
        if world_links:
            print(f"Navigating into world page: {world_links[0].get_attribute('href')}")
            driver.execute_script("arguments[0].click();", world_links[0])
            time.sleep(3)

    return WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.XPATH, CONTROL_BUTTON_XPATH))
    )


try:
    driver.get("https://seedloaf.com/dashboard")
    time.sleep(4)

    if "accounts.seedloaf.com" in driver.current_url or "sign-in" in driver.current_url:
        print("🔐 Not logged in — running login flow:", driver.current_url)
        run_loginflow(os.getenv("USERNAME"), os.getenv("PASSWORD"))

        if "dashboard" not in driver.current_url:
            driver.get("https://seedloaf.com/dashboard")
            time.sleep(4)
    else:
        print("✅ Already logged in:", driver.current_url)

    button = open_world_controls()

    os.makedirs(USER_DATA_DIR, exist_ok=True)
    with open(MARKER_FILE, "w") as f:
        f.write("session valid")

    label = get_button_label(button)
    btn_text = label.lower()

    if "stop" in btn_text:
        print(f"Stop button found ('{label}') — world already running.")
    elif "unarchive" in btn_text:
        driver.execute_script("arguments[0].scrollIntoView(true);", button)
        driver.execute_script("arguments[0].click();", button)
        print(f"✅ Clicked '{label}' — waiting for Start button...")
        time.sleep(6)

        start_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start') "
                    "or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start')]",
                )
            )
        )
        driver.execute_script("arguments[0].click();", start_btn)
        print(f"✅ Clicked '{get_button_label(start_btn)}'!")
        time.sleep(4)
    else:
        driver.execute_script("arguments[0].scrollIntoView(true);", button)
        driver.execute_script("arguments[0].click();", button)
        print(f"✅ Clicked '{label}'!")
        time.sleep(4)

    save_debug("after_click")

except Exception as e:
    print(f"❌ Failed with error: {e}")
    for el in driver.find_elements(By.XPATH, "//button | //a"):
        txt = get_button_label(el).replace("\n", " ")
        if txt or el.is_displayed():
            print(
                f"Found <{el.tag_name}> visible={el.is_displayed()} "
                f"text='{txt}' class='{el.get_attribute('class')}' href='{el.get_attribute('href')}'"
            )
    save_debug("error")
    sys.exit(1)

finally:
    driver.quit()
