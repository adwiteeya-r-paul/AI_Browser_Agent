import streamlit as st
import pandas as pd
import asyncio
import os
import json
import re
import time
import subprocess
import sys

try:
    with st.spinner("Setting up your agent..."):
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    st.success("Agent is here!")
except subprocess.CalledProcessError as e:
    st.error(f"Error installing Playwright browsers: {e}")
except FileNotFoundError:
    st.error("Playwright is not installed. Please add 'playwright' to your requirements.txt.")

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from groq import Groq

groq_client = Groq(api_key="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")

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
            page.getByLabel("Title, skill or company").fill(search_query)
            page.getByLabel("City, state or zip code").fill(search_query)


            
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
    system_prompt = """You are an expert at extracting job search criteria from a user's natural language query. Your task is to identify and extract the job title, keywords, location, and job type (e.g., 'remote', 'hybrid', 'on-site').
    
    The output should be a JSON object ONLY, with the following keys:
    - 'job_title': (a string, or null if not specified)
    - 'keywords': (an array of strings)
    - 'company': (a string, or null if not specified)
    - 'location': (a string, or null if not specified)
    
    Example Query: 'I am a recent graduate looking for remote software developer jobs in Europe focusing on data science and machine learning.'
    Example JSON:
    {
    "job_title": "software developer",
    "keywords": ["data science", "machine learning"],
    "company": null,
    "location": "Europe (remote)"
    }
    
    Now, please process the following user query:
    '{prompt}'
    """
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.2
    )

    response_text = response.choices[0].message.content.strip()
    
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    
    if json_match:
        valid_json_string = json_match.group(0)
        try:
            response_dict = json.loads(valid_json_string)
            return response_dict
        except json.JSONDecodeError as e:
            st.error(f"Failed to decode JSON from Groq: {e}")
            raise e
    else:
        st.error("Groq response did not contain a valid JSON object.")
        raise ValueError("Groq response missing JSON.")

st.set_page_config(
    page_title="Job Search Criteria Extractor",
    page_icon=":mag_right:",
    layout="wide"
)

st.title("What type of job are you looking for?")
st.write("Enter your job search query below!")
user_query = st.text_area(
    "Job Search Query",
    placeholder="e.g., 'I am looking for a remote software developer position in Europe focusing on data science and machine learning.'"
)

async def main_async_flow():
    if user_query:
        with st.spinner("Processing your query..."):
            try:
                job_criteria = await query_groq(user_query)
                st.success("Job criteria extracted successfully!")
                

                st.info("Starting web scraper...")
                df_results = await search("https://www.linkedin.com/jobs/search/", job_criteria)

                if not df_results.empty:
                    st.success("Scraping complete!")
                    st.dataframe(df_results, use_container_width=True)
                    
                    csv = df_results.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name='search_results.csv',
                        mime='text/csv',
                    )
                else:
                    st.warning("No job listings were found matching your criteria.")

            except Exception as e:
                st.error(f"An error occurred: {e}")

if st.button("Get Set Go!"):
    asyncio.run(main_async_flow())














