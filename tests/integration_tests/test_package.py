from json import load
import os
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_mrscraper import MrScraperToolkit
from dotenv import load_dotenv

load_dotenv()

tools = MrScraperToolkit().get_tools()

llm = ChatOpenAI(model="gpt-4o-mini")

agent = create_react_agent(llm, tools)

# Invoking the agent
result = agent.invoke({
    "messages": [{"role": "user", "content": "Scrape https://www.cireba.com/property-detail/spotts-prospect/residential-properties-for-sale-in-cayman-islands/allure-10-waterfront-condo-2"}]
})
print(result["messages"][-1].content)