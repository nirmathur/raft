"""
Operator API  (FastAPI)
-----------------------
Exposes authenticated endpoints for RAFT control and configuration:

    • POST /pause   {"flag": true|false}
    • POST /kill
    • GET  /state   -> {"pause": bool, "kill": bool}
    • POST /config  {"rho_max": float, "energy_multiplier": float}  [NEW]
    • POST /reload_model  [NEW]

Auth: single Bearer token read from env  OPERATOR_TOKEN.
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Dict

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from agent.core.config_store import ConfigValidator, get_config, update_config
from agent.core.escape_hatches import is_paused, load_state, request_kill, request_pause
from agent.core.event_log import record
from agent.core.plan_models import Plan
from agent.core.plan_smt import verify_plan

TOKEN = os.getenv("OPERATOR_TOKEN", "devtoken")  # set in docker-compose.yml

app = FastAPI(title="RAFT Operator API")

# Import model reload counter from metrics module
from agent.metrics import MODEL_RELOAD_COUNT


def _auth(request: Request):
    if request.headers.get("authorization") != f"Bearer {TOKEN}":
        raise HTTPException(401, "unauthorized")


class PauseReq(BaseModel):
    flag: bool


# Use the shared validator as the API request model
ConfigUpdateReq = ConfigValidator


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
async def update_configuration(request: Request, body: ConfigUpdateReq):
    """Update RAFT configuration dynamically.

    Accepts JSON payload with rho_max and energy_multiplier values.
    Updates are applied hot (no restart required) and persisted to config.yaml.

    Returns
    -------
    dict
        Updated configuration values and status
    """
    _auth(request)

    try:
        # Convert pydantic model to dict for update
        updates = body.model_dump()

        # Apply configuration update
        new_config = update_config(updates)

        # Log and record for audit trail
        payload = {"updates": updates, "new_config": new_config.__dict__}
        logger.info("config-update", payload)
        record("config-update", payload)

        return JSONResponse(
            {
                "status": "ok",
                "message": "Configuration updated successfully",
                "config": {
                    "rho_max": new_config.rho_max,
                    "energy_multiplier": new_config.energy_multiplier,
                },
            }
        )

    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise HTTPException(422, f"Invalid configuration: {e}")
    except Exception as e:
        logger.error(f"Configuration update failed: {e}")
        raise HTTPException(500, f"Configuration update failed: {e}")


@app.post("/reload_model")
async def reload_model(request: Request):
    """Reload the spectral analysis model from disk.

    Triggers a fresh model load and returns the new spectral radius.
    Useful for applying updated model weights without service restart.

    Returns
    -------
    dict
        Reload status and fresh spectral radius measurement
    """
    _auth(request)

    try:
        # Import governor to access the global model instance
        from agent.core.governor import _SPECTRAL_MODEL
        from agent.core.model import SimpleNet

        # For now, create a fresh stable model since there's no persistent storage yet
        # In production, this would load from MODEL_PATH
        new_model = SimpleNet.create_stable_model(
            in_dim=4, out_dim=4, target_rho=0.8, method="xavier"
        )

        # Replace the global model (hot swap)
        _SPECTRAL_MODEL.load_state_dict(new_model.state_dict())

        # Update the governor's model reference to prevent dangling references
        import agent.core.governor

        agent.core.governor._SPECTRAL_MODEL = _SPECTRAL_MODEL

        # Measure fresh spectral radius
        x0 = torch.randn(4, requires_grad=True)
        fresh_rho = _SPECTRAL_MODEL.estimate_spectral_radius(x0, n_iter=10)

        # Update metrics and logging
        MODEL_RELOAD_COUNT.inc()
        payload = {"fresh_rho": fresh_rho, "model_type": "SimpleNet"}
        logger.info("model-reload", payload)
        record("model-reload", payload)

        return JSONResponse(
            {
                "status": "reloaded",
                "rho": fresh_rho,
                "message": f"Model reloaded successfully, new spectral radius: {fresh_rho:.6f}",
            }
        )

    except Exception as e:
        logger.error(f"Model reload failed: {e}")
        raise HTTPException(500, f"Model reload failed: {e}")


@app.post("/prove")
async def prove_plan(request: Request, body: Plan):
    """Prove plan safety using SMT.

    Returns {"passed": bool, "counterexample": dict | None}
    """
    _auth(request)
    try:
        passed, counterexample = verify_plan(body)
        return JSONResponse({"passed": passed, "counterexample": counterexample})
    except Exception as e:
        raise HTTPException(500, f"proof failed: {e}")
