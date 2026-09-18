import json
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from src.paths import MATCH_LIST_DIR
from scraper.file_selector import get_league_season_selection
import time
import random

url = "https://fbref.com/en/comps/9/2024-2025/2024-2025-Premier-League-Stats"
options = Options
driver = webdriver.Chrome(options=options)
driver.get(url)
WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "shots_all")))
soup = BeautifulSoup(driver.page_source, "html.parser")
