from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

utility_router = APIRouter()

@utility_router.get('/')
async def root():
  return HTMLResponse("""<h1>Soleda AI</h1>
    <p>Soleda provides a useful, reliable and trustworthy conversational agent to help you understand your data.</p>""")

@utility_router.get('/health')
async def heartbeat():
  return {'status': 'ok'} 