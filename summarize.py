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

class Ingredient(BaseModel):
    name: str
    amount: str  # Example: "2 cups", "1 tbsp"

class Recipe(BaseModel):
    name: str
    ingredients: List[Ingredient]  # List of ingredient dictionaries
    instructions: List[str]  # List of steps

async def extract(inputUrl):    
    browser_config = BrowserConfig()  # Default browser configuration

    # Define the LLM extraction strategy
    llm_strategy = LLMExtractionStrategy(
        llm_config = LLMConfig(provider="groq/deepseek-r1-distill-llama-70b", api_token=os.getenv("GROQ_API_KEY")),  # Name of the LLM provider and API token
        extraction_type="schema",  # Type of extraction to perform
        schema=Recipe.schema_json(),
        instruction=(
            "Extract the name of the recipe, the ingredients (with original measurements), and numbered recipe steps. Remove any unrelated content (e.g., notes, ads, comments). Ensure clarity and conciseness."
        ), 
        input_format="fit_markdown",  # Format of the input content
        verbose=True,  # Enable verbose logging
        chunk_token_threshold=6000
    )


    # Create a pruning filter to reduce unnecessary content
    prune_filter = PruningContentFilter(
        # Lower → more content retained, higher → more content pruned
        threshold=0.65,           
        threshold_type="dynamic"
    )

    # Insert it into a Markdown Generator
    md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)

    # Pass LLM strategy and filter to CrawlerRunConfig
    config = CrawlerRunConfig(
        markdown_generator=md_generator,
        extraction_strategy=llm_strategy,
        delay_before_return_html=2
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url=inputUrl,
            config=config
        )

        if result.success:
            print(result.markdown.fit_markdown)
            data = json.loads(result.extracted_content)
            print("Extracted items:", data)

            llm_strategy.show_usage()
            return data
        else:
            print("Error: ", result.error_message)


async def main():
    return await extract('https://www.madewithlau.com/recipes/pan-fried-fish')



if __name__ == "__main__":
    asyncio.run(main())