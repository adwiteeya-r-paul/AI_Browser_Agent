import streamlit as st
import pandas as pd
import asyncio
import os
import json
import re
import time

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from groq import Groq

groq_client = Groq(api_key=st.secrets["GROQ_API"])

async def search(link: str, query: dict) -> pd.DataFrame:
    df_list = []
    
    search_items = []
    if query.get('job_title'): search_items.append(query['job_title'])
    if query.get('keywords'): search_items.extend(query['keywords'])
    if query.get('company'): search_items.append(query['company'])
    search_query = " ".join(search_items)

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        context: BrowserContext = await browser.new_context()
        page: Page = await context.new_page()

        await page.goto(link)

        if link == "https://www.linkedin.com/jobs/search/":
            what = page.locator("input[aria-label='Search by title, skill, or company']")
            where = page.locator("input[aria-label='Search by location']")

            await what.fill(search_query)
            if query.get('location'):
                await where.fill(query['location'])
            
            await page.keyboard.press("Enter")

            try:
                await page.wait_for_selector("div[data-results-list-top-scroll-sentinel] + ul li", timeout=15000)
                job_cards = page.locator("div[data-results-list-top-scroll-sentinel] + ul li")
                job_count = await job_cards.count()
                st.info(f"Found {job_count} job listings. Scraping now...")
            except Exception as e:
                st.error(f"No results found or an error occurred: {e}")
                job_count = 0

            if job_count > 0:
                for i in range(job_count):
                    card = job_cards.nth(i)
                    try:
                        card_link = card.locator("a")
                        title = await card_link.get_attribute("aria-label")
                        url = await card_link.get_attribute("href")
                        
                        company_container = card.locator("div.artdeco-entity-lockup__subtitle")
                        company = await company_container.locator("span").inner_text()
                        
                        location_container = card.locator("ul.job-card-container__metadata-wrapper")
                        location = await location_container.locator("li span").inner_text()
                        
                        df_list.append({
                            "Title": title,
                            "URL": url,
                            "Company": company,
                            "Location": location
                        })
                    except Exception as e:
                        st.warning(f"Error scraping card {i+1}: {e}")
                        continue
        
        await context.close()
        await browser.close()
    
    return pd.DataFrame(df_list, columns=["Title", "URL", "Company", "Location"])

async def query_groq(prompt: str) -> dict:
