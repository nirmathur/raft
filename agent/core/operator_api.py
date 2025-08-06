"""
Operator API  (FastAPI)
-----------------------
Exposes authenticated endpoints for operator control and configuration:

    • POST /pause       {"flag": true|false}
    • POST /kill
    • GET  /state       -> {"pause": bool, "kill": bool}
    • POST /config      {"rho_max": float, "energy_multiplier": float}
    • POST /reload_model

Auth: single Bearer token read from env  OPERATOR_TOKEN.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.core.config import get_config, reload_model_weights, update_config
from agent.core.escape_hatches import (is_paused, load_state, request_kill,
                                       request_pause)

TOKEN = os.getenv("OPERATOR_TOKEN", "devtoken")  # set in docker-compose.yml

app = FastAPI(title="RAFT Operator API")


def _auth(request: Request):
    if request.headers.get("authorization") != f"Bearer {TOKEN}":
        raise HTTPException(401, "unauthorized")


class PauseReq(BaseModel):
    flag: bool


class ConfigReq(BaseModel):
    rho_max: Optional[float] = None
    energy_multiplier: Optional[float] = None


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


@app.post("/config")
async def config(request: Request, body: ConfigReq):
    """Update runtime configuration parameters."""
    _auth(request)
    
    try:
        updated_config = update_config(
            rho_max=body.rho_max,
            energy_multiplier=body.energy_multiplier
        )
        return JSONResponse({
            "ok": True,
            "config": {
                "rho_max": updated_config.rho_max,
                "energy_multiplier": updated_config.energy_multiplier
            }
        })
    except ValueError as e:
        raise HTTPException(400, f"Invalid configuration: {e}")
    except Exception as e:
        raise HTTPException(500, f"Configuration update failed: {e}")


@app.post("/reload_model")
async def reload_model(request: Request):
    """Reload model weights from MODEL_PATH."""
    _auth(request)
    
    success = reload_model_weights()
    if success:
        return JSONResponse({"ok": True, "reloaded": True})
    else:
        raise HTTPException(500, "Model reload failed")
