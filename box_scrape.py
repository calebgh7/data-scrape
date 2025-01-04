# Activate venv in terminal: source /Users/calebhobbs/Desktop/CodingProjects/venv/bin/activate


from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import os
import json
import time
import gspread
from gspread_dataframe import set_with_dataframe
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# Get the current date and time
now = datetime.now()
today = now.strftime("%Y-%m-%d")
print(f"Today's date is {today}")

#hide
myMlsUsername = os.environ['MLS_USER']
myMlsPassword = os.environ['MLS_PASS']

# Load service account JSON from the environment variable
service_account_info = json.loads(os.environ['SERVICE_ACCOUNT_JSON'])

# Set Chrome options for headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--no-sandbox")  # Required for running in GitHub Actions
chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems

# Use the Chrome webdriver
driver = webdriver.Chrome(options=chrome_options)

# Function to login to the Flexmls website
def login(url, usernameId, username, passwordId, password):
    driver.get(url)
    driver.find_element(By.ID, usernameId).send_keys(username)
    driver.find_element(By.ID, passwordId).send_keys(password)
    # Use XPath to find the submit button by its type attribute
    submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
    try:
        submit_button.click()
    except:
        print("Login failed, please check login credentials.")
        driver.quit()

# Call the login function using the login details stored in the YAML file
login("https://armls.flexmls.com/", "username", myMlsUsername, "password", myMlsPassword)

# Navigate to the saved searches page link
driver.get("https://apps.flexmls.com/search/saved_searches?_variant=flagship")

wait=WebDriverWait(driver, 15)

# Find and click on the Referral Recovery saved search
caleb_buy_box_scrape = wait.until(EC.element_to_be_clickable(
    (By.XPATH, '//span[@class="savedSearchName" and text()="Caleb Scrape Buy Box"]/ancestor::div[@class="c-item__title u-flex-align-center"]')
))
try:
    caleb_buy_box_scrape.click()
except:
    print("Could not reach the Referral Scrape saved search. Please try again.")
    driver.quit()

time.sleep(5)

# Scrape page html and parse it
resultPage = driver.execute_script('return document.body.innerHTML')
parsedPage = BeautifulSoup(resultPage, "html.parser")
# Find all listing result rows
resultBoxes = parsedPage.find_all('tr', class_='listing')
print(f"There are {len(resultBoxes)} results from the Referral Recovery search.")

# Initialize DataFrame
listingData = pd.DataFrame(columns=['MLS', 'Address', 'CSZ', 'Status', 'Price', 'Days on Market', 'Bedrooms', 'Bathrooms', 'Year Built'])

# For row in results, scrape data. If no data is found, return a default value
for resultBox in resultBoxes:
    # Use a function to scrape text or return a default value
    def find_text_or_default(bs_element, query, attrs, default="Not Found"):
        found_element = bs_element.find(query, attrs=attrs)
        return found_element.text.strip() if found_element else default
    
    # Use a function to get agent data
    def drill_agents(agent_class, agent_type):
        listing_members = []
        td_elements = resultBox.find_all('td', class_= agent_class)
        # Check if any elements are found
        if not td_elements:
            print(f"Error: For property with MLS: {mls}, no agent data found with the specified class.")
        # Iterate over <td> elements to find <a> elements
        for td in td_elements:
            # Find all <a> tags within the current <td> element
            a_tags = td.find_all('a', class_='columnlink')
            if not a_tags:
                return "None"
            else:
                # Extract the text from each <a> tag
                for a_tag in a_tags:
                    listing_member = a_tag.text.strip()
                    listing_members.append(listing_member)
                agent = listing_members[0]
                agency = listing_members[1]
                if agent_type == 'agent':
                    return agent
                elif agent_type == 'agency':
                    return agency
                else:
                    return "Invalid agent type specified."

    # define the elements to scrape
    mls=find_text_or_default(resultBox,'a', {'id': 'listingNumberAnchor'})
    address=find_text_or_default(resultBox,'span', {'ls': 'address'})
    csz=find_text_or_default(resultBox,'span', {'ls': 'csz'})
    status=find_text_or_default(resultBox,'span', {'class': 'status_A'})
    price = find_text_or_default(resultBox, 'span', {'class': 'price'})
    daysOnMarket = find_text_or_default(resultBox, 'td', {'class': 'gridtd gridtd-std extracolumns column_cdom'})
    bedrooms = find_text_or_default(resultBox, 'td', {'class': 'gridtd gridtd-std extracolumns column_total_br'})
    bathrooms = find_text_or_default(resultBox, 'td', {'class': 'gridtd gridtd-std extracolumns column_total_bath'})
    yearBuilt = find_text_or_default(resultBox, 'td', {'class': 'gridtd gridtd-std extracolumns column_yr_built'})
    
    # Create a mini DataFrame to store the scraped data
    miniFrame=pd.DataFrame(columns=list(listingData.columns),data=[[mls, address, csz, status, price, daysOnMarket, bedrooms, bathrooms, yearBuilt]])
    listingData=pd.concat([listingData, miniFrame])

    #Sort listing
    listingData['Days on Market'] = pd.to_numeric(listingData['Days on Market'], errors='coerce')
    listingData = listingData.sort_values(by='Days on Market', ascending=False)

# Define the scope for Google Sheets and Google Drive
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Load credentials from the service account key file
creds = ServiceAccountCredentials.from_json_keyfile_name(service_account_info, scope)
client = gspread.authorize(creds)

# Open the Google Sheet by name and select the first sheet
sheet = client.open("ScrapeResults").sheet1
# Clear the entire sheet before writing new data
sheet.batch_clear(["A2:I1000"])

# Update the sheet with the DataFrame content
set_with_dataframe(sheet, listingData)  # This writes the DataFrame to the Google Sheet
print("Google Sheet updated successfully")

# Quit the driver
driver.quit()