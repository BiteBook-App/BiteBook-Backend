import os

from dotenv import load_dotenv
from pydantic import BaseModel
import json
from typing import List

import asyncio
from crawl4ai import AsyncWebCrawler, LLMConfig
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.extraction_strategy import LLMExtractionStrategy

load_dotenv()

class Recipe(BaseModel):
    ingredients: List[str]
    instructions: List[str]

async def extract(inputUrl):
    browser_config = BrowserConfig()  # Default browser configuration

    # Define the LLM extraction strategy
    llm_strategy = LLMExtractionStrategy(
        llm_config = LLMConfig(provider="groq/deepseek-r1-distill-llama-70b", api_token=os.getenv("GROQ_API_KEY")),  # Name of the LLM provider and API token
        extraction_type="schema",  # Type of extraction to perform
        schema=Recipe.schema_json(),
        instruction=(
            "You are an expert at extracting structured information from text. Given a chunk of text, isolate only the ingredients list and recipe instructions while removing any unnecessary information. Extract the ingredients and be sure to retain the amount of ingredients (i.e., 1 TBSP, 2 cups, etc.). Extract the recipe steps and present them in a numbered format. Remove any unrelated information (such as author notes, introductions, ads, reader comments or interactions, etc.). Ensure the extracted output is clear and concise. If no valid ingredients or instructions are found, return: No recipe data found."
        ), 
        input_format="markdown",  # Format of the input content
        verbose=True,  # Enable verbose logging
    )


    # Create a pruning filter to reduce unnecessary content
    prune_filter = PruningContentFilter(
        # Lower → more content retained, higher → more content pruned
        threshold=0.45,           
        threshold_type="dynamic",  
        # # Ignore nodes with <5 words
        # min_word_threshold=5      
    )

    # Insert it into a Markdown Generator
    md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)

    # Pass LLM strategy and filter to CrawlerRunConfig
    config = CrawlerRunConfig(
        markdown_generator=md_generator,
        extraction_strategy=llm_strategy
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url=inputUrl,
            config=config
        )

        if result.success:
            data = json.loads(result.extracted_content)
            print("Extracted items:", data)

            llm_strategy.show_usage()
        else:
            print("Error: ", result.error_message)


async def main():
    await extract('https://teakandthyme.com/blueberry-chiffon-cake/')



if __name__ == "__main__":
    asyncio.run(main())