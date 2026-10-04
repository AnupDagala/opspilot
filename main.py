from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from core import BoundaryError, BusyError, Engine, Store


class RunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task: str = Field(min_length=3, max_length=2000)
    request_key: str = Field(min_length=8, max_length=100)
    demo_failure: bool = True
    operation: Literal['process','draft_only','audit'] = 'process'
    ticket_ids: list[int] = Field(default_factory=list,max_length=8)


class ReviewDecision(BaseModel):
    decision: Literal['approved','rejected']


def create_app(store=None, engine=None):
    store = store or Store()
    engine = engine or Engine(store)

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield

    app = FastAPI(title='OpsPilot', lifespan=lifespan)
    app.state.store, app.state.engine = store, engine

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        # Local prototype: restrict host and reject cross-origin mutations.
        host = request.headers.get('host','').split(':')[0]
        if host not in ['localhost','127.0.0.1','testserver']:
            return JSONResponse({'detail':'This demo only accepts localhost requests.'},status_code=403)
        origin = request.headers.get('origin')
        if request.method not in ['GET','HEAD'] and origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail':'Cross-origin actions are blocked.'},status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        return response

    @app.get('/')
    def dashboard():
        return FileResponse(Path(__file__).parent / 'static' / 'index.html')

    @app.get('/static/{name}')
    def asset(name: Literal['app.js','style.css']):
        return FileResponse(Path(__file__).parent / 'static' / name)

    @app.get('/api/state')
    def state():
        return {**store.snapshot(),'mode':engine.mode,'scripted':engine.scripted,'boundaries':'Fictional local data. Drafts only. Refunds are simulated.'}

    @app.get('/api/tickets/{tid}')
    def detail(tid:int):
        try:
            return store.detail(tid)
        except BoundaryError as exc:
            raise HTTPException(404,str(exc))

    @app.post('/api/runs',status_code=202)
    def start(body:RunRequest, background:BackgroundTasks):
        if body.operation!='process' and not body.ticket_ids:
            raise HTTPException(422,'Draft-only and audit goals require explicit ticket IDs.')
        for tid in body.ticket_ids:
            try: store.ticket(tid)
            except BoundaryError: raise HTTPException(404,'Unknown scoped ticket.')
        try:
            run, fresh = store.start_run(body.task,body.request_key,engine.mode)
        except BusyError as exc:
            raise HTTPException(409,str(exc))
        if fresh:
            background.add_task(engine.run,run['id'],body.task,body.demo_failure,body.operation,body.ticket_ids)
        return {'run':run,'duplicate':not fresh}

    @app.post('/api/demo',status_code=202)
    def seeded_demo(body:RunRequest, background:BackgroundTasks):
        if body.operation!='process' or body.ticket_ids:
            raise HTTPException(422,'Seeded demo runs the full process contract. Use /api/runs for scoped goals.')
        # Reseed and create the run in one transaction; duplicate requests never reset twice.
        try:
            run, fresh = store.start_run(body.task,body.request_key,engine.mode,reseed=True)
        except BusyError as exc:
            raise HTTPException(409,str(exc))
        if fresh:
            background.add_task(engine.run,run['id'],body.task,body.demo_failure,body.operation,body.ticket_ids)
        return {'run':run,'duplicate':not fresh,'scope':'local fictional demo data'}

    @app.post('/api/reviews/{review_id}')
    def decide(review_id:int,body:ReviewDecision):
        try:
            return store.decide(review_id,body.decision)
        except BusyError as exc:
            raise HTTPException(409,str(exc))
        except BoundaryError as exc:
            raise HTTPException(409,str(exc))

    @app.post('/api/reset')
    def reset():
        try:
            store.reset()
        except BusyError as exc:
            raise HTTPException(409,str(exc))
        return {'reset':True,'scope':'local fictional demo database only'}

    return app


app = create_app()
