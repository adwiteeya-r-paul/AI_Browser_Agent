import streamlit as st
import pandas as pd
import asyncio
import json
import re
import subprocess
import sys
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from groq import Groq

st.set_page_config(page_title="Job Search Criteria Extractor", page_icon=":mag_right:", layout="wide")

st.title("What type of job are you looking for?")
st.write("Enter your job search query below!")
user_query = st.text_area(
    "Job Search Query",
    placeholder="e.g., 'I am looking for a remote software developer position in Europe focusing on data science and machine learning.'"
)

try:
    with st.spinner("Setting up your agent..."):
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    st.success("Agent is here!")
except Exception as e:
    st.error(f"Error setting up Playwright: {e}")

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
            await page.wait_for_load_state("networkidle")
            if "login" in page.url:
                st.error("You need to be logged into LinkedIn for job scraping to work.")
                return pd.DataFrame()
            try:
                await page.get_by_placeholder("Title, skill, or company").fill(search_query)
            except:
                await page.locator('input.jobs-search-box__text-input').nth(0).fill(search_query)
            if query.get('location'):
                try:
                    await page.get_by_label("City, state, or zip code").fill(query['location'])
                except:
                    await page.locator('input.jobs-search-box__text-input').nth(1).fill(query['location'])
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
                        company = await card.locator("div.artdeco-entity-lockup__subtitle span").inner_text()
                        location = await card.locator("ul.job-card-container__metadata-wrapper li span").inner_text()
                        df_list.append({
                            "Title": title,
                            "URL": url,
                            "Company": company,
                            "Location": location
                        })
                    except Exception:
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
        response_dict = json.loads(valid_json_string)
        return response_dict
    else:
        st.error("Groq response did not contain a valid JSON object.")
        raise ValueError("Groq response missing JSON.")

async def main_async_flow():
    if user_query:
        with st.spinner("Processing your query..."):
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

if st.button("Get Set Go!"):
    asyncio.run(main_async_flow())


















