import asyncio
from config import get_llm_model, settings
from runtime.agents.company_discovery import CompanyDiscoveryAgent

async def test():
    print(f'LLM_PROVIDER: {settings.LLM_PROVIDER}')
    print(f'Model String: {get_llm_model()}')
    
    agent = CompanyDiscoveryAgent({'industry': ['hospital'], 'geography': ['us']})
    agent.llm_model = get_llm_model()
    
    try:
        res = await agent.ask_llm_for_json('Return {"test": 123}')
        print('JSON Result:', res)
    except Exception as e:
        print('ERROR:', e)

asyncio.run(test())
