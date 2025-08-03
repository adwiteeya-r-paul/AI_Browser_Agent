import streamlit as st
import pandas as pd
import asyncio
import os
import json
import re
import subprocess
import sys
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from groq import Groq

try:
    with st.spinner("Setting up your agent..."):
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    st.success("Agent is here!")
except subprocess.CalledProcessError as e:
    st.error(f"Error installing Playwright browsers: {e}")
except FileNotFoundError:
    st.error("Playwright is not installed. Please add 'playwright' to your requirements.txt.")

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
        context: BrowserCon




























