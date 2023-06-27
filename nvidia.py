from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import requests, json, time, os
from msedge.selenium_tools import Edge, EdgeOptions

sleeptime = 1
timeout = 10
tryout = 30

# checkout and close tab, return false if unsuccessful
def checkout(driver, quantity):

    # Click checkout
    driver.get("https://www.bestbuy.com/checkout/r/fast-track")

    # Wait for Place Your Order
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.contact-card__order-button > div > button.button__fast-track')))
    except TimeoutException:
        driver.get("https://www.bestbuy.com/checkout/r/fast-track")
        wait = WebDriverWait(driver, 10)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.contact-card__order-button > div > button.button__fast-track')))
    
    try:
        wait = WebDriverWait(driver, 10)
        el_switch = wait.until(EC.presence_of_element_located((By.LINK_TEXT, 'Switch to Shipping')))
        driver.execute_script("arguments[0].click();", el_switch)
    except NoSuchElementException:
        pass

    wait = WebDriverWait(driver, 10)
    wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, '.page-spinner__spinner')))
    el_place = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.contact-card__order-button > div > button.button__fast-track')))
    driver.execute_script("arguments[0].click();", el_place)

    # SafeKey: Added protection provided by American Express SafeKey®
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.thank-you-enhancement__oc-heading')))
    el_order = driver.find_element_by_xpath('//*[@id="checkoutApp"]/div/div[1]/div[1]/main/div[2]/div[2]/div/section/div[2]/div[2]/span')
    print("Success: {}".format(el_order.text))

    return True
    

# Setup chrome
options = EdgeOptions()
options.use_chromium = True
options.add_argument("--user-data-dir=C:\\Users\\blaw\\AppData\\Local\\Microsoft\\Edge\\User Data")
options.add_argument("--start-maximized")
#options.add_argument("--no-sandbox")
driverpath = 'msedgedriver.exe'

driver = Edge(driverpath, options=options)
driver.implicitly_wait(timeout)

# Log in and be ready
driver.get('https://www.nvidia.com/en-us/account/edit-profile/')
el_email = driver.find_element_by_id('emailAddress')
el_email.send_keys('shoppingford@live.com')
el_pass = driver.find_element_by_id('password')
el_pass.send_keys('bz^MZ8Tm&s!thb')

time.sleep(1000)

WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.XPATH, "//iframe[starts-with(@name, 'a-') and starts-with(@src, 'https://www.google.com/recaptcha')]")))
WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, 'recaptcha-anchor'))).click()
driver.find_element_by_id('loginButton').click()
  
product_skus = {
    6429440: 1000,
    6432399: 1000,
    6430621: 1000,
}

import sys
sys.exit()

bbapikey = 'JL8HaMwGAGmLJZfuwM0LktYg'

# search through products until see one in stock
while product_skus:
    for sku in product_skus:
        print(product_skus)
        if product_skus[sku] > 0:
            r = requests.get("https://api.bestbuy.com/v1/products/{}.json?apiKey={}".format(sku, bbapikey))
            if r.status_code == 200:
                res = json.loads(r.content)
                print("SKU: {}; available: {}; last upate: {}".format(res['sku'], res['onlineAvailability'], res['onlineAvailabilityUpdateDate']))
                if res['onlineAvailability'] is True:
                    # spin up tab and buy
                    driver.get(res['addToCartUrl'])
                    if checkout(driver, res['quantityLimit']):
                        product_skus[sku] -= 1

        # wait between refresh
        time.sleep(sleeptime)

