import axios from 'axios';

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(async (config) => {
  // Only import createClient when needed to avoid issues if used server-side
  const { createClient } = await import('@/lib/supabase');
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`;
  }
  return config;
});

export const apiService = {
  // Projects
  createProject: (description: string) => 
    api.post('/projects', { name: "Agentic Workflow Project", business_description: description }),
  
  getProject: (id: string) => 
    api.get(`/projects/${id}`),

  listProjects: () => 
    api.get('/projects'),

  // ICP
  generateIcp: (projectId: string, description: string) => 
    api.post(`/projects/${projectId}/understand`, { business_description: description }),
    
  getIcp: (projectId: string) => 
    api.get(`/projects/${projectId}/icp`),
    
  updateIcp: (projectId: string, icpData: any) => 
    api.put(`/projects/${projectId}/icp`, icpData),
    
  confirmIcp: (projectId: string) => 
    api.post(`/projects/${projectId}/icp/confirm`),

  // Workflows
  runWorkflow: (projectId: string) => 
    api.post(`/workflows/run?project_id=${projectId}`),
    
  getWorkflowStatus: (runId: string) => 
    api.get(`/workflows/${runId}`),

  getWorkflowGraph: (runId: string) =>
    api.get(`/workflows/${runId}/graph`),

  // DAG Preview
  generateDagPreview: (projectId: string) =>
    api.post(`/projects/${projectId}/dag-preview`),

  getDagPreview: (projectId: string) =>
    api.get(`/projects/${projectId}/dag-preview`),

  // HITL
  getHitlQueue: () => 
    api.get('/hitl/queue'),
    
  getHitlBrief: (briefId: string) => 
    api.get(`/hitl/${briefId}`),
    
  submitHitlAction: (briefId: string, action: string, details: any = {}) => 
    api.post(`/hitl/${briefId}/action`, { action, details }),

  // Analytics
  getAnalytics: (projectId: string) => 
    api.get(`/analytics/${projectId}`),
};
