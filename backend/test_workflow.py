import requests
import time

project_id = 'b4bc15fd-a8d3-4ed8-8648-fd69edb04a8c'
url = f'http://127.0.0.1:8000/api/workflows/run?project_id={project_id}'
print(f'Triggering run for project {project_id}...')
r = requests.post(url)
print(r.status_code, r.text)

if r.status_code == 200:
    run_id = r.json().get('run_id')
    print(f'Started run {run_id}. Waiting for completion...')
    
    for _ in range(60):
        time.sleep(5)
        status_url = f'http://127.0.0.1:8000/api/workflows/{run_id}'
        r_stat = requests.get(status_url)
        if r_stat.status_code == 200:
            data = r_stat.json()
            status = data.get('status')
            print(f'Status: {status}')
            if status in ['completed', 'failed', 'paused_hitl']:
                print(f'Finished/Paused with status: {status}!')
                
                # Fetch queue to see results
                queue_url = f'http://127.0.0.1:8000/api/hitl/queue?project_id={project_id}'
                rq = requests.get(queue_url)
                if rq.status_code == 200:
                    q_data = rq.json()
                    print('HITL Queue Companies:')
                    for b in q_data.get('queue', []):
                        print(f" - {b.get('company_name')} (Confidence: {b.get('overall_confidence')})")
                else:
                    print('Failed to get queue:', rq.text)
                break
