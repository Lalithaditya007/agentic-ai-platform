import glob

files = glob.glob('d:/XLVenture/Project/backend/runtime/agents/*.py')

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    modified = content
    
    if 'from config import get_llm_model' not in modified and 'BaseAgent' in modified:
        modified = modified.replace('from runtime.agents.base_agent import BaseAgent', 'from runtime.agents.base_agent import BaseAgent\nfrom config import get_llm_model')
        
    modified = modified.replace('llm_model = "google/gemma-2-9b-it:free"', 'llm_model = get_llm_model()')
    modified = modified.replace('llm_model = "deepseek/deepseek-r1:free"', 'llm_model = get_llm_model()')
        
    if modified != content:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(modified)
        print(f'Updated {f}')
