"""
Operator API  (FastAPI)
-----------------------
Exposes three authenticated endpoints:

    • POST /pause   {"flag": true|false}
    • POST /kill
    • GET  /state   -> {"pause": bool, "kill": bool}

Auth: single Bearer token read from env  OPERATOR_TOKEN.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.core.escape_hatches import (is_paused, load_state, request_kill,
                                       request_pause)

TOKEN = os.getenv("OPERATOR_TOKEN", "devtoken")  # set in docker-compose.yml

app = FastAPI(title="RAFT Operator API")


def _auth(request: Request):
    if request.headers.get("authorization") != f"Bearer {TOKEN}":
        raise HTTPException(401, "unauthorized")


class PauseReq(BaseModel):
    flag: bool


@app.get("/state")
async def state(request: Request):
    _auth(request)
    load_state()
    return JSONResponse({"pause": is_paused(), "kill": False})


@app.post("/pause")
async def pause(request: Request, body: PauseReq):
    _auth(request)
    request_pause(body.flag)
    return JSONResponse({"ok": True, "pause": body.flag})


@app.post("/kill")
async def kill(request: Request):
    _auth(request)
    request_kill()
    return JSONResponse({"ok": True, "kill": True})
