# RAFT Operator API Documentation

The RAFT Operator API provides authenticated endpoints for controlling and configuring the RAFT system during runtime. All endpoints require Bearer token authentication and return JSON responses.

## Authentication

All endpoints require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <OPERATOR_TOKEN>
```

The token is configured via the `OPERATOR_TOKEN` environment variable (default: "devtoken").

## Base URL

When running locally via Docker:
```
http://localhost:8001
```

## Endpoints

### System Control

#### GET /state

Returns the current system state.

**Request:**
```bash
curl -H "Authorization: Bearer <OPERATOR_TOKEN>" \
     http://localhost:8001/state
```

**Response:**
```json
{
  "pause": false,
  "kill": false
}
```

#### POST /pause

Pause or resume the governor cycle.

**Request:**
```bash
curl -X POST \
     -H "Authorization: Bearer <OPERATOR_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"flag": true}' \
     http://localhost:8001/pause
```

**Response:**
```json
{
  "ok": true,
  "pause": true
}
```

#### POST /kill

Request system shutdown.

**Request:**
```bash
curl -X POST \
     -H "Authorization: Bearer <OPERATOR_TOKEN>" \
     http://localhost:8001/kill
```

**Response:**
```json
{
  "ok": true,
  "kill": true
}
```

### Dynamic Configuration

#### POST /config

Update RAFT runtime configuration without service restart. Changes are applied immediately and persisted to `config.yaml`.

**Parameters:**
- `rho_max` (float): Spectral radius threshold (0 < value < 1)
- `energy_multiplier` (float): Energy consumption multiplier (1 ≤ value ≤ 4)

**Request:**
```bash
curl -X POST \
     -H "Authorization: Bearer <OPERATOR_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"rho_max": 0.85, "energy_multiplier": 3.0}' \
     http://localhost:8001/config
```

**Success Response (200):**
```json
{
  "status": "ok",
  "message": "Configuration updated successfully",
  "config": {
    "rho_max": 0.85,
    "energy_multiplier": 3.0
  }
}
```

**Validation Error (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "rho_max"],
      "msg": "Input should be less than 1",
      "input": 1.2,
      "type": "less_than",
      "ctx": {"lt": 1.0}
    }
  ]
}
```

**Example Validation Failure:**
```bash
curl -X POST \
     -H "Authorization: Bearer devtoken" \
     -H "Content-Type: application/json" \
     -d '{"rho_max": 1.5, "energy_multiplier": 5.0}' \
     http://localhost:8001/config

# Response (422):
{
  "detail": [
    {
      "type": "less_than",
      "loc": ["body", "rho_max"],
      "msg": "Input should be less than 1",
      "input": 1.5,
      "ctx": {"lt": 1.0}
    },
    {
      "type": "less_than_equal", 
      "loc": ["body", "energy_multiplier"],
      "msg": "Input should be less than or equal to 4",
      "input": 5.0,
      "ctx": {"le": 4.0}
    }
  ]
}
```

**Notes:**
- Configuration changes propagate on the next governor cycle (no restart required)
- Values are validated before application
- Updates are atomic - either all succeed or all fail
- Audit events are logged for all configuration changes

### Model Reload

#### POST /reload_model

Reload the spectral analysis model and return fresh spectral radius measurement.

**Request:**
```bash
curl -X POST \
     -H "Authorization: Bearer <OPERATOR_TOKEN>" \
     http://localhost:8001/reload_model
```

**Success Response (200):**
```json
{
  "status": "reloaded",
  "rho": 0.756432,
  "message": "Model reloaded successfully, new spectral radius: 0.756432"
}
```

**Error Response (500):**
```json
{
  "detail": "Model reload failed: <error_details>"
}
```

**Notes:**
- Triggers immediate model weight refresh
- Returns fresh spectral radius measurement
- Updates Prometheus metrics (`raft_model_reload_total`)
- Governor sees new weights on next cycle

## Integration Notes

### Configuration Propagation

- **rho_max**: Used by spectral radius guard in governor cycle
- **energy_multiplier**: Used by energy guard calculations
- Changes take effect on the next `run_one_cycle()` call
- No service restart required

### Model Reloading

- Performs hot-swap of model weights in global `_SPECTRAL_MODEL` instance
- Governor continues using new model immediately
- Safe to call during active governor cycles
- Model persistence will be implemented in future versions

### Error Handling

All endpoints follow standard HTTP status codes:
- `200`: Success
- `401`: Unauthorized (invalid/missing token)
- `422`: Validation error (invalid request data)
- `500`: Internal server error

### Audit Trail

Configuration updates and model reloads are automatically logged:
- **Structured logging**: Via loguru with event type and payload
- **Event recording**: Via `record()` function for audit persistence
- **Metrics**: Prometheus counters for operational monitoring

### Prometheus Metrics

The operator API exposes the following metrics for monitoring:

- `raft_model_reload_total`: Counter tracking successful model reloads
- `raft_spectral_radius`: Current spectral radius value 
- `raft_spectral_threshold`: Current spectral radius threshold (dynamic)
- `raft_cycles_total`: Total governor cycles completed
- `raft_proof_pass_total` / `raft_proof_fail_total`: Proof verification stats

Access metrics at: `http://localhost:8002/metrics` (when governor is running)

## Examples

### Update Spectral Radius Threshold

Lower the spectral radius threshold for stricter stability:

```bash
curl -X POST \
     -H "Authorization: Bearer devtoken" \
     -H "Content-Type: application/json" \
     -d '{"rho_max": 0.7, "energy_multiplier": 2.0}' \
     http://localhost:8001/config
```

### Increase Energy Budget

Allow higher energy consumption:

```bash
curl -X POST \
     -H "Authorization: Bearer devtoken" \
     -H "Content-Type: application/json" \
     -d '{"rho_max": 0.9, "energy_multiplier": 3.5}' \
     http://localhost:8001/config
```

### Refresh Model Weights

Reload the model to apply updated weights:

```bash
curl -X POST \
     -H "Authorization: Bearer devtoken" \
     http://localhost:8001/reload_model
```

### Check System Status

Get current pause/kill state:

```bash
curl -H "Authorization: Bearer devtoken" \
     http://localhost:8001/state
```

## Security Considerations

- **Token-based authentication**: All endpoints require valid Bearer token
- **Input validation**: Request payloads are strictly validated using Pydantic
- **Audit logging**: All configuration changes are logged and recorded
- **Safe defaults**: Invalid configurations are rejected, system continues with current values
- **Atomic updates**: Configuration changes are all-or-nothing
- **Thread safety**: Configuration updates use locks to prevent race conditions
- **Cross-platform persistence**: Atomic file operations work on Windows and POSIX systems

## Troubleshooting

### Invalid Token

```bash
curl -X POST http://localhost:8001/config
# Response: {"detail": "unauthorized"}
```

**Solution**: Include the Authorization header with correct token.

### Validation Errors

```bash
curl -X POST \
     -H "Authorization: Bearer devtoken" \
     -H "Content-Type: application/json" \
     -d '{"rho_max": 1.5}' \
     http://localhost:8001/config
# Response: Validation error about rho_max range
```

**Solution**: Check parameter ranges and ensure all required fields are provided.

### Service Not Running

```bash
curl http://localhost:8001/state
# Response: Connection refused
```

**Solution**: Ensure the operator API service is running via Docker Compose or manually.

## Development

### Running Tests

```bash
poetry run pytest tests/test_operator_api.py -v
```

### Local Development

For local development without Docker:

```bash
# Set environment
export OPERATOR_TOKEN="devtoken"

# Run the API server
poetry run uvicorn agent.core.operator_api:app --port 8001 --reload
```

The API will be available at `http://localhost:8001` with interactive docs at `/docs`.